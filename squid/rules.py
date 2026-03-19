"""
SQUID structural mapping rules — complete ERG DMRS-to-SQL mapping.

Version: 1.0.0
Coverage: All SQL constructs expressible in natural English.

Architecture:
- Rules are DATA (frozen dicts), not code
- The compiler pattern-matches DMRS predicate names against these dicts
- Adding a rule = adding one dict entry, no code changes elsewhere
- Every rule has a human-readable `notes` field for EU AI Act audit trail

ERG predicate naming:
- Surface: _lemma_pos_sense (e.g. _student_n_1, _old_a_1)
- Abstract: name (e.g. which_q, comp, superl, neg)
- _rel suffix may/may not be present — lookup handles both

Rule lookup order:
1. Exact match on predicate string
2. Strip _rel suffix, retry
3. Prefix match (handles sense numbers: _old_a matches _old_a_1, _old_a_2)
4. Category match (anything starting with _ and containing _n_ is a noun, etc.)

NOTE: Some predicate names may need verification against actual ERG output.
Use the ERG demonstrator at http://erg.delph-in.net/logon or local ACE to verify.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from types import MappingProxyType
from typing import Dict, FrozenSet, List, Optional, Tuple

RULES_VERSION: str = "1.0.0"


@dataclass(slots=True, frozen=True)
class Rule:
    """A single structural mapping rule."""

    sql_op: str  # SQL operation identifier (compiler dispatches on this)
    category: str  # Rule category for classification
    arg_roles: Tuple[str, ...] = ()  # Relevant DMRS arg roles
    notes: str = ""  # Human-readable audit trail
    compound: bool = False  # True if detection requires multiple predicates
    priority: int = 0  # Higher = check first (for overlapping patterns)


def _intern_keys(d: Dict[str, Rule]) -> Dict[str, Rule]:
    """Intern all dictionary keys."""
    return {sys.intern(k): v for k, v in d.items()}


# =============================================================================
# CATEGORY 1: QUANTIFIERS
# =============================================================================

_QUANTIFIER_RULES_RAW: Dict[str, Rule] = {
    "which_q": Rule("SELECT", "quantifier", ("BV",), "WH-question, main query target"),
    "_which_q": Rule("SELECT", "quantifier", ("BV",), "Alternative form"),
    "_every_q": Rule("UNIVERSAL", "quantifier", ("BV",), "every X → NOT EXISTS(X WHERE NOT ...)"),
    "_all_q": Rule("UNIVERSAL", "quantifier", ("BV",), "all X → same as every"),
    "_each_q": Rule("GROUP_BY_TARGET", "quantifier", ("BV",), "each department → GROUP BY"),
    "_some_q": Rule("EXISTENTIAL", "quantifier", ("BV",), "some X → EXISTS or bare ref"),
    "_a_q": Rule("EXISTENTIAL", "quantifier", ("BV",), "Indefinite article"),
    "_any_q": Rule("EXISTENTIAL_OR_UNIVERSAL", "quantifier", ("BV",), "any X — context-dependent"),
    "_no_q": Rule("NEGATED_EXISTENTIAL", "quantifier", ("BV",), "no X → NOT EXISTS"),
    "_the_q": Rule("DEFINITE", "quantifier", ("BV",), "the X → unique reference, may need LIMIT 1"),
    "udef_q": Rule("BARE_QUANT", "quantifier", ("BV",), "Bare NP (no determiner)"),
    "proper_q": Rule("NAMED_ENTITY", "quantifier", ("BV",), "Proper name, CARG has value"),
    "def_explicit_q": Rule("DEFINITE", "quantifier", ("BV",), "Explicit definite"),
    "def_implicit_q": Rule("DEFINITE", "quantifier", ("BV",), "Implicit definite"),
    "pronoun_q": Rule("PRONOUN_REF", "quantifier", ("BV",), "Pronoun reference (he/she/it/they)"),
    "number_q": Rule("NUMERIC_REF", "quantifier", ("BV",), "Introduced with cardinal numbers"),
    "_this_q_dem": Rule("DEFINITE", "quantifier", ("BV",), "Demonstrative 'this'"),
    "_that_q_dem": Rule("DEFINITE", "quantifier", ("BV",), "Demonstrative 'that'"),
    "_these_q_dem": Rule("DEFINITE_PLURAL", "quantifier", ("BV",), "Demonstrative 'these'"),
    "_those_q_dem": Rule("DEFINITE_PLURAL", "quantifier", ("BV",), "Demonstrative 'those'"),
    "_most_q": Rule("MAJORITY", "quantifier", ("BV",), "most X → HAVING COUNT > total/2"),
    "_many_q": Rule("BARE_QUANT", "quantifier", ("BV",), "many X → no direct SQL equivalent"),
    "_few_q": Rule("BARE_QUANT", "quantifier", ("BV",), "few X → no direct SQL equivalent"),
    "_several_q": Rule("BARE_QUANT", "quantifier", ("BV",), "several X"),
    "_both_q": Rule("DUAL_UNIVERSAL", "quantifier", ("BV",), "both X and Y → INTERSECT or AND"),
    "_neither_q": Rule("DUAL_NEGATION", "quantifier", ("BV",), "neither X nor Y → NOT X AND NOT Y"),
    "_either_q": Rule("DUAL_EXISTENTIAL", "quantifier", ("BV",), "either X or Y → UNION or OR"),
    "free_relative_q": Rule("SUBQUERY_REF", "quantifier", ("BV",), "what/whoever as free relative"),
    "free_relative_ever_q": Rule("SUBQUERY_REF", "quantifier", ("BV",), "whatever/whoever"),
    "_enough_q": Rule("THRESHOLD", "quantifier", ("BV",), "enough X → HAVING COUNT >= threshold"),
}

# =============================================================================
# CATEGORY 2: COMPARISONS AND DEGREE
# =============================================================================

_COMPARISON_RULES_RAW: Dict[str, Rule] = {
    "comp": Rule("COMPARATIVE", "comparison", ("ARG1", "ARG2"), "Generic comparative, direction from adjective"),
    "comp_equal": Rule("COMP_EQUAL", "comparison", ("ARG1", "ARG2"), "as X as Y → ="),
    "comp_more": Rule("COMP_GREATER", "comparison", ("ARG1", "ARG2"), "more than → >"),
    "comp_less": Rule("COMP_LESS", "comparison", ("ARG1", "ARG2"), "less/fewer than → <"),
    "comp_not+less": Rule("COMP_GEQ", "comparison", ("ARG1", "ARG2"), "not less than → >="),
    "comp_not+more": Rule("COMP_LEQ", "comparison", ("ARG1", "ARG2"), "not more than → <="),
    "superl": Rule("SUPERLATIVE", "comparison", ("ARG1",), "oldest/youngest → ORDER BY + LIMIT 1"),
    "_at+least_x_deg": Rule("DEG_GEQ", "degree", ("ARG1",), "at least N → >= N"),
    "_at+most_x_deg": Rule("DEG_LEQ", "degree", ("ARG1",), "at most N → <= N"),
    "_more+than_x_deg": Rule("DEG_GT", "degree", ("ARG1",), "more than N → > N"),
    "_less+than_x_deg": Rule("DEG_LT", "degree", ("ARG1",), "less than N → < N"),
    "_fewer+than_x_deg": Rule("DEG_LT", "degree", ("ARG1",), "fewer than N → < N"),
    "_exactly_x_deg": Rule("DEG_EQ", "degree", ("ARG1",), "exactly N → = N"),
    "_about_x_deg": Rule("DEG_APPROX", "degree", ("ARG1",), "about N → BETWEEN N-margin AND N+margin"),
    "_approximately_x_deg": Rule("DEG_APPROX", "degree", ("ARG1",), "approximately N"),
    "_over_x_deg": Rule("DEG_GT", "degree", ("ARG1",), "over N → > N"),
    "_under_x_deg": Rule("DEG_LT", "degree", ("ARG1",), "under N → < N"),
    "_up+to_x_deg": Rule("DEG_LEQ", "degree", ("ARG1",), "up to N → <= N"),
    "_no+more+than_x_deg": Rule("DEG_LEQ", "degree", ("ARG1",), "no more than N → <= N"),
    "_no+less+than_x_deg": Rule("DEG_GEQ", "degree", ("ARG1",), "no less than N → >= N"),
    "_only_x_deg": Rule("DEG_EQ", "degree", ("ARG1",), "only N → = N"),
    "_just_x_deg": Rule("DEG_EQ", "degree", ("ARG1",), "just N → = N"),
    "_nearly_x_deg": Rule("DEG_LT", "degree", ("ARG1",), "nearly N → < N (approaching)"),
    "_almost_x_deg": Rule("DEG_LT", "degree", ("ARG1",), "almost N → < N"),
    "_more_x_comp": Rule("STANDALONE_MORE", "degree", (), "'more' without explicit 'than'"),
    "_less_x_comp": Rule("STANDALONE_LESS", "degree", (), "'less' without explicit 'than'"),
    "_most_x_comp": Rule("STANDALONE_MOST", "degree", (), "'most' as degree word"),
    "_least_x_comp": Rule("STANDALONE_LEAST", "degree", (), "'least' as degree word"),
    "_as_x_deg": Rule("DEG_EQUAL_AS", "degree", ("ARG1", "ARG2"), "Part of 'as...as' equative"),
    "_so_x_deg": Rule("DEG_RESULT", "degree", ("ARG1",), "'so X that...' — degree-result"),
    "_too_x_deg": Rule("DEG_EXCESS", "degree", ("ARG1",), "'too X' → exceeds threshold"),
    "_enough_x_deg": Rule("DEG_SUFFICIENT", "degree", ("ARG1",), "'X enough' → >= threshold"),
}

# =============================================================================
# CATEGORY 3: AGGREGATION
# =============================================================================

_AGGREGATION_RULES_RAW: Dict[str, Rule] = {
    "much-many_a": Rule("COUNT", "aggregation", ("ARG1",), "'how many' → COUNT(*)"),
    "_many_a_1": Rule("COUNT_CONTEXT", "aggregation", ("ARG1",), "'many X' → COUNT in HAVING context"),
    "_much_a_1": Rule("SUM_OR_COUNT", "aggregation", ("ARG1",), "Mass context → SUM, count context → COUNT"),
    "_few_a_1": Rule("COUNT_FEW", "aggregation", ("ARG1",), "'few' → COUNT < threshold in HAVING"),
    "_little_a_1": Rule("SUM_LOW", "aggregation", ("ARG1",), "'little revenue' → SUM < threshold"),
    "_most_a_1": Rule("AGG_MAX", "aggregation", ("ARG1",), "'the most X' → MAX or ORDER BY DESC LIMIT 1"),
    "_least_a_1": Rule("AGG_MIN", "aggregation", ("ARG1",), "'the fewest/least' → MIN"),
    "_highest_a_1": Rule("AGG_MAX", "aggregation", ("ARG1",), "'the highest X' → MAX(X)"),
    "_lowest_a_1": Rule("AGG_MIN", "aggregation", ("ARG1",), "'the lowest X' → MIN(X)"),
    "_greatest_a_1": Rule("AGG_MAX", "aggregation", ("ARG1",), "'the greatest X' → MAX(X)"),
    "_smallest_a_1": Rule("AGG_MIN", "aggregation", ("ARG1",), "'the smallest X' → MIN(X)"),
    "_largest_a_1": Rule("AGG_MAX", "aggregation", ("ARG1",), "'the largest X' → MAX(X)"),
    "_average_a_1": Rule("AGG_AVG", "aggregation", ("ARG1",), "'the average X' → AVG(X)"),
    "_mean_a_1": Rule("AGG_AVG", "aggregation", ("ARG1",), "'the mean X' → AVG(X)"),
    "_total_a_1": Rule("AGG_SUM", "aggregation", ("ARG1",), "'the total X' → SUM(X)"),
    "_overall_a_1": Rule("AGG_SUM", "aggregation", ("ARG1",), "'the overall X' → SUM(X)"),
    "_maximum_a_1": Rule("AGG_MAX", "aggregation", ("ARG1",), "'the maximum X' → MAX(X)"),
    "_minimum_a_1": Rule("AGG_MIN", "aggregation", ("ARG1",), "'the minimum X' → MIN(X)"),
    "_number_n_of-i": Rule("AGG_COUNT", "aggregation", ("ARG1",), "'the number of X' → COUNT(*)"),
    "_count_n_1": Rule("AGG_COUNT", "aggregation", ("ARG1",), "'the count of X' → COUNT(*)"),
    "_sum_n_1": Rule("AGG_SUM", "aggregation", ("ARG1",), "'the sum of X' → SUM(X)"),
    "_average_n_1": Rule("AGG_AVG", "aggregation", ("ARG1",), "'the average of X' → AVG(X)"),
    "_total_n_1": Rule("AGG_SUM", "aggregation", ("ARG1",), "'the total of X' → SUM(X)"),
    "_percentage_n_1": Rule("AGG_PERCENT", "aggregation", ("ARG1",), "'percentage of X' → COUNT(filtered)*100.0/COUNT(*)"),
    "_proportion_n_1": Rule("AGG_PERCENT", "aggregation", ("ARG1",), "'proportion of X' → same as percentage"),
    "_ratio_n_1": Rule("AGG_RATIO", "aggregation", ("ARG1", "ARG2"), "'ratio of X to Y' → COUNT(X)/COUNT(Y)"),
    "_difference_n_1": Rule("AGG_DIFF", "aggregation", ("ARG1", "ARG2"), "'difference between X and Y' → ABS(AGG(X) - AGG(Y))"),
}

# =============================================================================
# CATEGORY 4: LOGICAL CONNECTIVES
# =============================================================================

_CONNECTIVE_RULES_RAW: Dict[str, Rule] = {
    "_and_c": Rule("AND", "connective", ("L-INDEX", "R-INDEX"), "Binary conjunction"),
    "_or_c": Rule("OR", "connective", ("L-INDEX", "R-INDEX"), "Binary disjunction"),
    "_but_c": Rule("BUT_AND", "connective", ("L-INDEX", "R-INDEX"), "'X but Y' → AND (with possible EXCEPT)"),
    "_but+not_c": Rule("AND_NOT", "connective", ("L-INDEX", "R-INDEX"), "'X but not Y' → X AND NOT Y"),
    "neg": Rule("NOT", "connective", (), "Sentential negation"),
    "_not_x_deg": Rule("NOT_DEG", "connective", ("ARG1",), "Degree negation 'not more than'"),
    "_neither_c": Rule("NOR", "connective", ("L-INDEX", "R-INDEX"), "'neither X nor Y' → NOT(X) AND NOT(Y)"),
    "_nor_c": Rule("NOR", "connective", ("L-INDEX", "R-INDEX"), "Same as neither"),
    "implicit_conj": Rule("AND", "connective", (), "Implicit conjunction in N-ary coordination"),
    "_as+well+as_c": Rule("AND", "connective", ("L-INDEX", "R-INDEX"), "'as well as' → AND"),
    "_both_a_1": Rule("BOTH_MARKER", "connective", (), "Marks 'both...and' → INTERSECT or AND"),
    "_either_a_1": Rule("EITHER_MARKER", "connective", (), "Marks 'either...or' → UNION or OR"),
    "_only_a_1": Rule("EXCLUSIVE", "connective", ("ARG1",), "'only X' → exclusive restriction"),
    "_just_a_1": Rule("EXCLUSIVE", "connective", ("ARG1",), "'just X' → same as only"),
    "_also_a_1": Rule("ADDITIVE", "connective", ("ARG1",), "'also' → UNION or additional condition"),
    "_even_a_1": Rule("INCLUSIVE_EMPHASIS", "connective", ("ARG1",), "'even X' → no direct SQL"),
    "_instead_a_1": Rule("REPLACE", "connective", ("ARG1",), "'instead of X' → replace condition"),
    "_otherwise_a_1": Rule("ELSE", "connective", (), "'otherwise' → no direct SQL"),
}

# =============================================================================
# CATEGORY 5: PREPOSITIONS
# =============================================================================

_PREPOSITION_RULES_RAW: Dict[str, Rule] = {
    "_in_p_loc": Rule("PREP_IN_LOC", "preposition", ("ARG1", "ARG2"), "'in the department' → WHERE or JOIN"),
    "_in_p_state": Rule("PREP_IN_STATE", "preposition", ("ARG1", "ARG2"), "'in the list' → IN (set)"),
    "_of_p": Rule("PREP_OF", "preposition", ("ARG1", "ARG2"), "Genitive 'name of student' → table.column"),
    "_from_p_dir": Rule("PREP_FROM", "preposition", ("ARG1", "ARG2"), "'from France' → WHERE origin = 'France'"),
    "_with_p": Rule("PREP_WITH", "preposition", ("ARG1", "ARG2"), "'students with courses' → JOIN or EXISTS"),
    "_without_p": Rule("PREP_WITHOUT", "preposition", ("ARG1", "ARG2"), "'students without courses' → NOT EXISTS"),
    "_by_p": Rule("PREP_BY", "preposition", ("ARG1", "ARG2"), "Ambiguous: GROUP BY or agent"),
    "_for_p": Rule("PREP_FOR", "preposition", ("ARG1", "ARG2"), "'for each X' → GROUP BY, 'for Y' → WHERE"),
    "_before_p": Rule("PREP_BEFORE", "preposition", ("ARG1", "ARG2"), "'before 2020' → WHERE date < '2020-01-01'"),
    "_after_p": Rule("PREP_AFTER", "preposition", ("ARG1", "ARG2"), "'after 2020' → WHERE date > '2020-12-31'"),
    "_since_p": Rule("PREP_SINCE", "preposition", ("ARG1", "ARG2"), "'since 2020' → WHERE date >= '2020-01-01'"),
    "_until_p": Rule("PREP_UNTIL", "preposition", ("ARG1", "ARG2"), "'until 2020' → WHERE date <= '2020-12-31'"),
    "_during_p": Rule("PREP_DURING", "preposition", ("ARG1", "ARG2"), "'during 2020' → WHERE YEAR(date) = 2020"),
    "_between_p": Rule("PREP_BETWEEN", "preposition", ("ARG1", "ARG2"), "'between 18 and 25' → BETWEEN 18 AND 25"),
    "_above_p": Rule("PREP_ABOVE", "preposition", ("ARG1", "ARG2"), "'above average' → WHERE col > (SELECT AVG(...))"),
    "_below_p": Rule("PREP_BELOW", "preposition", ("ARG1", "ARG2"), "'below average' → WHERE col < (SELECT AVG(...))"),
    "_over_p": Rule("PREP_OVER", "preposition", ("ARG1", "ARG2"), "'over 1000' → WHERE col > 1000"),
    "_under_p": Rule("PREP_UNDER", "preposition", ("ARG1", "ARG2"), "'under 1000' → WHERE col < 1000"),
    "_per_p": Rule("PREP_PER", "preposition", ("ARG1", "ARG2"), "'per department' → GROUP BY department"),
    "_than_p_comp": Rule("PREP_THAN", "preposition", ("ARG1", "ARG2"), "Comparative complement: part of 'more/less than'"),
    "_as_p": Rule("PREP_AS", "preposition", ("ARG1", "ARG2"), "'as a teacher' → role/alias"),
    "_like_p": Rule("PREP_LIKE", "preposition", ("ARG1", "ARG2"), "'like Python' → WHERE col = 'Python'"),
    "_unlike_p": Rule("PREP_UNLIKE", "preposition", ("ARG1", "ARG2"), "'unlike X' → WHERE col != 'X'"),
    "_among_p": Rule("PREP_AMONG", "preposition", ("ARG1", "ARG2"), "'among the top 10' → IN or LIMIT"),
    "_except_p": Rule("PREP_EXCEPT", "preposition", ("ARG1", "ARG2"), "'except biology' → WHERE != or EXCEPT operation"),
    "_besides_p": Rule("PREP_BESIDES", "preposition", ("ARG1", "ARG2"), "'besides math' → additional to"),
    "_including_p": Rule("PREP_INCLUDING", "preposition", ("ARG1", "ARG2"), "'including math' → IN set with 'math'"),
    "_excluding_p": Rule("PREP_EXCLUDING", "preposition", ("ARG1", "ARG2"), "'excluding math' → WHERE col != 'math'"),
    "_within_p": Rule("PREP_WITHIN", "preposition", ("ARG1", "ARG2"), "'within 10 miles' → range comparison"),
    "_across_p": Rule("PREP_ACROSS", "preposition", ("ARG1", "ARG2"), "'across departments' → GROUP BY or span all"),
    "_through_p": Rule("PREP_THROUGH", "preposition", ("ARG1", "ARG2"), "'through 2020' → temporal range endpoint"),
    "_to_p": Rule("PREP_TO", "preposition", ("ARG1", "ARG2"), "'up to 100' → <= 100, or directional"),
    "_into_p": Rule("PREP_INTO", "preposition", ("ARG1", "ARG2"), "'into groups' → GROUP BY"),
    "_on_p_loc": Rule("PREP_ON", "preposition", ("ARG1", "ARG2"), "'on Monday' → WHERE day = 'Monday'"),
    "_on_p_temp": Rule("PREP_ON_TEMP", "preposition", ("ARG1", "ARG2"), "'on January 1st' → WHERE date = '...'"),
    "_at_p": Rule("PREP_AT", "preposition", ("ARG1", "ARG2"), "'at the university' → WHERE"),
    "_about_p": Rule("PREP_ABOUT", "preposition", ("ARG1", "ARG2"), "'about the student' → related to"),
    "_according+to_p": Rule("PREP_ACCORDING_TO", "preposition", ("ARG1", "ARG2"), "'according to score' → ORDER BY"),
    "_based+on_p": Rule("PREP_BASED_ON", "preposition", ("ARG1", "ARG2"), "'based on enrollment' → derived from column"),
    "_due+to_p": Rule("PREP_DUE_TO", "preposition", ("ARG1", "ARG2"), "Causal — rarely SQL-relevant"),
    "_along+with_p": Rule("PREP_ALONG_WITH", "preposition", ("ARG1", "ARG2"), "'along with courses' → JOIN"),
    "_together+with_p": Rule("PREP_TOGETHER_WITH", "preposition", ("ARG1", "ARG2"), "'together with courses' → JOIN"),
}

# =============================================================================
# CATEGORY 6: SET OPERATIONS
# =============================================================================

_SET_OP_RULES_RAW: Dict[str, Rule] = {
    # Compound rules (marked with compound=True)
    "BOTH_AND": Rule("INTERSECT", "set_op", (), "'both CS and Math' → INTERSECT", compound=True),
    "EITHER_OR": Rule("UNION", "set_op", (), "'either CS or Math' → UNION", compound=True),
    "BUT_NOT": Rule("EXCEPT", "set_op", (), "'CS but not Math' → EXCEPT", compound=True),
    "_other+than_p": Rule("EXCEPT", "set_op", ("ARG1", "ARG2"), "'other than biology' → EXCEPT or WHERE !="),
    "_apart+from_p": Rule("EXCEPT", "set_op", ("ARG1", "ARG2"), "'apart from math' → same"),
    "_too_a_1": Rule("UNION_ADD", "set_op", ("ARG1",), "'math too' → UNION additional"),
    "_in+addition+to_p": Rule("UNION_ADD", "set_op", ("ARG1", "ARG2"), "'in addition to CS' → UNION"),
    "_instead+of_p": Rule("REPLACE", "set_op", ("ARG1", "ARG2"), "'instead of CS' → substitute condition"),
}

# =============================================================================
# CATEGORY 7: MODIFIERS (query structure)
# =============================================================================

_MODIFIER_RULES_RAW: Dict[str, Rule] = {
    "_different_a_1": Rule("DISTINCT", "modifier", ("ARG1",), "'different countries' → SELECT DISTINCT"),
    "_distinct_a_1": Rule("DISTINCT", "modifier", ("ARG1",), "'distinct values' → SELECT DISTINCT"),
    "_unique_a_1": Rule("DISTINCT", "modifier", ("ARG1",), "'unique names' → SELECT DISTINCT"),
    "_various_a_1": Rule("DISTINCT", "modifier", ("ARG1",), "'various departments' → SELECT DISTINCT"),
    "_same_a_1": Rule("SELF_JOIN_EQ", "modifier", ("ARG1", "ARG2"), "'same department' → self-join WHERE a.col = b.col"),
    "_identical_a_1": Rule("SELF_JOIN_EQ", "modifier", ("ARG1", "ARG2"), "'identical scores' → same"),
    "_other_a_1": Rule("NOT_EQUAL", "modifier", ("ARG1",), "'other students' → WHERE id != ref_id"),
    "_another_a_1": Rule("NOT_EQUAL", "modifier", ("ARG1",), "'another department' → WHERE id != ref_id"),
    "_first_a_1": Rule("ORDINAL_FIRST", "modifier", ("ARG1",), "'first 10' → ORDER BY ASC LIMIT 10"),
    "_last_a_1": Rule("ORDINAL_LAST", "modifier", ("ARG1",), "'last 10' → ORDER BY DESC LIMIT 10"),
    "_top_a_1": Rule("ORDINAL_TOP", "modifier", ("ARG1",), "'top 5' → ORDER BY DESC LIMIT 5"),
    "_bottom_a_1": Rule("ORDINAL_BOTTOM", "modifier", ("ARG1",), "'bottom 5' → ORDER BY ASC LIMIT 5"),
    "_second_a_1": Rule("ORDINAL_NTH", "modifier", ("ARG1",), "'second highest' → OFFSET 1 LIMIT 1"),
    "_third_a_1": Rule("ORDINAL_NTH", "modifier", ("ARG1",), "'third oldest' → OFFSET 2 LIMIT 1"),
    "_ascending_a_1": Rule("ORDER_ASC", "modifier", (), "Explicit sort direction ASC"),
    "_descending_a_1": Rule("ORDER_DESC", "modifier", (), "Explicit sort direction DESC"),
    "_alphabetical_a_1": Rule("ORDER_ASC_TEXT", "modifier", ("ARG1",), "'alphabetical order' → ORDER BY col ASC"),
    "_chronological_a_1": Rule("ORDER_ASC_DATE", "modifier", ("ARG1",), "'chronological order' → ORDER BY date ASC"),
    "_reverse_a_1": Rule("ORDER_REVERSE", "modifier", (), "'reverse order' → flip sort direction"),
    "_remaining_a_1": Rule("COMPLEMENT", "modifier", ("ARG1",), "'remaining students' → NOT in previous result"),
    "_respective_a_1": Rule("CORRELATED", "modifier", (), "'their respective depts' → correlated reference"),
    "_corresponding_a_1": Rule("CORRELATED", "modifier", ("ARG1",), "'the corresponding course' → correlated JOIN"),
    "_available_a_1": Rule("NOT_NULL", "modifier", ("ARG1",), "'available scores' → WHERE score IS NOT NULL"),
    "_missing_a_1": Rule("IS_NULL", "modifier", ("ARG1",), "'missing values' → WHERE col IS NULL"),
    "_empty_a_1": Rule("IS_NULL_OR_EMPTY", "modifier", ("ARG1",), "'empty fields' → WHERE IS NULL OR = ''"),
    "_null_a_1": Rule("IS_NULL", "modifier", ("ARG1",), "'null values' → WHERE col IS NULL"),
    "_duplicate_a_1": Rule("HAVING_GT_1", "modifier", ("ARG1",), "'duplicate entries' → GROUP BY HAVING COUNT(*) > 1"),
    "_common_a_1": Rule("INTERSECT_SHARED", "modifier", ("ARG1",), "'common courses' → INTERSECT or JOIN"),
    "_random_a_1": Rule("ORDER_RANDOM", "modifier", (), "'random students' → ORDER BY RANDOM() LIMIT n"),
    "_consecutive_a_1": Rule("WINDOW_SEQUENCE", "modifier", ("ARG1",), "'consecutive days' → window function"),
    "_latest_a_1": Rule("ORDER_DESC_DATE", "modifier", ("ARG1",), "'latest enrollment' → ORDER BY date DESC LIMIT 1"),
    "_earliest_a_1": Rule("ORDER_ASC_DATE", "modifier", ("ARG1",), "'earliest enrollment' → ORDER BY date ASC LIMIT 1"),
    "_newest_a_1": Rule("ORDER_DESC_DATE", "modifier", ("ARG1",), "Same as latest"),
    "_oldest_a_1": Rule("ORDER_ASC_DATE_OR_AGE", "modifier", ("ARG1",), "Ambiguous: age DESC or date ASC"),
    "_recent_a_1": Rule("ORDER_DESC_DATE", "modifier", ("ARG1",), "'recent enrollments' → ORDER BY date DESC"),
    "_previous_a_1": Rule("TEMPORAL_PRIOR", "modifier", ("ARG1",), "'previous semester' → date range before current"),
    "_next_a_1": Rule("TEMPORAL_NEXT", "modifier", ("ARG1",), "'next semester' → date range after current"),
    "_current_a_1": Rule("TEMPORAL_CURRENT", "modifier", ("ARG1",), "'current students' → WHERE status = 'active'"),
    "_active_a_1": Rule("BOOLEAN_TRUE", "modifier", ("ARG1",), "'active students' → WHERE active = TRUE"),
    "_inactive_a_1": Rule("BOOLEAN_FALSE", "modifier", ("ARG1",), "'inactive students' → WHERE active = FALSE"),
}

# =============================================================================
# CATEGORY 8: SPECIAL VERBS
# =============================================================================

_VERB_RULES_RAW: Dict[str, Rule] = {
    # Query-framing verbs
    "_show_v_1": Rule("SELECT_FRAME", "verb", ("ARG1", "ARG2"), "'show me X' → SELECT"),
    "_find_v_1": Rule("SELECT_FRAME", "verb", ("ARG1", "ARG2"), "'find all X' → SELECT"),
    "_list_v_1": Rule("SELECT_FRAME", "verb", ("ARG1", "ARG2"), "'list the X' → SELECT"),
    "_give_v_1": Rule("SELECT_FRAME", "verb", ("ARG1", "ARG2"), "'give me X' → SELECT"),
    "_get_v_1": Rule("SELECT_FRAME", "verb", ("ARG1", "ARG2"), "'get the X' → SELECT"),
    "_return_v_1": Rule("SELECT_FRAME", "verb", ("ARG1", "ARG2"), "'return all X' → SELECT"),
    "_display_v_1": Rule("SELECT_FRAME", "verb", ("ARG1", "ARG2"), "'display the X' → SELECT"),
    "_report_v_1": Rule("SELECT_FRAME", "verb", ("ARG1", "ARG2"), "'report the X' → SELECT"),
    "_provide_v_1": Rule("SELECT_FRAME", "verb", ("ARG1", "ARG2"), "'provide a list' → SELECT"),
    "_retrieve_v_1": Rule("SELECT_FRAME", "verb", ("ARG1", "ARG2"), "'retrieve records' → SELECT"),
    "_tell_v_1": Rule("SELECT_FRAME", "verb", ("ARG1", "ARG2"), "'tell me X' → SELECT"),
    "_identify_v_1": Rule("SELECT_FRAME", "verb", ("ARG1", "ARG2"), "'identify X' → SELECT"),
    "_determine_v_1": Rule("SELECT_FRAME", "verb", ("ARG1", "ARG2"), "'determine the X' → SELECT"),
    "_compute_v_1": Rule("SELECT_AGG_FRAME", "verb", ("ARG1", "ARG2"), "'compute the average' → SELECT with AGG"),
    "_calculate_v_1": Rule("SELECT_AGG_FRAME", "verb", ("ARG1", "ARG2"), "'calculate the total' → SELECT with AGG"),
    "_count_v_1": Rule("SELECT_COUNT", "verb", ("ARG1", "ARG2"), "'count the X' → SELECT COUNT(*)"),
    "_sort_v_1": Rule("ORDER_BY", "verb", ("ARG1", "ARG2"), "'sort by age' → ORDER BY age"),
    "_order_v_1": Rule("ORDER_BY", "verb", ("ARG1", "ARG2"), "'order by age' → ORDER BY age"),
    "_rank_v_1": Rule("ORDER_BY_DESC", "verb", ("ARG1", "ARG2"), "'rank by score' → ORDER BY score DESC"),
    "_group_v_1": Rule("GROUP_BY", "verb", ("ARG1", "ARG2"), "'group by dept' → GROUP BY dept"),
    "_compare_v_1": Rule("MULTI_AGG", "verb", ("ARG1", "ARG2"), "'compare X and Y' → side-by-side AGG"),
    "_summarize_v_1": Rule("AGG_SUMMARY", "verb", ("ARG1", "ARG2"), "'summarize by dept' → GROUP BY with AGGs"),
    "_aggregate_v_1": Rule("AGG_GENERIC", "verb", ("ARG1", "ARG2"), "'aggregate the data'"),
    # Semantically meaningful verbs
    "_be_v_id": Rule("COPULA_IDENTITY", "verb", ("ARG1", "ARG2"), "'whose name is John' → WHERE name = 'John'"),
    "_be_v_there": Rule("EXISTENTIAL_THERE", "verb", ("ARG1",), "'there is/are' → EXISTS or COUNT > 0"),
    "_have_v_1": Rule("POSSESSION_JOIN", "verb", ("ARG1", "ARG2"), "'students who have courses' → JOIN via FK"),
    "_contain_v_1": Rule("LIKE_CONTAINS", "verb", ("ARG1", "ARG2"), "'name contains John' → LIKE '%John%'"),
    "_include_v_1": Rule("SET_INCLUDES", "verb", ("ARG1", "ARG2"), "'includes CS101' → IN or JOIN"),
    "_start_v_1": Rule("LIKE_PREFIX", "verb", ("ARG1", "ARG2"), "'starts with A' → LIKE 'A%'"),
    "_begin_v_1": Rule("LIKE_PREFIX", "verb", ("ARG1", "ARG2"), "'begins with A' → LIKE 'A%'"),
    "_end_v_1": Rule("LIKE_SUFFIX", "verb", ("ARG1", "ARG2"), "'ends with ing' → LIKE '%ing'"),
    "_finish_v_1": Rule("LIKE_SUFFIX", "verb", ("ARG1", "ARG2"), "Same as end"),
    "_match_v_1": Rule("EQUALS_OR_LIKE", "verb", ("ARG1", "ARG2"), "'matches pattern' → = or LIKE"),
    "_equal_v_1": Rule("EQUALS", "verb", ("ARG1", "ARG2"), "'equals 100' → WHERE col = 100"),
    "_exceed_v_1": Rule("GREATER_THAN", "verb", ("ARG1", "ARG2"), "'exceeds 100' → WHERE col > 100"),
    "_surpass_v_1": Rule("GREATER_THAN", "verb", ("ARG1", "ARG2"), "'surpasses average' → WHERE col > AVG"),
    "_reach_v_1": Rule("GEQ", "verb", ("ARG1", "ARG2"), "'reaches 100' → WHERE col >= 100"),
    "_differ_v_1": Rule("NOT_EQUALS", "verb", ("ARG1", "ARG2"), "'differs from X' → WHERE col != X"),
    "_vary_v_1": Rule("NOT_EQUALS", "verb", ("ARG1", "ARG2"), "'varies from' → WHERE col !="),
    "_exist_v_1": Rule("EXISTS", "verb", ("ARG1",), "'exists' → EXISTS subquery"),
    "_belong_v_1": Rule("FK_JOIN", "verb", ("ARG1", "ARG2"), "'belongs to dept' → JOIN via FK"),
    "_relate_v_1": Rule("FK_JOIN", "verb", ("ARG1", "ARG2"), "'related to' → JOIN"),
    "_correspond_v_1": Rule("FK_JOIN", "verb", ("ARG1", "ARG2"), "'corresponds to' → JOIN"),
    "_associate_v_1": Rule("FK_JOIN", "verb", ("ARG1", "ARG2"), "'associated with' → JOIN"),
    "_take_v_1": Rule("ACTIVITY_JOIN", "verb", ("ARG1", "ARG2"), "'students who take courses' → JOIN enrollment"),
    "_enroll_v_1": Rule("ACTIVITY_JOIN", "verb", ("ARG1", "ARG2"), "'enrolled in' → JOIN"),
    "_teach_v_1": Rule("ACTIVITY_JOIN", "verb", ("ARG1", "ARG2"), "'teaches the course' → JOIN"),
    "_attend_v_1": Rule("ACTIVITY_JOIN", "verb", ("ARG1", "ARG2"), "'attends the school' → JOIN"),
    "_work_v_1": Rule("ACTIVITY_JOIN", "verb", ("ARG1", "ARG2"), "'works in dept' → JOIN or WHERE"),
    "_live_v_1": Rule("LOCATION_EQ", "verb", ("ARG1", "ARG2"), "'lives in Paris' → WHERE city = 'Paris'"),
    "_reside_v_1": Rule("LOCATION_EQ", "verb", ("ARG1", "ARG2"), "'resides in' → WHERE"),
    "_increase_v_1": Rule("TEMPORAL_CHANGE", "verb", ("ARG1",), "'increased' → window function"),
    "_decrease_v_1": Rule("TEMPORAL_CHANGE", "verb", ("ARG1",), "'decreased' → window function"),
    "_remain_v_1": Rule("UNCHANGED", "verb", ("ARG1",), "'remains same' → WHERE current = previous"),
    "_overlap_v_1": Rule("TEMPORAL_OVERLAP", "verb", ("ARG1", "ARG2"), "'overlaps with' → date range intersection"),
}

# =============================================================================
# CATEGORY 9: ARITHMETIC AND FUNCTIONS
# =============================================================================

_ARITHMETIC_RULES_RAW: Dict[str, Rule] = {
    # Arithmetic operators
    "_plus_p": Rule("ARITH_ADD", "arithmetic", ("ARG1", "ARG2"), "'age plus 5' → col + 5"),
    "_minus_p": Rule("ARITH_SUBTRACT", "arithmetic", ("ARG1", "ARG2"), "'salary minus tax' → salary - tax"),
    "_times_p": Rule("ARITH_MULTIPLY", "arithmetic", ("ARG1", "ARG2"), "'price times quantity' → price * quantity"),
    "_divide_v_1": Rule("ARITH_DIVIDE", "arithmetic", ("ARG1", "ARG2"), "'salary divided by 12' → salary / 12"),
    "_multiply_v_1": Rule("ARITH_MULTIPLY", "arithmetic", ("ARG1", "ARG2"), "'multiply by 100' → * 100"),
    "_add_v_1": Rule("ARITH_ADD", "arithmetic", ("ARG1", "ARG2"), "'add 5 to age' → age + 5"),
    "_subtract_v_1": Rule("ARITH_SUBTRACT", "arithmetic", ("ARG1", "ARG2"), "'subtract tax' → - tax"),
    # String operations
    "_long_a_1": Rule("STRING_LENGTH", "function", ("ARG1",), "'how long is name' → LENGTH(name)"),
    "_short_a_1": Rule("STRING_LENGTH_LT", "function", ("ARG1",), "'short names' → LENGTH(name) < threshold"),
    "_upper_a_1": Rule("STRING_UPPER", "function", ("ARG1",), "'uppercase name' → UPPER(name)"),
    "_lower_a_1": Rule("STRING_LOWER", "function", ("ARG1",), "'lowercase name' → LOWER(name)"),
    "_combine_v_1": Rule("STRING_CONCAT", "function", ("ARG1", "ARG2"), "'combine first and last' → first || ' ' || last"),
    "_concatenate_v_1": Rule("STRING_CONCAT", "function", ("ARG1", "ARG2"), "'concatenate' → CONCAT or ||"),
    "_trim_v_1": Rule("STRING_TRIM", "function", ("ARG1",), "'trim whitespace' → TRIM(col)"),
    "_replace_v_1": Rule("STRING_REPLACE", "function", ("ARG1", "ARG2", "ARG3"), "'replace X with Y' → REPLACE(col, X, Y)"),
    "_extract_v_1": Rule("EXTRACT_FUNC", "function", ("ARG1", "ARG2"), "'extract the year' → EXTRACT(YEAR FROM date)"),
    # Date/time operations
    "_year_n_1": Rule("TEMPORAL_YEAR", "function", ("ARG1",), "'the year of enrollment' → YEAR(date)"),
    "_month_n_1": Rule("TEMPORAL_MONTH", "function", ("ARG1",), "'the month' → MONTH(date)"),
    "_day_n_1": Rule("TEMPORAL_DAY", "function", ("ARG1",), "'the day' → DAY(date)"),
    "_week_n_1": Rule("TEMPORAL_WEEK", "function", ("ARG1",), "'the week' → WEEK(date)"),
    "_hour_n_1": Rule("TEMPORAL_HOUR", "function", ("ARG1",), "'the hour' → HOUR(time)"),
    "_age_n_1": Rule("TEMPORAL_AGE", "function", ("ARG1",), "'age' → datediff or column"),
    "dofm": Rule("DATE_DAY", "function", (), "ERG day-of-month in date expressions"),
    "mofy": Rule("DATE_MONTH", "function", (), "ERG month-of-year"),
    "yofc": Rule("DATE_YEAR", "function", (), "ERG year-of-century"),
    "season": Rule("DATE_SEASON", "function", (), "ERG season (spring/summer/fall/winter)"),
    "_today_a_1": Rule("CURRENT_DATE", "function", (), "'today' → CURRENT_DATE"),
    "_yesterday_a_1": Rule("DATE_MINUS_1", "function", (), "'yesterday' → CURRENT_DATE - 1"),
    "_tomorrow_a_1": Rule("DATE_PLUS_1", "function", (), "'tomorrow' → CURRENT_DATE + 1"),
    "_ago_p": Rule("DATE_AGO", "function", ("ARG1", "ARG2"), "'3 days ago' → CURRENT_DATE - INTERVAL '3 days'"),
}

# =============================================================================
# CATEGORY 10: VALUES AND LITERALS
# =============================================================================

_VALUE_RULES_RAW: Dict[str, Rule] = {
    "card": Rule("NUMERIC_LITERAL", "value", (), "Cardinal number, CARG = value"),
    "ord": Rule("ORDINAL", "value", (), "Ordinal number 'first' → 1, 'second' → 2"),
    "named": Rule("STRING_LITERAL", "value", (), "Named entity, CARG = name string"),
    "_true_a_1": Rule("BOOLEAN_TRUE", "value", (), "→ WHERE col = TRUE or 1"),
    "_false_a_1": Rule("BOOLEAN_FALSE", "value", (), "→ WHERE col = FALSE or 0"),
    "_yes_a_1": Rule("BOOLEAN_TRUE", "value", (), "→ TRUE"),
    "_no_a_1": Rule("BOOLEAN_FALSE", "value", (), "→ FALSE (not the quantifier!)"),
    "_unknown_a_1": Rule("IS_NULL", "value", ("ARG1",), "'unknown value' → WHERE col IS NULL"),
    "_blank_a_1": Rule("IS_NULL_OR_EMPTY", "value", ("ARG1",), "'blank field' → WHERE IS NULL OR = ''"),
    "_zero_a_1": Rule("NUMERIC_ZERO", "value", (), "→ WHERE col = 0 or COUNT = 0"),
    "string": Rule("STRING_TYPE", "value", (), "ERG abstract predicate for quoted string literals"),
}

# =============================================================================
# CATEGORY 11: COMPOUND PATTERNS (multi-predicate detection)
# =============================================================================

# These are descriptions of compound patterns, not simple predicate rules
# The compiler must detect these by examining combinations of predicates
COMPOUND_PATTERNS: List[str] = [
    "RELATIVE_CLAUSE: verb sharing variable with main clause noun → JOIN or subquery",
    "EXISTENTIAL_THERE: _be_v_there + _there_q → SELECT EXISTS(...) or COUNT > 0",
    "POSSESSIVE_JOIN: _have_v_1 linking two table entities → JOIN via FK",
    "PASSIVE_VOICE: parg_d link or passive derivation → argument reordering",
    "NOMINALIZATION: verb event as noun argument → subquery",
    "COUNT_PER_GROUP: much-many_a + (_per_p | _each_q | _for_p) → COUNT(*) GROUP BY",
    "HAVING_PATTERN: comparison scoping over aggregation → HAVING instead of WHERE",
    "SUPERLATIVE_RELATIVE: superl + relative clause → ORDER BY AGG DESC LIMIT 1",
    "COPULA_EQUALITY: _be_v_id + named entity/cardinal → WHERE col = value",
    "OR_IN_LIST: _or_c coordinating values → WHERE col IN (x, y)",
    "CONDITIONAL: _if_x_then → CASE WHEN ... THEN ... ELSE ... END",
    "WINDOW_RANK: ord + superl → ROW_NUMBER() OVER or OFFSET",
    "SELF_JOIN: _same_a_1 or _pair_n_1 on same table → self-join",
    "NEGATED_EXISTENCE: neg + _have_v_1 or _without_p → LEFT JOIN ... IS NULL or NOT EXISTS",
    "MULTI_AGGREGATION: multiple AGG predicates → SELECT COUNT(*), AVG(...), MAX(...)",
    "NESTED_AGGREGATION: AGG whose argument is itself an AGG → subquery",
    "MULTI_GROUP_BY: multiple _per_p / _each_q → GROUP BY col1, col2",
    "SUBQUERY_IN_WHERE: comparison with quantified AGG as ARG2 → WHERE col > (SELECT AGG...)",
    "CORRELATED_SUBQUERY: inner query references outer variable → EXISTS with correlation",
    "UNIVERSAL_QUANTIFICATION: _every_q / _all_q → NOT EXISTS(... WHERE NOT ...)",
    "RANGE_CONSTRAINT: _at+least_x_deg + _and_c + _at+most_x_deg → BETWEEN N AND M",
    "DEFAULT_VALUE: conditional with null check → COALESCE(col, default)",
    "PERCENTAGE: _percentage_n_1 + _of_p + filtered entity → COUNT(filtered)*100.0/COUNT(*)",
]

# =============================================================================
# CATEGORY 12: SENTENCE FORCE (variable properties)
# =============================================================================

# These are not predicates but properties on variables (SF: ques, SF: prop, etc.)
# They don't get predicate rules, but the compiler checks them
SENTENCE_FORCE_TYPES: Dict[str, str] = {
    "ques": "QUESTION - interrogative, return result set",
    "prop": "STATEMENT - declarative/imperative",
    "comm": "COMMAND - imperative 'Find...', same SQL as question",
    "prop-or-ques": "AMBIGUOUS_FORCE - treat as question",
}

# =============================================================================
# BUILD MASTER RULE DICTIONARIES
# =============================================================================

# Intern all keys and freeze
QUANTIFIER_RULES: MappingProxyType[str, Rule] = MappingProxyType(_intern_keys(_QUANTIFIER_RULES_RAW))
COMPARISON_RULES: MappingProxyType[str, Rule] = MappingProxyType(_intern_keys(_COMPARISON_RULES_RAW))
AGGREGATION_RULES: MappingProxyType[str, Rule] = MappingProxyType(_intern_keys(_AGGREGATION_RULES_RAW))
CONNECTIVE_RULES: MappingProxyType[str, Rule] = MappingProxyType(_intern_keys(_CONNECTIVE_RULES_RAW))
PREPOSITION_RULES: MappingProxyType[str, Rule] = MappingProxyType(_intern_keys(_PREPOSITION_RULES_RAW))
SET_OP_RULES: MappingProxyType[str, Rule] = MappingProxyType(_intern_keys(_SET_OP_RULES_RAW))
MODIFIER_RULES: MappingProxyType[str, Rule] = MappingProxyType(_intern_keys(_MODIFIER_RULES_RAW))
VERB_RULES: MappingProxyType[str, Rule] = MappingProxyType(_intern_keys(_VERB_RULES_RAW))
ARITHMETIC_RULES: MappingProxyType[str, Rule] = MappingProxyType(_intern_keys(_ARITHMETIC_RULES_RAW))
VALUE_RULES: MappingProxyType[str, Rule] = MappingProxyType(_intern_keys(_VALUE_RULES_RAW))

# Master lookup combining all rule types (check for collisions)
_all_rules_combined: Dict[str, Rule] = {}
for rule_dict in [
    QUANTIFIER_RULES,
    COMPARISON_RULES,
    AGGREGATION_RULES,
    CONNECTIVE_RULES,
    PREPOSITION_RULES,
    SET_OP_RULES,
    MODIFIER_RULES,
    VERB_RULES,
    ARITHMETIC_RULES,
    VALUE_RULES,
]:
    for key, rule in rule_dict.items():
        if key in _all_rules_combined:
            # Collision - keep rule with higher priority
            existing = _all_rules_combined[key]
            if rule.priority > existing.priority:
                _all_rules_combined[key] = rule
        else:
            _all_rules_combined[key] = rule

ALL_RULES: MappingProxyType[str, Rule] = MappingProxyType(_all_rules_combined)

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def lookup_rule(predicate: str) -> Optional[Rule]:
    """
    Look up a structural rule for a DMRS predicate.

    Lookup order:
    1. Exact match
    2. Strip _rel suffix, retry
    3. Strip sense number (e.g. _old_a_1 → _old_a), retry
    4. Return None (content word, handled by schema linker)

    Args:
        predicate: DMRS predicate name (e.g., "which_q", "_old_a_1", "comp")

    Returns:
        Rule object or None if not found
    """
    # 1. Exact match
    if predicate in ALL_RULES:
        return ALL_RULES[predicate]

    # 2. Strip _rel suffix
    if predicate.endswith("_rel"):
        pred_no_rel = predicate[:-4]
        if pred_no_rel in ALL_RULES:
            return ALL_RULES[pred_no_rel]

    # 3. Strip sense number (e.g. _old_a_1 → _old_a)
    # Match pattern: _lemma_pos_sense
    match = re.match(r"^(_[^_]+_[a-z])_\d+(_rel)?$", predicate)
    if match:
        pred_no_sense = match.group(1)
        if pred_no_sense in ALL_RULES:
            return ALL_RULES[pred_no_sense]

    # 4. Not found — content word
    return None


def classify_predicate(predicate: str) -> str:
    """
    Classify a DMRS predicate by category.

    Returns one of: 'quantifier', 'comparison', 'aggregation', 'connective',
    'preposition', 'set_op', 'modifier', 'verb', 'arithmetic', 'value',
    'construction', 'content_noun', 'content_verb', 'content_adj', 'unknown'.

    Args:
        predicate: DMRS predicate name

    Returns:
        Category string
    """
    rule = lookup_rule(predicate)

    if rule:
        return rule.category

    # No rule found — classify by POS if it's a lexical predicate
    if predicate.startswith("_") and "_" in predicate[1:]:
        # Pattern: _lemma_pos_sense
        parts = predicate.split("_")
        if len(parts) >= 3:
            pos = parts[2]
            if pos == "n":
                return "content_noun"
            elif pos == "v":
                return "content_verb"
            elif pos == "a" or pos == "aj":
                return "content_adj"
            elif pos == "p":
                return "content_prep"

    return "unknown"


def describe_rule(predicate: str) -> str:
    """
    Return a human-readable English explanation of a rule.

    For audit trail compliance (EU AI Act Article 13).

    Args:
        predicate: DMRS predicate name

    Returns:
        Human-readable description string
    """
    rule = lookup_rule(predicate)

    if not rule:
        return f"Content word '{predicate}' — handled by schema linker, not structural rules"

    return f"{predicate} → {rule.sql_op}: {rule.notes}"


def get_rules_by_category(category: str) -> Dict[str, Rule]:
    """
    Return all rules in a given category.

    Args:
        category: Category name (e.g., "quantifier", "comparison", "aggregation")

    Returns:
        Dictionary of predicate → Rule for rules in that category
    """
    return {
        pred: rule
        for pred, rule in ALL_RULES.items()
        if rule.category == category
    }


def get_compound_rules() -> List[str]:
    """
    Return the list of compound pattern descriptions.

    These are multi-predicate patterns that the compiler must detect
    by examining DMRS structure, not single-predicate lookups.

    Returns:
        List of human-readable compound pattern descriptions
    """
    return COMPOUND_PATTERNS.copy()


def get_rule_count() -> int:
    """Return the total number of defined rules."""
    return len(ALL_RULES)


def get_categories() -> FrozenSet[str]:
    """Return the set of all rule categories."""
    return frozenset(rule.category for rule in ALL_RULES.values())


# Legacy compatibility functions (for existing code that uses the old API)
def get_rule(predicate: str) -> Optional[Dict[str, str]]:
    """
    Look up a rule (legacy API, returns dict not Rule object).

    DEPRECATED: Use lookup_rule() instead.
    """
    rule = lookup_rule(predicate)
    if rule:
        return {"sql_op": rule.sql_op, "notes": rule.notes}
    return None


def is_quantifier(predicate: str) -> bool:
    """Check if predicate is a quantifier."""
    return predicate in QUANTIFIER_RULES


def is_comparison(predicate: str) -> bool:
    """Check if predicate is a comparison operator."""
    return predicate in COMPARISON_RULES


def is_aggregation(predicate: str) -> bool:
    """Check if predicate is an aggregation function."""
    return predicate in AGGREGATION_RULES


def is_connective(predicate: str) -> bool:
    """Check if predicate is a logical connective."""
    return predicate in CONNECTIVE_RULES


def is_construction(predicate: str) -> bool:
    """Check if predicate is a special construction (legacy)."""
    rule = lookup_rule(predicate)
    return rule is not None and rule.category == "verb"


def is_preposition(predicate: str) -> bool:
    """Check if predicate is a preposition."""
    return predicate in PREPOSITION_RULES
