"""
Schema-based parse disambiguation.

Scores DMRS parses by how well their predicates match the database schema.
This replaces the ERG's MaxEnt parse ranker with a fully rule-based approach.
"""

from __future__ import annotations

from typing import List

from delphin import dmrs

from squid import rules
from squid.linker import link
from squid.schema import Schema


def score_parse(dmrs_obj: dmrs.Dmrs, schema: Schema) -> float:
    """
    Score a DMRS parse by schema fit.

    Scoring rubric:
    - Predicate matches a table name: +1.0
    - Predicate matches a column name: +0.8
    - Predicate matches a known DB value: +0.6
    - Predicate is a function word (quantifier, comparison, etc.): 0.0 (neutral)
    - Predicate is an unknown content word with no schema match: -0.5

    Higher score = better match to schema.

    Args:
        dmrs_obj: DMRS parse to score
        schema: Database schema

    Returns:
        Score (float)
    """
    score = 0.0

    # Get schema links for this parse
    links = link(dmrs_obj, schema)

    # Score each node in the DMRS
    for node in dmrs_obj.nodes:
        node_id = str(node.id)
        pred = str(node.predicate)

        # Check if this is a function word (quantifier, comparison, connective, etc.)
        if rules.is_quantifier(pred):
            score += 0.0  # Neutral
            continue
        if rules.is_comparison(pred):
            score += 0.0  # Neutral
            continue
        if rules.is_aggregation(pred):
            score += 0.2  # Slight bonus for having aggregation
            continue
        if rules.is_connective(pred):
            score += 0.0  # Neutral
            continue
        if rules.is_construction(pred):
            score += 0.0  # Neutral
            continue
        if rules.is_preposition(pred):
            score += 0.0  # Neutral
            continue

        # This is a content word - check if it's linked to schema
        if node_id in links:
            link_obj = links[node_id]

            if link_obj.element_type == 'table':
                score += 1.0 * link_obj.score
            elif link_obj.element_type == 'column':
                score += 0.8 * link_obj.score
            elif link_obj.element_type == 'value':
                score += 0.6 * link_obj.score
        else:
            # Content word with no schema match
            # Only penalize if it's a lexical predicate (starts with _)
            if pred.startswith('_'):
                score -= 0.5

    return score


def disambiguate(parses: List[dmrs.Dmrs], schema: Schema) -> dmrs.Dmrs:
    """
    Select the best parse from N-best list based on schema fit.

    Args:
        parses: List of DMRS parses
        schema: Database schema

    Returns:
        Best DMRS parse

    Raises:
        ValueError: If parses list is empty
    """
    if not parses:
        raise ValueError("Cannot disambiguate empty parse list")

    if len(parses) == 1:
        return parses[0]

    # Score all parses
    scored_parses: List[tuple[float, dmrs.Dmrs]] = []
    for parse in parses:
        score = score_parse(parse, schema)
        scored_parses.append((score, parse))

    # Sort by score (descending)
    scored_parses.sort(key=lambda x: x[0], reverse=True)

    # Return the best parse
    return scored_parses[0][1]


def disambiguate_with_score(
    parses: List[dmrs.Dmrs],
    schema: Schema
) -> tuple[dmrs.Dmrs, float]:
    """
    Select the best parse and return its score.

    Args:
        parses: List of DMRS parses
        schema: Database schema

    Returns:
        (best_parse, score) tuple
    """
    if not parses:
        raise ValueError("Cannot disambiguate empty parse list")

    if len(parses) == 1:
        score = score_parse(parses[0], schema)
        return (parses[0], score)

    # Score all parses
    scored_parses: List[tuple[float, dmrs.Dmrs]] = []
    for parse in parses:
        score = score_parse(parse, schema)
        scored_parses.append((score, parse))

    # Sort by score (descending)
    scored_parses.sort(key=lambda x: x[0], reverse=True)

    # Return the best parse and its score
    return scored_parses[0]


def rank_parses(parses: List[dmrs.Dmrs], schema: Schema) -> List[tuple[dmrs.Dmrs, float]]:
    """
    Rank all parses by schema fit score.

    Args:
        parses: List of DMRS parses
        schema: Database schema

    Returns:
        List of (parse, score) tuples, sorted by score (descending)
    """
    scored_parses: List[tuple[dmrs.Dmrs, float]] = []
    for parse in parses:
        score = score_parse(parse, schema)
        scored_parses.append((parse, score))

    # Sort by score (descending)
    scored_parses.sort(key=lambda x: x[1], reverse=True)

    return scored_parses
