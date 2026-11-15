"""The tolk back end (squid/tolk_backend.py). Needs tolk on the path (PYTHONPATH=/path/to/tolk); without it these tests are not collected."""

import sqlite3
import sys
from pathlib import Path

import pytest

tolk = pytest.importorskip("tolk")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import differential_tolk as d  # noqa: E402

import squid  # noqa: E402
from squid.tolk_backend import predicates, to_sql  # noqa: E402


@pytest.fixture(scope="module")
def world():
    db = sqlite3.connect(":memory:")
    db.executescript(d.DDL)
    schema = d._schema(db)
    mind = tolk.Mind(closed_world=True)
    for s in d.sentences(db):
        mind.tell(s)
    return db, schema, mind, predicates(schema)


def test_the_predicates_the_schema_expresses(world) -> None:
    assert world[3] == {"_person_n_1", "_dog_n_1", "_cat_n_1", "_own_v_1", "_like_v_1"}


@pytest.mark.parametrize("text", ["Kim owns a dog.", "Every dog barks.", "Does Kim believe that Rex barks?", "Who is the tallest?", "Is every dog a pet?"])
def test_what_is_not_a_question_the_schema_can_answer_is_refused(world, text: str) -> None:
    out = to_sql(tolk.read(text, world[3]), world[1])
    assert isinstance(out, tolk.Refusal), text


def test_a_predicate_the_schema_lacks_is_refused(world) -> None:
    out = to_sql(tolk.read("Does Kim fly?", world[3]), world[1])
    assert isinstance(out, tolk.Refusal) and out.code == "UNKNOWN_PREDICATE"


@pytest.mark.parametrize("question", d.QUESTIONS)
def test_the_rows_equal_tolks_answer(world, question: str) -> None:
    db, schema, mind, known = world
    ok, t, rows, sql = d.compare(question, mind, db, schema, known)
    assert ok, (t, rows, sql)


def test_all_fifteen_agree_with_the_world_closed(world) -> None:
    db, schema, mind, known = world
    assert len(d.QUESTIONS) == 15
    assert [q for q in d.QUESTIONS if not d.compare(q, mind, db, schema, known)[0]] == []
