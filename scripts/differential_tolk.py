"""Differential test of the tolk back end: the same facts as rows in SQLite and as English sentences told to tolk, the same questions
asked of both, every disagreement reported. Run with tolk on the path: PYTHONPATH=/path/to/tolk:. python scripts/differential_tolk.py"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tolk  # noqa: E402

import squid  # noqa: E402
from squid.tolk_backend import predicates, to_sql  # noqa: E402

DDL = """
CREATE TABLE person(id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE dog(id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE cat(id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE owns(person_id INTEGER REFERENCES person(id), dog_id INTEGER REFERENCES dog(id), cat_id INTEGER REFERENCES cat(id));
CREATE TABLE likes(person_id INTEGER REFERENCES person(id), dog_id INTEGER REFERENCES dog(id), cat_id INTEGER REFERENCES cat(id));
INSERT INTO person VALUES (1,'Kim'),(2,'Sandy'),(3,'Lee'),(4,'Bo');
INSERT INTO dog VALUES (1,'Rex'),(2,'Fido'),(3,'Spot');
INSERT INTO cat VALUES (1,'Tom'),(2,'Mia');
INSERT INTO owns VALUES (1,1,NULL),(1,NULL,1),(2,2,NULL),(3,NULL,2),(3,3,NULL);
INSERT INTO likes VALUES (1,2,NULL),(2,NULL,1),(3,1,NULL),(4,NULL,2),(4,3,NULL);
"""
QUESTIONS = [
    "How many dogs does Kim own?", "How many cats does Kim own?", "How many dogs does Lee own?", "How many cats does Sandy own?",
    "Who owns a dog?", "Who owns a cat?", "Who likes a dog?", "Which dogs does Kim own?", "Which cats does Bo like?",
    "Does Kim own Rex?", "Does Kim own Fido?", "Does Lee like Rex?", "Does Kim not own Rex?", "Does Kim not own Fido?",
    "Which dogs does Kim not own?",
]
VERB = {"owns": "owns", "likes": "likes"}


def sentences(db: sqlite3.Connection) -> list[str]:
    """English for each row: a name and its table, then each row of a relation table."""
    out = [f"{n} is a {t}." for t in ("person", "dog", "cat") for (n,) in db.execute(f"SELECT name FROM {t} ORDER BY id")]
    for rel, verb in VERB.items():
        for p, d, c in db.execute(f"SELECT p.name, d.name, c.name FROM {rel} r JOIN person p ON p.id = r.person_id "
                                  f"LEFT JOIN dog d ON d.id = r.dog_id LEFT JOIN cat c ON c.id = r.cat_id"):
            out.append(f"{p} {verb} {d or c}.")
    return out


def tolk_side(mind, question: str):
    r = mind.ask(question)
    a = r.answer
    if a is None:
        return ("refused", r.outcome)
    if a.count is not None:
        return ("count", a.count)
    if a.value == "Yes" and a.solutions:
        return ("set", {s[0].lower() for s in a.solutions})
    return ("value", a.value)


def sql_side(db, x, schema):
    sql = to_sql(x, schema)
    if isinstance(sql, tolk.Refusal):
        return ("refused", sql.code), sql
    rows = db.execute(sql).fetchall()
    return rows, sql


def compare(question, mind, db, schema, known):
    t = tolk_side(mind, question)
    x = tolk.read(question, known)
    rows, sql = sql_side(db, x, schema)
    if t[0] == "count":
        ok = rows == [(t[1],)]
    elif t[0] == "set":
        ok = {r[0].lower() for r in rows} == t[1]
    elif t[0] == "value" and t[1] == "Yes":
        ok = bool(rows)
    elif t[0] == "value" and t[1] == "No":
        ok = not rows
    else:
        ok = False
    return ok, t, rows, sql


def main() -> int:
    db = sqlite3.connect(":memory:")
    db.executescript(DDL)
    schema = squid.Schema.from_sqlite(":memory:") if False else _schema(db)
    mind = tolk.Mind()
    for s in sentences(db):
        assert mind.tell(s).outcome.startswith("stored"), s
    known = predicates(schema)
    wrong = 0
    for q in QUESTIONS:
        ok, t, rows, sql = compare(q, mind, db, schema, known)
        wrong += not ok
        print(f"{'agree   ' if ok else 'DISAGREE'} {q}\n   tolk: {t}\n   sql:  {rows}\n   {sql}")
    print(f"{len(QUESTIONS)} questions, {wrong} disagreements")
    return 0


def _schema(db):
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        disk = sqlite3.connect(f.name)
        db.backup(disk)
        disk.commit()
        return squid.Schema.from_sqlite(f.name)


if __name__ == "__main__":
    sys.exit(main())
