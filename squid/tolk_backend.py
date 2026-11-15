"""A tolk question as SQL.

tolk (https://github.com/richarah/tolk) reads English into logical forms. This module turns two of them, `Ask` and `Describe`, into SQL
over a schema, built with sqlglot. The mapping from predicates to tables and columns is SQUID's own schema linking (`match_table`).
Anything else tolk can produce (a statement, a rule, a claim, a comparison, a question over every thing) is refused, because a database
holds rows and has no rule to add them to.

A predicate is a noun when its lemma is a table, and a relation when its lemma is a table with two or more foreign keys, whose first foreign
key (in column order) is its subject. Which table a thing is in comes from a noun atom about it, or from the column of a relation it
fills. A name is compared in lower case with the `name` column, as tolk keeps names in lower case. Where a role could be filled by more
than one column the query is the union over each, so that "Does Kim own Rex?" finds Rex whether he is a dog or a cat."""

from __future__ import annotations

import re
from itertools import product
from typing import Optional

import tolk
from sqlglot import exp, select

from squid.linker import match_table
from squid.schema import Schema

LEXICAL = re.compile(r"_([^_]+)_([nva])_.*")
NAME = "name"


def is_relation(schema: Schema, table: str) -> bool:
    return len(foreign_keys(schema, table)) >= 2


def foreign_keys(schema: Schema, table: str) -> list[tuple[str, str]]:
    """(column, referenced table) of each foreign key, in the order the columns are declared."""
    refs = {fk.src_column: fk.dst_table for fk in schema.foreign_keys if fk.src_table == table}
    return [(c.name, refs[c.name]) for c in schema.get_table(table).columns if c.name in refs]


def predicates(schema: Schema) -> frozenset[str]:
    """The predicates the schema can express, for `tolk.read(text, known_predicates)`: a noun per plain table, a verb per relation."""
    out = set()
    for t in schema.tables:
        lemma = re.sub(r"s$", "", t.name) if is_relation(schema, t.name) else t.name
        out.add(f"_{lemma}_{'v' if is_relation(schema, t.name) else 'n'}_1")
    return frozenset(out)


def to_sql(x, schema: Schema, dialect: str = "sqlite") -> str | tolk.Refusal:
    """SQL for a tolk Ask or Describe; a tolk Refusal for anything else, or for a question the schema cannot express."""
    if isinstance(x, tolk.Refusal):
        return x
    if isinstance(x, tolk.Describe):
        return _describe(x, schema, dialect)
    if not isinstance(x, tolk.Ask):
        return tolk.Refusal("NOT_A_QUESTION", type(x).__name__)
    if x.alternatives or x.claims or any(t == "past" for _, t in x.tenses):
        return tolk.Refusal("UNSUPPORTED_QUESTION", "an or, a claim or a past tense has no form in the schema")
    plans = _plans(x, schema)
    if isinstance(plans, tolk.Refusal):
        return plans
    queries = [_query(x, p, schema) for p in plans]
    if any(isinstance(q, tolk.Refusal) for q in queries):
        return next(q for q in queries if isinstance(q, tolk.Refusal))
    whole = queries[0]
    for q in queries[1:]:
        whole = exp.union(whole, q)
    return whole.sql(dialect=dialect)


class Plan:
    """One way of filling every role: the table of each thing, and the column each relation atom's things sit in."""

    def __init__(self, types: dict, columns: dict) -> None:
        self.types, self.columns = types, columns


def _thing(t) -> Optional[str]:
    return t.key if isinstance(t, tolk.Var) else t.id if isinstance(t, tolk.Const) else None


def _lemma(pred: str) -> Optional[tuple[str, str]]:
    m = LEXICAL.fullmatch(pred)
    return (m.group(1), m.group(2)) if m else None


def _table(pred: str, schema: Schema) -> Optional[str]:
    lex = _lemma(pred)
    found = match_table(lex[0], schema) if lex else None
    return found[0] if found else None


def _plans(x, schema: Schema) -> list[Plan] | tolk.Refusal:
    known: dict[str, str] = {}
    relations = []
    for i, a in enumerate(x.body):
        table, lex = _table(a.pred, schema), _lemma(a.pred)
        if table is None or lex is None or lex[1] == "a":
            return tolk.Refusal("UNKNOWN_PREDICATE", f"{a.pred} is no table of the schema")
        if lex[1] == "n":
            if not a.positive:
                return tolk.Refusal("UNSUPPORTED_QUESTION", "a negated noun")
            known[_thing(a.args[0])] = table
        elif not is_relation(schema, table) or len(a.args) != 3:
            return tolk.Refusal("UNSUPPORTED_QUESTION", f"{a.pred} needs a relation of two things")
        else:
            relations.append((i, table, _thing(a.args[1]), _thing(a.args[2])))
    options = []
    for i, table, subject, obj in relations:
        keys = foreign_keys(schema, table)
        first = keys[0]
        rest = [k for k in keys[1:] if known.get(obj) in (None, k[1])]
        options.append([(i, table, first, k) for k in rest])
    plans = []
    for combo in product(*options) if options else [()]:
        types = dict(known)
        ok = True
        for (i, table, subject_key, object_key), (_, _, s, o) in zip(combo, relations):
            for thing, (_, ref) in ((s, subject_key), (o, object_key)):
                if types.setdefault(thing, ref) != ref:
                    ok = False
        if ok:
            plans.append(Plan(types, {i: (sk[0], ok_[0]) for (i, _, sk, ok_) in combo}))
    return plans or tolk.Refusal("UNSUPPORTED_QUESTION", "no way to fill the roles from the schema")


def _alias(t) -> str:
    return ("v_" if isinstance(t, tolk.Var) else "c_") + re.sub(r"\W", "_", _thing(t))


def _query(x, plan: Plan, schema: Schema):
    things = {_thing(t): t for a in x.body for t in a.args[(1 if _lemma(a.pred)[1] == "v" else 0):]}
    froms = {k: exp.Table(this=exp.to_identifier(plan.types[k]), alias=exp.to_identifier(_alias(t))) for k, t in things.items() if k in plan.types}
    conds = []
    for k, t in things.items():
        if isinstance(t, tolk.Const) and k in plan.types:
            conds.append(exp.EQ(this=exp.Lower(this=exp.column(NAME, _alias(t))), expression=exp.Literal.string(t.id)))
    extra, negatives = [], []
    for i, a in enumerate(x.body):
        if _lemma(a.pred)[1] != "v":
            continue
        table, (subject_col, object_col) = _table(a.pred, schema), plan.columns[i]
        subject, obj = a.args[1], a.args[2]
        on = [exp.EQ(this=exp.column(subject_col, f"r{i}"), expression=exp.column("id", _alias(subject))),
              exp.EQ(this=exp.column(object_col, f"r{i}"), expression=exp.column("id", _alias(obj)))]
        rel = exp.Table(this=exp.to_identifier(table), alias=exp.to_identifier(f"r{i}"))
        if a.positive:
            extra.append(rel)
            conds += on
        else:
            inner = select("1").from_(rel).where(exp.and_(*on))
            negatives.append(exp.Not(this=exp.Exists(this=inner)))
    sources = list(froms.values()) + extra
    if not sources:
        return tolk.Refusal("UNSUPPORTED_QUESTION", "nothing in the question is a table")
    where = exp.and_(*(conds + negatives)) if conds + negatives else None

    def assemble(projection):
        q = select(projection).from_(sources[0])
        for source in sources[1:]:
            q = q.join(source, join_type="cross")
        return q.where(where) if where is not None else q

    if x.count is not None:
        counted = assemble(exp.Count(this=exp.Distinct(expressions=[exp.column("id", _alias(things[_thing(x.count)]))])))
        if x.atleast:
            return select("1").where(exp.GTE(this=counted.subquery(), expression=exp.Literal.number(x.atleast)))
        return counted
    if x.wanted:
        return assemble(exp.column(NAME, _alias(things[_thing(x.wanted[0])]))).distinct()
    return assemble("1").limit(1)


def _describe(x, schema: Schema, dialect: str) -> str:
    """What the rows say about a name: the tables it is in, and the relations it is the first thing of."""
    name = exp.Literal.string(x.entity.id)
    parts = []
    for t in schema.tables:
        if t.get_column(NAME) and not is_relation(schema, t.name):
            parts.append(select(exp.Literal.string(t.name).as_("kind"), exp.column(NAME)).from_(t.name)
                         .where(exp.EQ(this=exp.Lower(this=exp.column(NAME)), expression=name)))
    whole = parts[0]
    for p in parts[1:]:
        whole = exp.union(whole, p, distinct=False)
    return whole.sql(dialect=dialect)
