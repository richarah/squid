"""
DMRS to SQL compiler.

The core of SQUID: walks a DMRS graph and emits SQL via sqlglot's builder API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Union

import sqlglot
from delphin import dmrs

from squid import rules
from squid.linker import SchemaLink, get_linked_tables
from squid.schema import Schema


class SquidCompileError(Exception):
    """Raised when compilation fails."""
    pass


@dataclass(slots=True)
class AggCall:
    """Represents an aggregation call (COUNT, MAX, MIN, AVG, SUM)."""

    func: str  # "COUNT", "MAX", "MIN", "AVG", "SUM"
    column: Optional[str] = None  # Column name, or None for COUNT(*)
    distinct: bool = False


@dataclass(slots=True)
class Condition:
    """Represents a WHERE or HAVING condition."""

    left: str  # Column name or expression
    operator: str  # "=", ">", "<", ">=", "<=", "!=", "LIKE", "IN", etc.
    right: Union[str, int, float, List]  # Value or list of values


@dataclass(slots=True)
class JoinClause:
    """Represents a JOIN between two tables."""

    left_table: str
    right_table: str
    left_column: str
    right_column: str
    join_type: str = "INNER"  # "INNER", "LEFT", "RIGHT", "OUTER"


@dataclass(slots=True)
class OrderClause:
    """Represents an ORDER BY clause."""

    column: str
    direction: str = "ASC"  # "ASC" or "DESC"


@dataclass(slots=True)
class SetOp:
    """Represents a set operation (UNION, INTERSECT, EXCEPT)."""

    operation: str  # "UNION", "INTERSECT", "EXCEPT"
    subquery: QueryPlan


@dataclass(slots=True)
class QueryPlan:
    """
    Intermediate representation of a SQL query.

    This is built by walking the DMRS graph, then converted to SQL via sqlglot.
    """

    select: List[Union[str, AggCall]] = field(default_factory=list)
    tables: List[str] = field(default_factory=list)
    joins: List[JoinClause] = field(default_factory=list)
    conditions: List[Condition] = field(default_factory=list)
    group_by: List[str] = field(default_factory=list)
    having: List[Condition] = field(default_factory=list)
    order_by: List[OrderClause] = field(default_factory=list)
    limit: Optional[int] = None
    distinct: bool = False
    set_ops: List[SetOp] = field(default_factory=list)
    subqueries: List[QueryPlan] = field(default_factory=list)


class DMRSCompiler:
    """
    Compiles a linked DMRS to SQL.

    Algorithm:
    1. Find the top node (dmrs.top) - this is the main clause
    2. Identify the query target: follow from top to find which_q or similar
    3. Walk the DMRS nodes, classifying each by rules
    4. Build a QueryPlan (intermediate representation)
    5. Convert QueryPlan to sqlglot expression tree
    6. Return .sql(dialect)
    """

    def __init__(self, schema: Schema, links: Dict[str, SchemaLink]):
        """
        Initialize compiler.

        Args:
            schema: Database schema
            links: Schema links from linker.link()
        """
        self.schema = schema
        self.links = links

    def compile(self, dmrs_obj: dmrs.Dmrs, dialect: str = "sqlite") -> str:
        """
        Compile a linked DMRS to SQL.

        Args:
            dmrs_obj: DMRS parse
            dialect: SQL dialect for sqlglot

        Returns:
            SQL query string

        Raises:
            SquidCompileError: If compilation fails
        """
        try:
            # Build query plan from DMRS
            plan = self._build_query_plan(dmrs_obj)

            # Convert plan to SQL
            sql = self._plan_to_sql(plan, dialect)

            return sql

        except Exception as e:
            raise SquidCompileError(f"Compilation failed: {e}")

    def _build_query_plan(self, dmrs_obj: dmrs.Dmrs) -> QueryPlan:
        """Build a QueryPlan by walking the DMRS graph."""
        plan = QueryPlan()

        # Find all tables referenced in the DMRS
        plan.tables = get_linked_tables(self.links)

        if not plan.tables:
            raise SquidCompileError("No tables found in DMRS")

        # Walk the DMRS graph starting from the top node
        visited: Set[int] = set()
        if dmrs_obj.top is not None:
            self._walk(dmrs_obj.top, dmrs_obj, plan, visited)

        # If no SELECT columns were identified, default to COUNT(*)
        if not plan.select:
            plan.select.append(AggCall(func="COUNT"))

        # Infer JOINs if multiple tables are referenced
        if len(plan.tables) > 1:
            self._resolve_joins(plan)

        # Infer GROUP BY if needed
        if any(isinstance(s, AggCall) for s in plan.select):
            self._resolve_group_by(plan)

        return plan

    def _walk(
        self,
        node_id: int,
        dmrs_obj: dmrs.Dmrs,
        plan: QueryPlan,
        visited: Set[int]
    ) -> None:
        """Recursive DMRS graph walker."""
        if node_id in visited:
            return
        visited.add(node_id)

        # Get the node
        node = dmrs_obj[node_id]
        pred = str(node.predicate)
        node_id_str = str(node_id)

        # Check if this predicate has a structural rule
        rule = rules.get_rule(pred)

        # Handle quantifiers
        if rules.is_quantifier(pred):
            self._resolve_quantifier(node, dmrs_obj, plan, visited)

        # Handle comparisons
        elif rules.is_comparison(pred):
            self._resolve_comparison(node, dmrs_obj, plan, visited)

        # Handle aggregations
        elif rules.is_aggregation(pred):
            self._resolve_aggregation(node, dmrs_obj, plan, visited)

        # Handle connectives
        elif rules.is_connective(pred):
            self._resolve_connective(node, dmrs_obj, plan, visited)

        # Handle content predicates (table/column references)
        elif node_id_str in self.links:
            link = self.links[node_id_str]
            if link.element_type == 'column':
                # Add column to SELECT if not already there
                col_ref = f"{link.table}.{link.column}"
                if col_ref not in plan.select:
                    plan.select.append(col_ref)

        # Walk outgoing links
        for link in dmrs_obj.links:
            if link.start == node_id:
                self._walk(link.end, dmrs_obj, plan, visited)

    def _resolve_quantifier(
        self,
        node,
        dmrs_obj: dmrs.Dmrs,
        plan: QueryPlan,
        visited: Set[int]
    ) -> None:
        """Handle quantifier nodes."""
        pred = str(node.predicate)
        rule = rules.QUANTIFIER_RULES.get(pred)

        if not rule:
            return

        sql_op = rule['sql_op']

        if sql_op == 'SELECT':
            # which_q: this is the query target
            # Follow RSTR link to find what we're selecting
            for link in dmrs_obj.links:
                if link.start == node.id and link.post == 'RSTR':
                    self._walk(link.end, dmrs_obj, plan, visited)

    def _resolve_comparison(
        self,
        node,
        dmrs_obj: dmrs.Dmrs,
        plan: QueryPlan,
        visited: Set[int]
    ) -> None:
        """Handle comparison nodes (>, <, =, etc.)."""
        pred = str(node.predicate)
        rule = rules.COMPARISON_RULES.get(pred)

        if not rule:
            return

        sql_op = rule['sql_op']

        # Find ARG1 and ARG2
        arg1_node = None
        arg2_node = None

        for link in dmrs_obj.links:
            if link.start == node.id:
                if link.post == 'ARG1':
                    arg1_node = dmrs_obj[link.end]
                elif link.post == 'ARG2':
                    arg2_node = dmrs_obj[link.end]

        if not arg1_node or not arg2_node:
            return

        # Get column from ARG1 (should be linked to schema)
        arg1_link = self.links.get(str(arg1_node.id))
        if not arg1_link or arg1_link.element_type != 'column':
            return

        column = f"{arg1_link.table}.{arg1_link.column}"

        # Get value from ARG2 (could be a CARG or another column)
        arg2_link = self.links.get(str(arg2_node.id))
        if arg2_link and arg2_link.element_type == 'value':
            value = arg2_link.value
        elif hasattr(arg2_node, 'carg') and arg2_node.carg:
            value = arg2_node.carg
        else:
            # Could be another column or expression
            return

        # Map SQL operation to operator
        operator_map = {
            'EQUAL': '=',
            'GREATER': '>',
            'LESS': '<',
            'COMPARE': '>',  # Default, may need to determine from context
        }
        operator = operator_map.get(sql_op, '=')

        # Add condition
        plan.conditions.append(Condition(left=column, operator=operator, right=value))

    def _resolve_aggregation(
        self,
        node,
        dmrs_obj: dmrs.Dmrs,
        plan: QueryPlan,
        visited: Set[int]
    ) -> None:
        """Handle aggregation nodes (COUNT, MAX, MIN, AVG, SUM)."""
        pred = str(node.predicate)
        rule = rules.AGGREGATION_RULES.get(pred)

        if not rule:
            return

        sql_op = rule['sql_op']

        # Map SQL operation to function name
        func_map = {
            'COUNT': 'COUNT',
            'MAX': 'MAX',
            'MAX_OR_SUPERLATIVE': 'MAX',
            'MIN': 'MIN',
            'MIN_OR_SUPERLATIVE': 'MIN',
            'AVG': 'AVG',
            'SUM': 'SUM',
        }
        func = func_map.get(sql_op, 'COUNT')

        # Find the ARG1 to determine what to aggregate
        arg1_node = None
        for link in dmrs_obj.links:
            if link.start == node.id and link.post == 'ARG1':
                arg1_node = dmrs_obj[link.end]
                break

        if arg1_node:
            arg1_link = self.links.get(str(arg1_node.id))
            if arg1_link and arg1_link.element_type == 'column':
                column = arg1_link.column
            else:
                column = None
        else:
            column = None

        # Add aggregation to SELECT
        plan.select.append(AggCall(func=func, column=column))

    def _resolve_connective(
        self,
        node,
        dmrs_obj: dmrs.Dmrs,
        plan: QueryPlan,
        visited: Set[int]
    ) -> None:
        """Handle logical connectives (AND, OR, NOT)."""
        pred = str(node.predicate)
        rule = rules.CONNECTIVE_RULES.get(pred)

        if not rule:
            return

        # For AND/OR, we just walk both arguments and combine conditions
        # The actual combination happens in _plan_to_sql
        for link in dmrs_obj.links:
            if link.start == node.id:
                self._walk(link.end, dmrs_obj, plan, visited)

    def _resolve_joins(self, plan: QueryPlan) -> None:
        """
        Infer JOINs from foreign key graph.

        When the query references multiple tables, find the shortest
        path in the FK graph and add JOIN clauses.
        """
        if len(plan.tables) < 2:
            return

        # For each pair of tables, find join path
        # This is a simplified implementation - for complex queries,
        # we'd need to analyze the DMRS structure more carefully
        for i in range(len(plan.tables) - 1):
            table1 = plan.tables[i]
            table2 = plan.tables[i + 1]

            # Find join path
            path = self.schema.find_join_path(table1, table2)
            if not path:
                continue

            # Add JOIN for each hop in the path
            for j in range(len(path) - 1):
                left_table = path[j]
                right_table = path[j + 1]

                # Find the FK connecting these tables
                fk = None
                for foreign_key in self.schema.foreign_keys:
                    if (foreign_key.src_table == left_table and
                        foreign_key.dst_table == right_table):
                        fk = foreign_key
                        break
                    elif (foreign_key.src_table == right_table and
                          foreign_key.dst_table == left_table):
                        # Reverse direction
                        fk = foreign_key
                        left_table, right_table = right_table, left_table
                        break

                if fk:
                    plan.joins.append(JoinClause(
                        left_table=fk.src_table,
                        right_table=fk.dst_table,
                        left_column=fk.src_column,
                        right_column=fk.dst_column
                    ))

    def _resolve_group_by(self, plan: QueryPlan) -> None:
        """
        Infer GROUP BY from the query structure.

        If there's an aggregation over variable X and a non-aggregated
        variable Y in SELECT, then GROUP BY Y.
        """
        # Find all non-aggregated columns in SELECT
        non_agg_columns: List[str] = []
        for item in plan.select:
            if isinstance(item, str):
                non_agg_columns.append(item)

        # If we have both aggregated and non-aggregated columns, GROUP BY the latter
        has_agg = any(isinstance(s, AggCall) for s in plan.select)
        if has_agg and non_agg_columns:
            plan.group_by = non_agg_columns

    def _plan_to_sql(self, plan: QueryPlan, dialect: str) -> str:
        """
        Convert QueryPlan to SQL string via sqlglot builder API.

        Args:
            plan: Query plan
            dialect: SQL dialect

        Returns:
            SQL query string
        """
        # Build SELECT clause
        select_exprs: List[str] = []
        for item in plan.select:
            if isinstance(item, AggCall):
                if item.column:
                    expr = f"{item.func}({item.column})"
                else:
                    expr = f"{item.func}(*)"
                select_exprs.append(expr)
            else:
                select_exprs.append(item)

        # If no select items, default to *
        if not select_exprs:
            select_exprs = ["*"]

        # Start building query with sqlglot
        query = sqlglot.select(*select_exprs)

        # Add FROM clause
        if plan.tables:
            query = query.from_(plan.tables[0])

        # Add JOINs
        for join in plan.joins:
            on_condition = f"{join.left_table}.{join.left_column} = {join.right_table}.{join.right_column}"
            query = query.join(
                join.right_table,
                on=on_condition,
                join_type=join.join_type
            )

        # Add WHERE conditions
        for condition in plan.conditions:
            if condition.operator == '=':
                query = query.where(f"{condition.left} = {self._quote_value(condition.right)}")
            elif condition.operator == '>':
                query = query.where(f"{condition.left} > {self._quote_value(condition.right)}")
            elif condition.operator == '<':
                query = query.where(f"{condition.left} < {self._quote_value(condition.right)}")
            elif condition.operator == '>=':
                query = query.where(f"{condition.left} >= {self._quote_value(condition.right)}")
            elif condition.operator == '<=':
                query = query.where(f"{condition.left} <= {self._quote_value(condition.right)}")
            elif condition.operator == '!=':
                query = query.where(f"{condition.left} != {self._quote_value(condition.right)}")

        # Add GROUP BY
        if plan.group_by:
            query = query.group_by(*plan.group_by)

        # Add HAVING
        for condition in plan.having:
            # Similar to WHERE
            pass  # TODO: Implement HAVING

        # Add ORDER BY
        for order in plan.order_by:
            if order.direction == 'DESC':
                query = query.order_by(order.column, desc=True)
            else:
                query = query.order_by(order.column)

        # Add LIMIT
        if plan.limit:
            query = query.limit(plan.limit)

        # Add DISTINCT
        if plan.distinct:
            query = query.distinct()

        # Generate SQL
        return query.sql(dialect=dialect)

    def _quote_value(self, value: Union[str, int, float]) -> str:
        """Quote a value appropriately for SQL."""
        if isinstance(value, str):
            return f"'{value}'"
        else:
            return str(value)
