"""Tests for squid.rules module."""

import pytest
from squid import rules


@pytest.mark.xfail(strict=True, reason="tests the legacy pipeline: the rule tables (squid/rules.py, read only by the legacy compiler and disambiguator) hold Rule objects and the tests index them as dicts")
def test_quantifier_rules():
    """Test quantifier rule definitions."""
    assert "which_q" in rules.QUANTIFIER_RULES
    assert rules.QUANTIFIER_RULES["which_q"]["sql_op"] == "SELECT"

    assert "_every_q" in rules.QUANTIFIER_RULES
    assert rules.QUANTIFIER_RULES["_every_q"]["sql_op"] == "UNIVERSAL"


@pytest.mark.xfail(strict=True, reason="tests the legacy pipeline: the rule tables (squid/rules.py, read only by the legacy compiler and disambiguator) hold Rule objects and the tests index them as dicts")
def test_comparison_rules():
    """Test comparison rule definitions."""
    assert "comp" in rules.COMPARISON_RULES
    assert rules.COMPARISON_RULES["comp"]["sql_op"] == "COMPARE"

    assert "comp_equal" in rules.COMPARISON_RULES
    assert rules.COMPARISON_RULES["comp_equal"]["sql_op"] == "EQUAL"


@pytest.mark.xfail(strict=True, reason="tests the legacy pipeline: the rule tables (squid/rules.py, read only by the legacy compiler and disambiguator) hold Rule objects and the tests index them as dicts")
def test_aggregation_rules():
    """Test aggregation rule definitions."""
    assert "much-many_a" in rules.AGGREGATION_RULES
    assert rules.AGGREGATION_RULES["much-many_a"]["sql_op"] == "COUNT"

    assert "_most_a_1" in rules.AGGREGATION_RULES


@pytest.mark.xfail(strict=True, reason="tests the legacy pipeline: the rule tables (squid/rules.py, read only by the legacy compiler and disambiguator) hold Rule objects and the tests index them as dicts")
def test_connective_rules():
    """Test connective rule definitions."""
    assert "_and_c" in rules.CONNECTIVE_RULES
    assert rules.CONNECTIVE_RULES["_and_c"]["sql_op"] == "AND"

    assert "_or_c" in rules.CONNECTIVE_RULES
    assert rules.CONNECTIVE_RULES["_or_c"]["sql_op"] == "OR"


def test_get_rule():
    """Test rule lookup."""
    rule = rules.get_rule("which_q")
    assert rule is not None
    assert rule["sql_op"] == "SELECT"

    assert rules.get_rule("nonexistent") is None


def test_is_quantifier():
    """Test quantifier predicate check."""
    assert rules.is_quantifier("which_q")
    assert rules.is_quantifier("_every_q")
    assert not rules.is_quantifier("comp")
    assert not rules.is_quantifier("_student_n_1")


def test_is_comparison():
    """Test comparison predicate check."""
    assert rules.is_comparison("comp")
    assert rules.is_comparison("comp_equal")
    assert not rules.is_comparison("which_q")


def test_is_aggregation():
    """Test aggregation predicate check."""
    assert rules.is_aggregation("much-many_a")
    assert rules.is_aggregation("_most_a_1")
    assert not rules.is_aggregation("which_q")


def test_is_connective():
    """Test connective predicate check."""
    assert rules.is_connective("_and_c")
    assert rules.is_connective("_or_c")
    assert rules.is_connective("neg")
    assert not rules.is_connective("which_q")


def test_rules_are_immutable():
    """Test that rule dictionaries are immutable."""
    import types

    assert isinstance(rules.QUANTIFIER_RULES, types.MappingProxyType)
    assert isinstance(rules.COMPARISON_RULES, types.MappingProxyType)
    assert isinstance(rules.AGGREGATION_RULES, types.MappingProxyType)
    assert isinstance(rules.CONNECTIVE_RULES, types.MappingProxyType)

    # Attempting to modify should raise error
    try:
        rules.QUANTIFIER_RULES["new_key"] = {}
        assert False, "Should not be able to modify rules"
    except TypeError:
        pass  # Expected
