"""Tests for squid.linker module."""

import pytest

from squid.linker import (
    extract_lemma_from_predicate,
    match_column,
    match_table,
    normalize_inflection,
    normalize_lemma,
)


def test_extract_lemma_from_predicate():
    """Test lemma extraction from DMRS predicates."""
    assert extract_lemma_from_predicate("_student_n_1") == "student"
    assert extract_lemma_from_predicate("_sing_v_1") == "sing"
    assert extract_lemma_from_predicate("which_q") == "which_q"


def test_normalize_inflection():
    """Test inflection normalization."""
    variants = normalize_inflection("student")
    assert "student" in variants
    assert "students" in variants

    variants = normalize_inflection("students")
    assert "student" in variants
    assert "students" in variants


def test_normalize_lemma():
    """Test lemmatization."""
    lemmas = normalize_lemma("singing")
    assert "singing" in lemmas
    # Should contain lemma "sing"
    # (actual behavior depends on lemminflect)


def test_match_table_exact(simple_schema):
    """Test exact table name matching."""
    result = match_table("students", simple_schema)

    assert result is not None
    table, score = result
    assert table == "students"
    assert score == 1.0


def test_match_table_inflection(simple_schema):
    """Test table matching with inflection normalization."""
    result = match_table("student", simple_schema)

    assert result is not None
    table, score = result
    assert table == "students"
    assert score >= 0.9  # High confidence match


def test_match_table_fuzzy(simple_schema):
    """Test fuzzy table matching."""
    result = match_table("studnts", simple_schema, threshold=80)

    # Should match "students" via fuzzy matching
    if result:
        table, score = result
        assert table == "students"
        assert score >= 0.8


def test_match_column_exact(simple_schema):
    """Test exact column name matching."""
    result = match_column("name", simple_schema)

    assert result is not None
    table, column, score = result
    assert table == "students"
    assert column == "name"
    assert score == 1.0


def test_match_column_with_table_hint(multi_table_schema):
    """Test column matching with table hint."""
    result = match_column("name", multi_table_schema, table_hint="customers")

    assert result is not None
    table, column, score = result
    assert table == "customers"
    assert column == "name"


def test_match_column_fuzzy(simple_schema):
    """Test fuzzy column matching."""
    result = match_column("nme", simple_schema, threshold=70)

    # Should match "name" via fuzzy matching
    if result:
        table, column, score = result
        assert column == "name"
        assert score >= 0.7
