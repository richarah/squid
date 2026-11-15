"""A value that is in the database is read as that value. The grammar expands some abbreviations ("Ga" is Georgia, "Mo" Missouri); a
query that compared the expansion would return nothing with no sign why. Either the value is what is compared, or the question is refused."""

import sqlite3

import pytest

import squid

DDL = """
CREATE TABLE person(id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE state(id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE visits(person_id INTEGER REFERENCES person(id), state_id INTEGER REFERENCES state(id));
INSERT INTO person VALUES (1,'Kim'),(2,'Lee');
INSERT INTO state VALUES (1,'Ga'),(2,'Ca'),(3,'Mo'),(4,'Fla'),(5,'Tex'),(6,'Ohio'),(7,'New York'),(8,'Rose');
INSERT INTO visits VALUES (1,1),(1,2),(1,3),(1,4),(1,5),(2,6),(2,7),(2,8);
"""


@pytest.fixture()
def database(tmp_path):
    path = str(tmp_path / "v.db")
    db = sqlite3.connect(path)
    db.executescript(DDL)
    db.commit()
    return db, squid.Schema.from_sqlite(path)


@pytest.mark.parametrize("value", ["Ga", "Ca", "Mo", "Fla", "Tex"])
def test_an_abbreviation_in_a_row_is_that_value_not_its_expansion(database, value: str) -> None:
    db, schema = database
    assert db.execute(squid.compile(f"Does Kim visit {value}?", schema)).fetchall(), value
    assert db.execute(squid.compile(f"Who visits {value}?", schema)).fetchall() == [("Kim",)], value
    assert not db.execute(squid.compile(f"Does Lee visit {value}?", schema)).fetchall(), value


@pytest.mark.parametrize("value", ["New York", "Rose", "Ohio"])
def test_other_values_the_grammar_reads_as_something_else_still_match(database, value: str) -> None:
    db, schema = database
    assert db.execute(squid.compile(f"Does Lee visit {value}?", schema)).fetchall(), value


def test_the_values_are_part_of_the_schema(database) -> None:
    _, schema = database
    assert "Ga" in schema.values["state"] and "Kim" in schema.values["person"]


def test_a_name_the_grammar_expanded_that_is_not_a_value_is_refused_not_compared(database) -> None:
    _, schema = database
    # "Wy" is in no row, and the grammar would compare it as Wyoming: the question says Wy, so what is compared must be Wy or nothing.
    with pytest.raises(squid.SquidCompileError, match="NAME_NOT_AS_WRITTEN"):
        squid.compile("Does Kim visit Wy?", schema)


def test_a_value_written_in_another_case_is_refused_as_ambiguous(database) -> None:
    _, schema = database
    with pytest.raises(squid.SquidCompileError, match="AMBIGUOUS_VALUE"):
        squid.compile("Does Kim visit ga?", schema)


def test_a_schema_without_rows_is_read_as_before(database) -> None:
    _, schema = database
    bare = squid.Schema(db_id="bare", tables=schema.tables, foreign_keys=schema.foreign_keys)
    assert bare.values == {}
    assert "kim" in squid.compile("Does Kim visit Ohio?", bare).lower()


def test_no_question_about_a_value_returns_rows_for_a_different_value(database) -> None:
    db, schema = database
    # Georgia is not a row; Ga is. Asking about Georgia must not find Ga's row, and must not find any other.
    assert not db.execute(squid.compile("Does Kim visit Georgia?", schema)).fetchall()
