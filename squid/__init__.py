"""
SQUID - SQL Unique Interpretation through Deep Parsing

English questions to SQL over a database schema. The sentence is read by tolk (ACE and the English Resource Grammar), and the schema
decides which tables and columns its words mean. The first pipeline is in `squid/legacy.py` and is not used.
"""

from __future__ import annotations

import tolk

from squid.compiler import SquidCompileError
from squid.parser import SquidParseError
from squid.schema import Column, ForeignKey, Schema, Table
from squid.tolk_backend import predicates, to_sql, vocabulary

__version__ = "0.1.0"

__all__ = [
    "compile",
    "Schema",
    "Table",
    "Column",
    "ForeignKey",
    "SquidParseError",
    "SquidCompileError",
]


def compile(question: str, schema: Schema, dialect: str = "sqlite") -> str:
    """Compile an English question to SQL.

    tolk reads the question, with the schema's table names given to the parser as tagged input and its tables as the predicates that
    steer the choice between readings; the schema then turns the logical form into SQL.

    Raises:
        SquidCompileError: the question is not one the schema can answer (tolk's refusal code and reason are in the message).

    Example:
        >>> schema = Schema.from_sqlite("my_database.db")
        >>> compile("How many customers does Kim own?", schema)
    """
    x = tolk.read(question, predicates(schema), vocabulary(schema))
    sql = to_sql(x, schema, dialect)
    if isinstance(sql, tolk.Refusal):
        raise SquidCompileError(f"{sql.code}: {sql.detail}")
    return sql
