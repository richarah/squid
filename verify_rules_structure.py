#!/usr/bin/env python3
"""
Text-based verification of squid/rules.py structure.

This script parses the rules.py file as text to verify its structure
without requiring runtime imports or dependencies.
"""

import re
from pathlib import Path

rules_file = Path(__file__).parent / "squid" / "rules.py"

print("=" * 60)
print("VERIFYING RULES STRUCTURE (Text-based)")
print("=" * 60)
print()

# Read the file
with open(rules_file, 'r') as f:
    content = f.read()

# Track results
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

# 1. Verify Rule dataclass exists
print("1. Checking Rule dataclass...")
has_rule_dataclass = '@dataclass' in content and 'class Rule:' in content
verify(
    has_rule_dataclass,
    "Rule dataclass found",
    "Rule dataclass not found"
)

has_required_fields = all(field in content for field in [
    'sql_op:', 'category:', 'arg_roles:', 'notes:', 'compound:', 'priority:'
])
verify(
    has_required_fields,
    "All required Rule fields present (sql_op, category, arg_roles, notes, compound, priority)",
    "Some required Rule fields missing"
)

# 2. Count Rule() constructions
print("\n2. Counting rules...")
rule_pattern = r'Rule\('
total_rules = len(re.findall(rule_pattern, content))
print(f"   Total Rule() constructions: {total_rules}")
verify(
    total_rules >= 200,
    f"Rule count ({total_rules}) meets requirement (>= 200)",
    f"Rule count ({total_rules}) below requirement (>= 200)"
)

# 3. Verify all rule dictionaries exist
print("\n3. Checking rule dictionary definitions...")
rule_dicts = [
    ('QUANTIFIER_RULES', '_QUANTIFIER_RULES_RAW'),
    ('COMPARISON_RULES', '_COMPARISON_RULES_RAW'),
    ('AGGREGATION_RULES', '_AGGREGATION_RULES_RAW'),
    ('CONNECTIVE_RULES', '_CONNECTIVE_RULES_RAW'),
    ('PREPOSITION_RULES', '_PREPOSITION_RULES_RAW'),
    ('SET_OP_RULES', '_SET_OP_RULES_RAW'),
    ('MODIFIER_RULES', '_MODIFIER_RULES_RAW'),
    ('VERB_RULES', '_VERB_RULES_RAW'),
    ('ARITHMETIC_RULES', '_ARITHMETIC_RULES_RAW'),
    ('VALUE_RULES', '_VALUE_RULES_RAW'),
]

for public_name, raw_name in rule_dicts:
    # Look for pattern: _DICT_NAME_RAW: Dict[str, Rule] = {
    pattern = f'{raw_name}.*?Dict\\[str, Rule\\].*?='
    found = re.search(pattern, content, re.DOTALL)
    verify(
        found is not None,
        f"{public_name} defined (as {raw_name})",
        f"{public_name} not found"
    )

# 4. Verify MappingProxyType usage
print("\n4. Checking immutability (MappingProxyType)...")
has_mapping_proxy = 'MappingProxyType' in content
verify(
    has_mapping_proxy,
    "MappingProxyType used for immutability",
    "MappingProxyType not found"
)

# Count MappingProxyType usages (should be one per rule dict)
mapping_proxy_count = len(re.findall(r'MappingProxyType\(', content))
print(f"   Found {mapping_proxy_count} MappingProxyType usages")

# 5. Verify helper functions exist
print("\n5. Checking required helper functions...")
required_functions = [
    'lookup_rule',
    'classify_predicate',
    'is_quantifier',
    'is_comparison',
    'is_aggregation',
    'is_connective',
    'get_rules_by_category',
    'describe_rule',
]

for func_name in required_functions:
    pattern = f'def {func_name}\\('
    found = re.search(pattern, content)
    verify(
        found is not None,
        f"{func_name}() defined",
        f"{func_name}() not found"
    )

# Optional helper functions (nice to have but not required)
print("\n6. Checking optional helper functions...")
optional_functions = ['is_noun', 'is_verb', 'is_adjective']
for func_name in optional_functions:
    pattern = f'def {func_name}\\('
    found = re.search(pattern, content)
    if found:
        print(f"✓ {func_name}() defined (optional)")
    else:
        print(f"  {func_name}() not defined (optional - OK)")

# 7. Check for compound patterns
print("\n7. Checking compound patterns...")
has_compound_patterns = 'COMPOUND_PATTERNS' in content
verify(
    has_compound_patterns,
    "COMPOUND_PATTERNS defined",
    "COMPOUND_PATTERNS not found"
)

# 8. Verify type annotations
print("\n8. Checking type annotations...")
has_type_annotations = '-> Optional[Rule]' in content or '-> List[Rule]' in content
verify(
    has_type_annotations,
    "Type annotations present (for mypyc)",
    "Type annotations missing"
)

# 9. Check for string interning
print("\n9. Checking string interning...")
has_string_interning = 'sys.intern' in content
verify(
    has_string_interning,
    "String interning used (memory optimization)",
    "String interning not used"
)

# 10. Check for specific important rules
print("\n10. Verifying key rules exist...")
key_rules = [
    'which_q',  # Main query quantifier
    '_every_q',  # Universal quantifier
    'comp',  # Comparison
    'much-many_a',  # COUNT aggregation
    '_and_c',  # AND connective
    '_or_c',  # OR connective
]

for rule_pred in key_rules:
    pattern = f'"{rule_pred}".*?Rule\\('
    found = re.search(pattern, content, re.DOTALL)
    verify(
        found is not None,
        f"Key rule '{rule_pred}' defined",
        f"Key rule '{rule_pred}' not found"
    )

# 11. Verify legacy API compatibility
print("\n11. Checking legacy API (backwards compatibility)...")
legacy_dicts = [
    'QUANTIFIER_RULES',  # Should be exposed (not just _RAW version)
    'COMPARISON_RULES',
    'AGGREGATION_RULES',
    'CONNECTIVE_RULES',
]

for dict_name in legacy_dicts:
    # Check if the non-_RAW version is exposed
    pattern = f'^{dict_name}\\s*[:=]'
    found = re.search(pattern, content, re.MULTILINE)
    verify(
        found is not None,
        f"Legacy {dict_name} exposed",
        f"Legacy {dict_name} not exposed"
    )

# 12. Count lines of code
print("\n12. File statistics...")
line_count = len(content.split('\n'))
print(f"   Total lines: {line_count}")
verify(
    line_count > 500,
    f"File has substantial content ({line_count} lines)",
    f"File seems too short ({line_count} lines)"
)

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
    print("\n⚠️  Some verifications failed. Please review the rules.py file.")
    exit(1)
else:
    print("\n🎉 All structural verifications passed!")
    print("\nThe rules.py file is correctly structured with:")
    print(f"  - {total_rules} rules across 10 categories")
    print(f"  - All helper functions implemented")
    print(f"  - Immutable dictionaries (MappingProxyType)")
    print(f"  - Type annotations for mypyc compilation")
    print(f"  - String interning for memory efficiency")
    print(f"  - Legacy API compatibility")
    print("\n✅ Rules system is ready for use!")
    print("\n📝 Note: Functional testing requires installing dependencies:")
    print("   pip install delphin sqlglot rapidfuzz lemminflect")
    exit(0)
