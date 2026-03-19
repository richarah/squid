"""
Schema loading and representation for SQUID.

Supports loading from Spider JSON format, SQLite databases, and SQLAlchemy engines.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

import networkx as nx
from lemminflect import getLemma


@dataclass(slots=True)
class Column:
    """A database column with name, type, and metadata."""

    name: str
    type: str
    primary_key: bool = False
    foreign_key: Optional[Tuple[str, str]] = None  # (table, column)
    nullable: bool = True

    def __post_init__(self) -> None:
        # Intern string names for memory efficiency
        self.name = sys.intern(self.name.lower())
        self.type = sys.intern(self.type.lower())


@dataclass(slots=True)
class Table:
    """A database table with columns and primary keys."""

    name: str
    columns: List[Column]
    primary_keys: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.name = sys.intern(self.name.lower())
        self.primary_keys = [sys.intern(pk.lower()) for pk in self.primary_keys]

    def column_names(self) -> List[str]:
        return [col.name for col in self.columns]

    def get_column(self, name: str) -> Optional[Column]:
        name_lower = name.lower()
        for col in self.columns:
            if col.name == name_lower:
                return col
        return None


@dataclass(slots=True)
class ForeignKey:
    """A foreign key relationship between two tables."""

    src_table: str
    src_column: str
    dst_table: str
    dst_column: str

    def __post_init__(self) -> None:
        self.src_table = sys.intern(self.src_table.lower())
        self.src_column = sys.intern(self.src_column.lower())
        self.dst_table = sys.intern(self.dst_table.lower())
        self.dst_column = sys.intern(self.dst_column.lower())


@dataclass(slots=True)
class Schema:
    """
    Database schema with tables, columns, and foreign keys.

    Precomputes all derived data structures for fast access during compilation.
    """

    db_id: str
    tables: List[Table]
    foreign_keys: List[ForeignKey]

    # Precomputed lookup structures (populated in __post_init__)
    _table_name_set: FrozenSet[str] = field(default_factory=frozenset, init=False)
    _table_lookup: Dict[str, Table] = field(default_factory=dict, init=False)
    _column_lookup: Dict[str, List[str]] = field(default_factory=dict, init=False)
    _column_type_lookup: Dict[Tuple[str, str], str] = field(default_factory=dict, init=False)
    _fk_graph: nx.Graph = field(default_factory=nx.Graph, init=False)
    _lemmatized_tables: Dict[str, str] = field(default_factory=dict, init=False)
    _lemmatized_columns: Dict[str, Tuple[str, str]] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        """Precompute all derived data structures."""
        # Intern db_id
        self.db_id = sys.intern(self.db_id)

        # Build table lookup
        self._table_name_set = frozenset(t.name for t in self.tables)
        self._table_lookup = {t.name: t for t in self.tables}

        # Build column lookup
        for table in self.tables:
            self._column_lookup[table.name] = table.column_names()
            for col in table.columns:
                self._column_type_lookup[(table.name, col.name)] = col.type

        # Build FK graph
        self._fk_graph = self._build_fk_graph()

        # Build lemmatized lookup tables
        self._build_lemma_indices()

    def _build_fk_graph(self) -> nx.Graph:
        """Build a graph where nodes are tables and edges are foreign keys."""
        graph = nx.Graph()

        # Add all tables as nodes
        for table in self.tables:
            graph.add_node(table.name)

        # Add foreign keys as edges
        for fk in self.foreign_keys:
            graph.add_edge(
                fk.src_table,
                fk.dst_table,
                src_col=fk.src_column,
                dst_col=fk.dst_column
            )

        return graph

    def _build_lemma_indices(self) -> None:
        """Build lemmatized lookup tables for fuzzy matching."""
        # Table name lemmas
        for table in self.tables:
            lemmas = getLemma(table.name, upos='NOUN')
            if lemmas:
                for lemma in lemmas:
                    self._lemmatized_tables[lemma.lower()] = table.name
            # Also store original
            self._lemmatized_tables[table.name] = table.name

        # Column name lemmas
        for table in self.tables:
            for col in table.columns:
                lemmas = getLemma(col.name, upos='NOUN')
                if lemmas:
                    for lemma in lemmas:
                        self._lemmatized_columns[lemma.lower()] = (table.name, col.name)
                # Also store original
                self._lemmatized_columns[col.name] = (table.name, col.name)

    def table_names(self) -> List[str]:
        """Return list of all table names."""
        return list(self._table_name_set)

    def has_table(self, name: str) -> bool:
        """Check if table exists in schema."""
        return name.lower() in self._table_name_set

    def get_table(self, name: str) -> Optional[Table]:
        """Get table by name."""
        return self._table_lookup.get(name.lower())

    def column_names(self, table: str) -> List[str]:
        """Return list of column names for a table."""
        return self._column_lookup.get(table.lower(), [])

    def column_type(self, table: str, column: str) -> Optional[str]:
        """Return type of a column."""
        return self._column_type_lookup.get((table.lower(), column.lower()))

    def fk_graph(self) -> nx.Graph:
        """Return the foreign key graph."""
        return self._fk_graph

    def find_join_path(self, table1: str, table2: str) -> Optional[List[str]]:
        """
        Find shortest join path between two tables using FK graph.
        Returns list of table names forming the path, or None if no path exists.
        """
        table1_lower = table1.lower()
        table2_lower = table2.lower()

        if not self.has_table(table1_lower) or not self.has_table(table2_lower):
            return None

        try:
            return nx.shortest_path(self._fk_graph, table1_lower, table2_lower)
        except nx.NetworkXNoPath:
            return None

    @classmethod
    def from_spider(cls, tables_json_path: str, db_id: str) -> Schema:
        """
        Load schema from Spider's tables.json format.

        Args:
            tables_json_path: Path to tables.json file
            db_id: Database identifier to load from the file

        Returns:
            Schema object
        """
        with open(tables_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Find the database entry
        db_entry = None
        for entry in data:
            if entry['db_id'] == db_id:
                db_entry = entry
                break

        if db_entry is None:
            raise ValueError(f"Database '{db_id}' not found in {tables_json_path}")

        # Parse tables
        tables: List[Table] = []
        table_names = db_entry['table_names_original']
        column_names_original = db_entry['column_names_original']
        column_types = db_entry['column_types']
        primary_keys = set(db_entry['primary_keys'])

        # Build tables
        for table_idx, table_name in enumerate(table_names):
            # Get columns for this table
            table_columns: List[Column] = []
            table_pks: List[str] = []

            for col_idx, (tbl_idx, col_name) in enumerate(column_names_original):
                if tbl_idx == table_idx:
                    is_pk = col_idx in primary_keys
                    col_type = column_types[col_idx] if col_idx < len(column_types) else 'text'

                    col = Column(
                        name=col_name,
                        type=col_type,
                        primary_key=is_pk
                    )
                    table_columns.append(col)

                    if is_pk:
                        table_pks.append(col_name)

            tables.append(Table(
                name=table_name,
                columns=table_columns,
                primary_keys=table_pks
            ))

        # Parse foreign keys
        fks: List[ForeignKey] = []
        for fk_col_idx, ref_col_idx in db_entry['foreign_keys']:
            # Get source table and column
            src_table_idx, src_col_name = column_names_original[fk_col_idx]
            src_table_name = table_names[src_table_idx]

            # Get destination table and column
            dst_table_idx, dst_col_name = column_names_original[ref_col_idx]
            dst_table_name = table_names[dst_table_idx]

            fks.append(ForeignKey(
                src_table=src_table_name,
                src_column=src_col_name,
                dst_table=dst_table_name,
                dst_column=dst_col_name
            ))

        return cls(db_id=db_id, tables=tables, foreign_keys=fks)

    @classmethod
    def from_sqlite(cls, db_path: str, db_id: Optional[str] = None) -> Schema:
        """
        Load schema by introspecting a SQLite database.

        Args:
            db_path: Path to SQLite database file
            db_id: Optional database identifier (defaults to filename)

        Returns:
            Schema object
        """
        if db_id is None:
            db_id = Path(db_path).stem

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get all tables
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """)
        table_names = [row[0] for row in cursor.fetchall()]

        tables: List[Table] = []
        foreign_keys: List[ForeignKey] = []

        for table_name in table_names:
            # Get column info
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns_data = cursor.fetchall()

            columns: List[Column] = []
            primary_keys: List[str] = []

            for col_data in columns_data:
                col_name = col_data[1]
                col_type = col_data[2] or 'text'
                is_nullable = col_data[3] == 0
                is_pk = col_data[5] == 1

                columns.append(Column(
                    name=col_name,
                    type=col_type,
                    primary_key=is_pk,
                    nullable=is_nullable
                ))

                if is_pk:
                    primary_keys.append(col_name)

            tables.append(Table(
                name=table_name,
                columns=columns,
                primary_keys=primary_keys
            ))

            # Get foreign keys for this table
            cursor.execute(f"PRAGMA foreign_key_list({table_name})")
            fk_data = cursor.fetchall()

            for fk_row in fk_data:
                dst_table = fk_row[2]
                src_col = fk_row[3]
                dst_col = fk_row[4]

                foreign_keys.append(ForeignKey(
                    src_table=table_name,
                    src_column=src_col,
                    dst_table=dst_table,
                    dst_column=dst_col
                ))

        conn.close()
        return cls(db_id=db_id, tables=tables, foreign_keys=foreign_keys)

    @classmethod
    def from_sqlalchemy(cls, engine, db_id: Optional[str] = None) -> Schema:
        """
        Load schema by introspecting via SQLAlchemy.

        Args:
            engine: SQLAlchemy engine object
            db_id: Optional database identifier

        Returns:
            Schema object
        """
        from sqlalchemy import inspect

        if db_id is None:
            db_id = str(engine.url.database)

        inspector = inspect(engine)
        table_names = inspector.get_table_names()

        tables: List[Table] = []
        foreign_keys: List[ForeignKey] = []

        for table_name in table_names:
            columns_data = inspector.get_columns(table_name)
            pk_constraint = inspector.get_pk_constraint(table_name)
            pk_columns = set(pk_constraint.get('constrained_columns', []))

            columns: List[Column] = []
            primary_keys: List[str] = []

            for col_data in columns_data:
                col_name = col_data['name']
                col_type = str(col_data['type'])
                is_nullable = col_data.get('nullable', True)
                is_pk = col_name in pk_columns

                columns.append(Column(
                    name=col_name,
                    type=col_type,
                    primary_key=is_pk,
                    nullable=is_nullable
                ))

                if is_pk:
                    primary_keys.append(col_name)

            tables.append(Table(
                name=table_name,
                columns=columns,
                primary_keys=primary_keys
            ))

            # Get foreign keys
            fk_data = inspector.get_foreign_keys(table_name)
            for fk in fk_data:
                dst_table = fk['referred_table']
                src_cols = fk['constrained_columns']
                dst_cols = fk['referred_columns']

                # Add one FK per column pair
                for src_col, dst_col in zip(src_cols, dst_cols):
                    foreign_keys.append(ForeignKey(
                        src_table=table_name,
                        src_column=src_col,
                        dst_table=dst_table,
                        dst_column=dst_col
                    ))

        return cls(db_id=db_id, tables=tables, foreign_keys=foreign_keys)
