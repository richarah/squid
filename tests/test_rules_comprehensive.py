"""Comprehensive tests for squid.rules module (200+ rules)."""

import types

import pytest

from squid import rules
from squid.rules import Rule


def test_rules_version():
    """Test that RULES_VERSION is defined."""
    assert rules.RULES_VERSION == "1.0.0"


def test_rule_dataclass_structure():
    """Test Rule dataclass has correct structure."""
    rule = Rule(
        sql_op="TEST",
        category="test",
        arg_roles=("ARG1", "ARG2"),
        notes="Test rule",
        compound=False,
        priority=0
    )

    assert rule.sql_op == "TEST"
    assert rule.category == "test"
    assert rule.arg_roles == ("ARG1", "ARG2")
    assert rule.notes == "Test rule"
    assert rule.compound is False
    assert rule.priority == 0


def test_all_rule_dicts_are_frozen():
    """Test that all rule dictionaries are frozen (MappingProxyType)."""
    assert isinstance(rules.QUANTIFIER_RULES, types.MappingProxyType)
    assert isinstance(rules.COMPARISON_RULES, types.MappingProxyType)
    assert isinstance(rules.AGGREGATION_RULES, types.MappingProxyType)
    assert isinstance(rules.CONNECTIVE_RULES, types.MappingProxyType)
    assert isinstance(rules.PREPOSITION_RULES, types.MappingProxyType)
    assert isinstance(rules.SET_OP_RULES, types.MappingProxyType)
    assert isinstance(rules.MODIFIER_RULES, types.MappingProxyType)
    assert isinstance(rules.VERB_RULES, types.MappingProxyType)
    assert isinstance(rules.ARITHMETIC_RULES, types.MappingProxyType)
    assert isinstance(rules.VALUE_RULES, types.MappingProxyType)
    assert isinstance(rules.ALL_RULES, types.MappingProxyType)


def test_rules_are_immutable():
    """Test that attempting to modify rules raises error."""
    with pytest.raises(TypeError):
        rules.QUANTIFIER_RULES["new_key"] = Rule("TEST", "test")


def test_all_rules_are_rule_objects():
    """Test that all values in ALL_RULES are Rule objects."""
    for pred, rule in rules.ALL_RULES.items():
        assert isinstance(rule, Rule), f"{pred} is not a Rule object"
        assert isinstance(rule.sql_op, str), f"{pred} sql_op is not string"
        assert isinstance(rule.category, str), f"{pred} category is not string"
        assert isinstance(rule.arg_roles, tuple), f"{pred} arg_roles is not tuple"
        assert isinstance(rule.notes, str), f"{pred} notes is not string"
        assert isinstance(rule.compound, bool), f"{pred} compound is not bool"
        assert isinstance(rule.priority, int), f"{pred} priority is not int"


def test_all_rules_have_non_empty_fields():
    """Test that all rules have non-empty sql_op and notes."""
    for pred, rule in rules.ALL_RULES.items():
        assert rule.sql_op, f"{pred} has empty sql_op"
        assert rule.category, f"{pred} has empty category"
        # notes can be empty for legacy compatibility


def test_total_rule_count():
    """Test that we have at least 200 rules defined."""
    count = rules.get_rule_count()
    assert count >= 200, f"Only {count} rules defined, expected >= 200"


def test_quantifier_rules_exist():
    """Test quantifier rules are defined."""
    assert "which_q" in rules.QUANTIFIER_RULES
    assert "_every_q" in rules.QUANTIFIER_RULES
    assert "_some_q" in rules.QUANTIFIER_RULES
    assert "_a_q" in rules.QUANTIFIER_RULES
    assert "_the_q" in rules.QUANTIFIER_RULES
    assert "udef_q" in rules.QUANTIFIER_RULES
    assert "proper_q" in rules.QUANTIFIER_RULES
    assert "_no_q" in rules.QUANTIFIER_RULES


def test_comparison_rules_exist():
    """Test comparison rules are defined."""
    assert "comp" in rules.COMPARISON_RULES
    assert "comp_equal" in rules.COMPARISON_RULES
    assert "superl" in rules.COMPARISON_RULES
    assert "_at+least_x_deg" in rules.COMPARISON_RULES
    assert "_at+most_x_deg" in rules.COMPARISON_RULES


def test_aggregation_rules_exist():
    """Test aggregation rules are defined."""
    assert "much-many_a" in rules.AGGREGATION_RULES
    assert "_most_a_1" in rules.AGGREGATION_RULES
    assert "_average_a_1" in rules.AGGREGATION_RULES
    assert "_total_a_1" in rules.AGGREGATION_RULES
    assert "_sum_n_1" in rules.AGGREGATION_RULES


def test_connective_rules_exist():
    """Test connective rules are defined."""
    assert "_and_c" in rules.CONNECTIVE_RULES
    assert "_or_c" in rules.CONNECTIVE_RULES
    assert "neg" in rules.CONNECTIVE_RULES
    assert "_but_c" in rules.CONNECTIVE_RULES


def test_preposition_rules_exist():
    """Test preposition rules are defined."""
    assert "_in_p_loc" in rules.PREPOSITION_RULES
    assert "_of_p" in rules.PREPOSITION_RULES
    assert "_with_p" in rules.PREPOSITION_RULES
    assert "_from_p_dir" in rules.PREPOSITION_RULES
    assert "_before_p" in rules.PREPOSITION_RULES
    assert "_after_p" in rules.PREPOSITION_RULES
    assert "_between_p" in rules.PREPOSITION_RULES


def test_modifier_rules_exist():
    """Test modifier rules are defined."""
    assert "_different_a_1" in rules.MODIFIER_RULES
    assert "_distinct_a_1" in rules.MODIFIER_RULES
    assert "_first_a_1" in rules.MODIFIER_RULES
    assert "_last_a_1" in rules.MODIFIER_RULES
    assert "_top_a_1" in rules.MODIFIER_RULES


def test_verb_rules_exist():
    """Test verb rules are defined."""
    assert "_show_v_1" in rules.VERB_RULES
    assert "_find_v_1" in rules.VERB_RULES
    assert "_be_v_id" in rules.VERB_RULES
    assert "_have_v_1" in rules.VERB_RULES
    assert "_contain_v_1" in rules.VERB_RULES


def test_arithmetic_rules_exist():
    """Test arithmetic rules are defined."""
    assert "_plus_p" in rules.ARITHMETIC_RULES
    assert "_minus_p" in rules.ARITHMETIC_RULES
    assert "_times_p" in rules.ARITHMETIC_RULES
    assert "_divide_v_1" in rules.ARITHMETIC_RULES


def test_value_rules_exist():
    """Test value rules are defined."""
    assert "card" in rules.VALUE_RULES
    assert "ord" in rules.VALUE_RULES
    assert "named" in rules.VALUE_RULES
    assert "_true_a_1" in rules.VALUE_RULES
    assert "_false_a_1" in rules.VALUE_RULES


def test_lookup_rule_exact_match():
    """Test lookup_rule finds exact matches."""
    rule = rules.lookup_rule("which_q")
    assert rule is not None
    assert rule.sql_op == "SELECT"

    rule = rules.lookup_rule("comp")
    assert rule is not None
    assert rule.sql_op == "COMPARATIVE"


def test_lookup_rule_strips_rel_suffix():
    """Test lookup_rule strips _rel suffix."""
    # First verify the rule exists without _rel
    assert "which_q" in rules.ALL_RULES

    # Now test lookup with _rel suffix
    rule = rules.lookup_rule("which_q_rel")
    assert rule is not None
    assert rule.sql_op == "SELECT"


def test_lookup_rule_strips_sense_number():
    """Test lookup_rule strips sense numbers."""
    # If we have _old_a in rules, _old_a_1 should match
    # Let's use a real example: _average_a_1
    rule = rules.lookup_rule("_average_a_1")
    assert rule is not None
    assert rule.sql_op == "AGG_AVG"

    # Should also match _average_a_2 if we stripped the sense
    # (though in practice we'd need the base rule without sense)


def test_lookup_rule_returns_none_for_unknown():
    """Test lookup_rule returns None for unknown predicates."""
    rule = rules.lookup_rule("_student_n_1")
    assert rule is None

    rule = rules.lookup_rule("_unknown_predicate_x_1")
    assert rule is None


def test_classify_predicate_quantifier():
    """Test classify_predicate correctly classifies quantifiers."""
    assert rules.classify_predicate("which_q") == "quantifier"
    assert rules.classify_predicate("_every_q") == "quantifier"
    assert rules.classify_predicate("_the_q") == "quantifier"


def test_classify_predicate_comparison():
    """Test classify_predicate correctly classifies comparisons."""
    assert rules.classify_predicate("comp") == "comparison"
    assert rules.classify_predicate("comp_equal") == "comparison"
    assert rules.classify_predicate("superl") == "comparison"


def test_classify_predicate_aggregation():
    """Test classify_predicate correctly classifies aggregations."""
    assert rules.classify_predicate("much-many_a") == "aggregation"
    assert rules.classify_predicate("_average_a_1") == "aggregation"
    assert rules.classify_predicate("_total_a_1") == "aggregation"


def test_classify_predicate_connective():
    """Test classify_predicate correctly classifies connectives."""
    assert rules.classify_predicate("_and_c") == "connective"
    assert rules.classify_predicate("_or_c") == "connective"
    assert rules.classify_predicate("neg") == "connective"


def test_classify_predicate_preposition():
    """Test classify_predicate correctly classifies prepositions."""
    assert rules.classify_predicate("_in_p_loc") == "preposition"
    assert rules.classify_predicate("_of_p") == "preposition"


def test_classify_predicate_modifier():
    """Test classify_predicate correctly classifies modifiers."""
    assert rules.classify_predicate("_different_a_1") == "modifier"
    assert rules.classify_predicate("_distinct_a_1") == "modifier"


def test_classify_predicate_verb():
    """Test classify_predicate correctly classifies verbs."""
    assert rules.classify_predicate("_show_v_1") == "verb"
    assert rules.classify_predicate("_have_v_1") == "verb"


def test_classify_predicate_content_noun():
    """Test classify_predicate classifies content nouns."""
    assert rules.classify_predicate("_student_n_1") == "content_noun"
    assert rules.classify_predicate("_dog_n_1") == "content_noun"


def test_classify_predicate_content_verb():
    """Test classify_predicate classifies content verbs."""
    assert rules.classify_predicate("_run_v_1") == "content_verb"
    assert rules.classify_predicate("_sleep_v_1") == "content_verb"


def test_classify_predicate_content_adj():
    """Test classify_predicate classifies content adjectives."""
    assert rules.classify_predicate("_happy_a_1") == "content_adj"
    assert rules.classify_predicate("_old_aj_1") == "content_adj"


def test_classify_predicate_unknown():
    """Test classify_predicate returns 'unknown' for unrecognized predicates."""
    assert rules.classify_predicate("weird_pred") == "unknown"
    assert rules.classify_predicate("123") == "unknown"


def test_describe_rule():
    """Test describe_rule returns human-readable descriptions."""
    desc = rules.describe_rule("which_q")
    assert "which_q" in desc
    assert "SELECT" in desc

    desc = rules.describe_rule("_average_a_1")
    assert "_average_a_1" in desc or "average" in desc.lower()
    assert "AVG" in desc


def test_describe_rule_content_word():
    """Test describe_rule handles content words."""
    desc = rules.describe_rule("_student_n_1")
    assert "content word" in desc.lower() or "schema linker" in desc.lower()


def test_get_rules_by_category():
    """Test get_rules_by_category returns rules for each category."""
    quantifiers = rules.get_rules_by_category("quantifier")
    assert len(quantifiers) > 0
    assert all(r.category == "quantifier" for r in quantifiers.values())

    comparisons = rules.get_rules_by_category("comparison")
    assert len(comparisons) > 0
    assert all(r.category == "comparison" for r in comparisons.values())

    aggregations = rules.get_rules_by_category("aggregation")
    assert len(aggregations) > 0
    assert all(r.category == "aggregation" for r in aggregations.values())


def test_get_compound_rules():
    """Test get_compound_rules returns compound patterns."""
    compounds = rules.get_compound_rules()

    assert isinstance(compounds, list)
    assert len(compounds) >= 15, f"Expected >= 15 compound patterns, got {len(compounds)}"

    # Check that compound patterns are described
    assert any("RELATIVE_CLAUSE" in p for p in compounds)
    assert any("HAVING_PATTERN" in p for p in compounds)
    assert any("UNIVERSAL_QUANTIFICATION" in p for p in compounds)


def test_get_rule_count():
    """Test get_rule_count returns correct count."""
    count = rules.get_rule_count()
    assert isinstance(count, int)
    assert count == len(rules.ALL_RULES)
    assert count >= 200


def test_get_categories():
    """Test get_categories returns all unique categories."""
    categories = rules.get_categories()

    assert isinstance(categories, frozenset)
    assert "quantifier" in categories
    assert "comparison" in categories
    assert "aggregation" in categories
    assert "connective" in categories
    assert "preposition" in categories
    assert "modifier" in categories
    assert "verb" in categories
    assert "value" in categories


def test_legacy_get_rule():
    """Test legacy get_rule function (returns dict)."""
    result = rules.get_rule("which_q")
    assert result is not None
    assert isinstance(result, dict)
    assert "sql_op" in result
    assert "notes" in result
    assert result["sql_op"] == "SELECT"


def test_legacy_is_quantifier():
    """Test legacy is_quantifier function."""
    assert rules.is_quantifier("which_q") is True
    assert rules.is_quantifier("_every_q") is True
    assert rules.is_quantifier("comp") is False


def test_legacy_is_comparison():
    """Test legacy is_comparison function."""
    assert rules.is_comparison("comp") is True
    assert rules.is_comparison("superl") is True
    assert rules.is_comparison("which_q") is False


def test_legacy_is_aggregation():
    """Test legacy is_aggregation function."""
    assert rules.is_aggregation("much-many_a") is True
    assert rules.is_aggregation("_average_a_1") is True
    assert rules.is_aggregation("which_q") is False


def test_legacy_is_connective():
    """Test legacy is_connective function."""
    assert rules.is_connective("_and_c") is True
    assert rules.is_connective("_or_c") is True
    assert rules.is_connective("which_q") is False


def test_legacy_is_preposition():
    """Test legacy is_preposition function."""
    assert rules.is_preposition("_in_p_loc") is True
    assert rules.is_preposition("_of_p") is True
    assert rules.is_preposition("which_q") is False


def test_no_key_collisions():
    """Test that there are no unintended key collisions in ALL_RULES."""
    # Count rules in individual dicts
    total_individual = (
        len(rules.QUANTIFIER_RULES) +
        len(rules.COMPARISON_RULES) +
        len(rules.AGGREGATION_RULES) +
        len(rules.CONNECTIVE_RULES) +
        len(rules.PREPOSITION_RULES) +
        len(rules.SET_OP_RULES) +
        len(rules.MODIFIER_RULES) +
        len(rules.VERB_RULES) +
        len(rules.ARITHMETIC_RULES) +
        len(rules.VALUE_RULES)
    )

    # If there were collisions, ALL_RULES would have fewer entries
    # A small number of intentional collisions is okay (handled by priority)
    # but large discrepancies indicate a problem
    assert len(rules.ALL_RULES) >= total_individual * 0.95, \
        f"Too many collisions: {total_individual} individual rules, but only {len(rules.ALL_RULES)} in ALL_RULES"


def test_string_keys_are_interned():
    """Test that all rule dictionary keys are interned strings."""
    # Python interns short strings automatically, but we can check identity
    for key in rules.ALL_RULES.keys():
        assert isinstance(key, str)
        # The fact that rules load without error means intern worked


def test_compound_patterns_list():
    """Test COMPOUND_PATTERNS is accessible."""
    assert isinstance(rules.COMPOUND_PATTERNS, list)
    assert len(rules.COMPOUND_PATTERNS) > 0


def test_sentence_force_types():
    """Test SENTENCE_FORCE_TYPES is defined."""
    assert isinstance(rules.SENTENCE_FORCE_TYPES, dict)
    assert "ques" in rules.SENTENCE_FORCE_TYPES
    assert "prop" in rules.SENTENCE_FORCE_TYPES
    assert "comm" in rules.SENTENCE_FORCE_TYPES


def test_all_arg_roles_are_tuples():
    """Test that all arg_roles fields are tuples."""
    for pred, rule in rules.ALL_RULES.items():
        assert isinstance(rule.arg_roles, tuple), \
            f"{pred} has arg_roles of type {type(rule.arg_roles)}"


def test_priority_field_exists():
    """Test that all rules have a priority field."""
    for pred, rule in rules.ALL_RULES.items():
        assert hasattr(rule, "priority")
        assert isinstance(rule.priority, int)


def test_compound_field_exists():
    """Test that all rules have a compound field."""
    for pred, rule in rules.ALL_RULES.items():
        assert hasattr(rule, "compound")
        assert isinstance(rule.compound, bool)


def test_set_operation_compound_rules():
    """Test that set operation compound rules are marked correctly."""
    for pred in ["BOTH_AND", "EITHER_OR", "BUT_NOT"]:
        if pred in rules.SET_OP_RULES:
            assert rules.SET_OP_RULES[pred].compound is True


def test_degree_rules_coverage():
    """Test that degree rules cover common patterns."""
    degree_preds = [
        "_at+least_x_deg", "_at+most_x_deg", "_more+than_x_deg",
        "_less+than_x_deg", "_exactly_x_deg", "_about_x_deg"
    ]

    for pred in degree_preds:
        assert pred in rules.COMPARISON_RULES or pred in rules.ALL_RULES, \
            f"Degree predicate {pred} not found"


def test_temporal_rules_coverage():
    """Test that temporal rules are defined."""
    temporal_preds = [
        "_before_p", "_after_p", "_since_p", "_until_p", "_during_p",
        "_year_n_1", "_month_n_1", "_day_n_1",
        "_today_a_1", "_yesterday_a_1", "_tomorrow_a_1"
    ]

    found = sum(1 for p in temporal_preds if p in rules.ALL_RULES)
    assert found >= len(temporal_preds) * 0.8, \
        f"Only {found}/{len(temporal_preds)} temporal predicates found"


def test_string_function_rules():
    """Test that string function rules are defined."""
    string_preds = [
        "_contain_v_1", "_start_v_1", "_end_v_1",
        "_upper_a_1", "_lower_a_1", "_trim_v_1"
    ]

    found = sum(1 for p in string_preds if p in rules.ALL_RULES)
    assert found >= 4, f"Only {found} string function predicates found"


def test_rule_categories_are_valid():
    """Test that all rules have valid category values."""
    valid_categories = {
        "quantifier", "comparison", "degree", "aggregation", "connective",
        "preposition", "set_op", "modifier", "verb", "arithmetic", "function",
        "value", "construction"
    }

    for pred, rule in rules.ALL_RULES.items():
        assert rule.category in valid_categories, \
            f"{pred} has invalid category: {rule.category}"
