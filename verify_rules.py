#!/usr/bin/env python3
"""
Standalone verification script for squid/rules.py

This script verifies the rules system works correctly without requiring
the full squid module dependencies (like delphin).
"""

import sys
import types
from pathlib import Path
import importlib.util

# Import rules.py directly without going through squid/__init__.py
rules_path = Path(__file__).parent / "squid" / "rules.py"

try:
    spec = importlib.util.spec_from_file_location("rules", rules_path)
    rules = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rules)
    print("✓ Successfully imported squid/rules.py directly")
except Exception as e:
    print(f"✗ Failed to import squid/rules.py: {e}")
    sys.exit(1)

# Track failures
failures = []
successes = []

def verify(condition, success_msg, failure_msg):
    """Helper to track verification results."""
    if condition:
        successes.append(success_msg)
        print(f"✓ {success_msg}")
    else:
        failures.append(failure_msg)
        print(f"✗ {failure_msg}")

print("\n" + "=" * 60)
print("VERIFYING RULES SYSTEM")
print("=" * 60 + "\n")

# 1. Verify all rule dictionaries exist and are frozen
print("1. Checking rule dictionary structure...")
verify(
    hasattr(rules, 'QUANTIFIER_RULES'),
    "QUANTIFIER_RULES exists",
    "QUANTIFIER_RULES not found"
)
verify(
    hasattr(rules, 'COMPARISON_RULES'),
    "COMPARISON_RULES exists",
    "COMPARISON_RULES not found"
)
verify(
    hasattr(rules, 'AGGREGATION_RULES'),
    "AGGREGATION_RULES exists",
    "AGGREGATION_RULES not found"
)
verify(
    hasattr(rules, 'CONNECTIVE_RULES'),
    "CONNECTIVE_RULES exists",
    "CONNECTIVE_RULES not found"
)
verify(
    hasattr(rules, 'PREPOSITION_RULES'),
    "PREPOSITION_RULES exists",
    "PREPOSITION_RULES not found"
)
verify(
    hasattr(rules, 'SET_OPERATION_RULES'),
    "SET_OPERATION_RULES exists",
    "SET_OPERATION_RULES not found"
)
verify(
    hasattr(rules, 'MODIFIER_RULES'),
    "MODIFIER_RULES exists",
    "MODIFIER_RULES not found"
)
verify(
    hasattr(rules, 'VERB_RULES'),
    "VERB_RULES exists",
    "VERB_RULES not found"
)
verify(
    hasattr(rules, 'ARITHMETIC_RULES'),
    "ARITHMETIC_RULES exists",
    "ARITHMETIC_RULES not found"
)
verify(
    hasattr(rules, 'VALUE_RULES'),
    "VALUE_RULES exists",
    "VALUE_RULES not found"
)

# Verify they are frozen (MappingProxyType)
verify(
    isinstance(rules.QUANTIFIER_RULES, types.MappingProxyType),
    "QUANTIFIER_RULES is immutable (MappingProxyType)",
    "QUANTIFIER_RULES is not frozen"
)
verify(
    isinstance(rules.COMPARISON_RULES, types.MappingProxyType),
    "COMPARISON_RULES is immutable (MappingProxyType)",
    "COMPARISON_RULES is not frozen"
)

# 2. Count total rules
print("\n2. Counting rules...")
total_rules = 0
for rule_dict_name in ['QUANTIFIER_RULES', 'COMPARISON_RULES', 'AGGREGATION_RULES',
                        'CONNECTIVE_RULES', 'PREPOSITION_RULES', 'SET_OPERATION_RULES',
                        'MODIFIER_RULES', 'VERB_RULES', 'ARITHMETIC_RULES', 'VALUE_RULES']:
    rule_dict = getattr(rules, rule_dict_name)
    count = len(rule_dict)
    total_rules += count
    print(f"   {rule_dict_name}: {count} rules")

print(f"\n   Total: {total_rules} rules")
verify(
    total_rules >= 200,
    f"Total rule count ({total_rules}) meets requirement (>= 200)",
    f"Total rule count ({total_rules}) below requirement (>= 200)"
)

# 3. Test rule lookup function
print("\n3. Testing lookup_rule() function...")
test_cases = [
    ("which_q", True, "Exact match: which_q"),
    ("which_q_rel", True, "Match with _rel suffix: which_q_rel"),
    ("_old_a_1", True, "Match with sense number: _old_a_1"),
    ("_old_a_1_rel", True, "Match with sense and _rel: _old_a_1_rel"),
    ("nonexistent_predicate", False, "No match for nonexistent predicate"),
]

for pred, should_match, desc in test_cases:
    result = rules.lookup_rule(pred)
    if should_match:
        verify(
            result is not None,
            desc,
            f"{desc} - expected match, got None"
        )
    else:
        verify(
            result is None,
            desc,
            f"{desc} - expected None, got {result}"
        )

# 4. Test classification functions
print("\n4. Testing classification functions...")

verify(
    rules.is_quantifier("which_q"),
    "is_quantifier('which_q') returns True",
    "is_quantifier('which_q') failed"
)
verify(
    not rules.is_quantifier("comp"),
    "is_quantifier('comp') returns False",
    "is_quantifier('comp') should return False"
)

verify(
    rules.is_comparison("comp"),
    "is_comparison('comp') returns True",
    "is_comparison('comp') failed"
)
verify(
    not rules.is_comparison("which_q"),
    "is_comparison('which_q') returns False",
    "is_comparison('which_q') should return False"
)

verify(
    rules.is_aggregation("much-many_a"),
    "is_aggregation('much-many_a') returns True",
    "is_aggregation('much-many_a') failed"
)

verify(
    rules.is_connective("_and_c"),
    "is_connective('_and_c') returns True",
    "is_connective('_and_c') failed"
)

# 5. Test content word classification
print("\n5. Testing content word classification...")
verify(
    rules.is_noun("_student_n_1"),
    "is_noun('_student_n_1') returns True",
    "is_noun classification failed"
)
verify(
    rules.is_verb("_show_v_1"),
    "is_verb('_show_v_1') returns True",
    "is_verb classification failed"
)
verify(
    rules.is_adjective("_old_a_1"),
    "is_adjective('_old_a_1') returns True",
    "is_adjective classification failed"
)

# 6. Verify Rule dataclass
print("\n6. Testing Rule dataclass...")
# Get a sample rule
sample_rule = rules.lookup_rule("which_q")
if sample_rule:
    verify(
        hasattr(sample_rule, 'sql_op'),
        "Rule has sql_op attribute",
        "Rule missing sql_op attribute"
    )
    verify(
        hasattr(sample_rule, 'category'),
        "Rule has category attribute",
        "Rule missing category attribute"
    )
    verify(
        hasattr(sample_rule, 'arg_roles'),
        "Rule has arg_roles attribute",
        "Rule missing arg_roles attribute"
    )
    verify(
        hasattr(sample_rule, 'notes'),
        "Rule has notes attribute",
        "Rule missing notes attribute"
    )
    verify(
        sample_rule.sql_op == "SELECT",
        "which_q maps to SELECT operation",
        f"which_q should map to SELECT, got {sample_rule.sql_op}"
    )

# 7. Test get_rules_by_category
print("\n7. Testing get_rules_by_category()...")
if hasattr(rules, 'get_rules_by_category'):
    quantifier_rules = rules.get_rules_by_category("quantifier")
    verify(
        len(quantifier_rules) > 0,
        f"get_rules_by_category('quantifier') returns {len(quantifier_rules)} rules",
        "get_rules_by_category('quantifier') returned no rules"
    )
else:
    failures.append("get_rules_by_category() function not found")
    print("✗ get_rules_by_category() function not found")

# 8. Verify compound patterns
print("\n8. Checking compound patterns...")
if hasattr(rules, 'COMPOUND_PATTERNS'):
    compound_count = len(rules.COMPOUND_PATTERNS)
    print(f"   Found {compound_count} compound patterns")
    verify(
        compound_count > 0,
        f"COMPOUND_PATTERNS contains {compound_count} patterns",
        "COMPOUND_PATTERNS is empty"
    )
else:
    failures.append("COMPOUND_PATTERNS not found")
    print("✗ COMPOUND_PATTERNS not found")

# Summary
print("\n" + "=" * 60)
print("VERIFICATION SUMMARY")
print("=" * 60)
print(f"✓ Passed: {len(successes)}")
print(f"✗ Failed: {len(failures)}")

if failures:
    print("\nFailures:")
    for failure in failures:
        print(f"  - {failure}")
    sys.exit(1)
else:
    print("\n🎉 All verifications passed! Rules system is working correctly.")
    sys.exit(0)
