"""Tests for squid.lexicon module."""

import pytest

from squid.lexicon import (
    generate_tdl,
    make_tdl_entry,
    sanitize_for_tdl,
    should_include_word,
    split_identifier,
)


def test_split_identifier():
    """Test identifier splitting."""
    assert split_identifier("student_id") == ["student", "id"]
    assert split_identifier("StudentName") == ["student", "name"]
    assert split_identifier("order_items") == ["order", "items"]
    assert split_identifier("firstName") == ["first", "name"]


def test_sanitize_for_tdl():
    """Test TDL sanitization."""
    assert sanitize_for_tdl("student") == "student"
    assert sanitize_for_tdl("Student") == "student"
    assert sanitize_for_tdl("student-name") == "student-name"
    assert sanitize_for_tdl("student_id") == "student_id"
    assert sanitize_for_tdl("student@email") == "student_email"


def test_should_include_word():
    """Test word inclusion logic."""
    assert should_include_word("student")
    assert should_include_word("singer")
    assert should_include_word("concert")

    # Too short
    assert not should_include_word("id")
    assert not should_include_word("a")

    # Common words (in KNOWN_WORDS)
    assert not should_include_word("name")

    # Numbers
    assert not should_include_word("123")


def test_make_tdl_entry():
    """Test TDL entry generation."""
    entry = make_tdl_entry("student", pos="noun")

    assert "student" in entry
    assert "n_-_c_le" in entry
    assert "_student_n_1_rel" in entry


def test_generate_tdl(simple_schema):
    """Test TDL generation from schema."""
    tdl = generate_tdl(simple_schema)

    assert isinstance(tdl, str)
    assert len(tdl) > 0

    # Should contain table name
    assert "student" in tdl

    # Should contain column names (those not in KNOWN_WORDS)
    assert "major" in tdl


def test_tdl_avoids_duplicates(simple_schema):
    """Test that TDL generation doesn't create duplicate entries."""
    tdl = generate_tdl(simple_schema)

    # Count occurrences of "student"
    # Should appear only once (in the entry definition)
    lines = [line for line in tdl.split('\n') if line.startswith('student :=')]
    assert len(lines) == 1
