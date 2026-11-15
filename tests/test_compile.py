"""squid.compile goes through tolk. The schema has two invented table names, which the grammar does not know: they reach the parser as
tagged input (tolk.read's vocabulary), not through an option the parser lacks."""

import sqlite3

import pytest

import squid
from squid.tolk_backend import vocabulary

DDL = """
CREATE TABLE zorp(id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE wug(id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE tends(zorp_id INTEGER REFERENCES zorp(id), wug_id INTEGER REFERENCES wug(id));
INSERT INTO zorp VALUES (1,'Pip'),(2,'Quin');
INSERT INTO wug VALUES (1,'Ada'),(2,'Bo'),(3,'Cy');
INSERT INTO tends VALUES (1,1),(1,2),(2,3);
"""


@pytest.fixture()
def database(tmp_path):
    path = str(tmp_path / "zw.db")
    db = sqlite3.connect(path)
    db.executescript(DDL)
    db.commit()
    return db, squid.Schema.from_sqlite(path)


def test_the_vocabulary_is_the_schemas_table_names_with_their_classes(database) -> None:
    _, schema = database
    assert vocabulary(schema) == {"zorp": "n", "wug": "n", "tend": "v"}


def test_a_question_over_two_invented_tables_runs_and_answers(database) -> None:
    db, schema = database
    sql = squid.compile("Which wugs does Pip tend?", schema)
    assert sorted(r[0] for r in db.execute(sql)) == ["Ada", "Bo"]


def test_a_count_over_them(database) -> None:
    db, schema = database
    assert db.execute(squid.compile("How many wugs does Pip tend?", schema)).fetchall() == [(2,)]


def test_a_yes_or_no_question(database) -> None:
    db, schema = database
    assert db.execute(squid.compile("Does Pip tend Ada?", schema)).fetchall()
    assert not db.execute(squid.compile("Does Quin tend Ada?", schema)).fetchall()


def test_a_sentence_that_is_not_a_question_raises_a_compile_error_with_the_reason(database) -> None:
    _, schema = database
    with pytest.raises(squid.SquidCompileError, match="NOT_A_QUESTION"):
        squid.compile("Pip tends Ada.", schema)


def test_the_old_pipeline_is_called_from_nowhere() -> None:
    import pathlib
    import re
    for path in list(pathlib.Path(squid.__file__).parent.glob("*.py")) + list(pathlib.Path(__file__).parent.glob("*.py")):
        if path.name not in ("legacy.py", "test_compile.py"):
            assert not re.search(r"(import|from)\s+squid(\.legacy|\s+import\s+.*legacy)|from \.legacy|import legacy", path.read_text()), path
