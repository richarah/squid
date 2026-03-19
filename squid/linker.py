"""
Schema linking: connect DMRS predicates to schema elements.

Uses fuzzy matching, lemmatization, and inflection normalization to link
linguistic predicates to database tables, columns, and values.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import inflect
from delphin import dmrs
from lemminflect import getLemma
from rapidfuzz import fuzz, process

from squid.schema import Schema

# Fuzzy matching threshold (0-100)
FUZZY_THRESHOLD: int = 85

# Initialize inflect engine for pluralization/singularization
_inflect_engine = inflect.engine()


@dataclass(slots=True)
class SchemaLink:
    """A link between a DMRS predicate and a schema element."""

    predicate: str  # DMRS predicate, e.g. "_student_n_1"
    element_type: str  # "table", "column", or "value"
    table: str  # e.g. "students"
    column: Optional[str] = None  # e.g. "name" (None for table-level links)
    value: Optional[str] = None  # for value matches
    score: float = 1.0  # matching confidence (0.0-1.0)


def extract_lemma_from_predicate(predicate: str) -> str:
    """
    Extract the lemma from a DMRS predicate.

    Examples:
        "_student_n_1" -> "student"
        "_sing_v_1" -> "sing"
        "proper_q" -> "proper_q" (no change for non-lexical predicates)

    Args:
        predicate: DMRS predicate string

    Returns:
        Lemma string
    """
    # Most lexical predicates follow the pattern: _lemma_pos_sense
    if predicate.startswith('_') and predicate.count('_') >= 2:
        parts = predicate.split('_')
        # Return the lemma (second part)
        return parts[1] if len(parts) > 1 else predicate
    else:
        # Non-lexical predicate (quantifier, etc.)
        return predicate


def normalize_inflection(word: str) -> List[str]:
    """
    Generate inflectional variants of a word.

    Args:
        word: Input word

    Returns:
        List of variants (includes original, singular, plural)
    """
    variants: List[str] = [word]

    # Try pluralization
    plural = _inflect_engine.plural(word)
    if plural and plural != word:
        variants.append(plural)

    # Try singularization
    singular = _inflect_engine.singular_noun(word)
    if singular and singular != word and isinstance(singular, str):
        variants.append(singular)

    return list(set(variants))


def normalize_lemma(word: str) -> List[str]:
    """
    Get lemmatized forms of a word.

    Args:
        word: Input word

    Returns:
        List of lemmas
    """
    lemmas: List[str] = [word]

    # Try noun lemmatization
    noun_lemmas = getLemma(word, upos='NOUN')
    if noun_lemmas:
        lemmas.extend(noun_lemmas)

    # Try verb lemmatization
    verb_lemmas = getLemma(word, upos='VERB')
    if verb_lemmas:
        lemmas.extend(verb_lemmas)

    # Try adjective lemmatization
    adj_lemmas = getLemma(word, upos='ADJ')
    if adj_lemmas:
        lemmas.extend(adj_lemmas)

    return list(set(lemmas))


def match_table(
    lemma: str,
    schema: Schema,
    threshold: int = FUZZY_THRESHOLD
) -> Optional[Tuple[str, float]]:
    """
    Match a lemma to a table name.

    Matching cascade:
    1. Exact match
    2. Inflection normalization
    3. Lemmatization
    4. Fuzzy match

    Args:
        lemma: Word to match
        schema: Database schema
        threshold: Fuzzy matching threshold

    Returns:
        (table_name, score) or None
    """
    table_names = schema.table_names()

    # 1. Exact match
    lemma_lower = lemma.lower()
    if schema.has_table(lemma_lower):
        return (lemma_lower, 1.0)

    # 2. Inflection normalization
    variants = normalize_inflection(lemma)
    for variant in variants:
        if schema.has_table(variant.lower()):
            return (variant.lower(), 0.95)

    # 3. Lemmatization
    lemmas = normalize_lemma(lemma)
    for lem in lemmas:
        if schema.has_table(lem.lower()):
            return (lem.lower(), 0.9)

    # 4. Fuzzy match
    result = process.extractOne(
        lemma,
        table_names,
        scorer=fuzz.ratio,
        score_cutoff=threshold
    )

    if result:
        matched_table, score, _ = result
        return (matched_table, score / 100.0)

    return None


def match_column(
    lemma: str,
    schema: Schema,
    table_hint: Optional[str] = None,
    threshold: int = FUZZY_THRESHOLD
) -> Optional[Tuple[str, str, float]]:
    """
    Match a lemma to a column name.

    Args:
        lemma: Word to match
        schema: Database schema
        table_hint: Optional table name to restrict search
        threshold: Fuzzy matching threshold

    Returns:
        (table_name, column_name, score) or None
    """
    # Build list of (table, column) pairs to search
    candidates: List[Tuple[str, str]] = []

    if table_hint and schema.has_table(table_hint):
        # Search only in specified table
        for col in schema.column_names(table_hint):
            candidates.append((table_hint, col))
    else:
        # Search all columns in all tables
        for table in schema.tables:
            for col in table.columns:
                candidates.append((table.name, col.name))

    # Build flat list of column names for matching
    column_names = [col for _, col in candidates]

    # 1. Exact match
    lemma_lower = lemma.lower()
    for table, col in candidates:
        if col == lemma_lower:
            return (table, col, 1.0)

    # 2. Inflection normalization
    variants = normalize_inflection(lemma)
    for variant in variants:
        for table, col in candidates:
            if col == variant.lower():
                return (table, col, 0.95)

    # 3. Lemmatization
    lemmas = normalize_lemma(lemma)
    for lem in lemmas:
        for table, col in candidates:
            if col == lem.lower():
                return (table, col, 0.9)

    # 4. Fuzzy match
    result = process.extractOne(
        lemma,
        column_names,
        scorer=fuzz.ratio,
        score_cutoff=threshold
    )

    if result:
        matched_col, score, idx = result
        # Find the table for this column
        table = candidates[idx][0]
        return (table, matched_col, score / 100.0)

    return None


def match_multiword(
    lemmas: List[str],
    schema: Schema,
    threshold: int = FUZZY_THRESHOLD
) -> Optional[SchemaLink]:
    """
    Match a sequence of lemmas to a multi-word table or column name.

    Example: ["singer", "id"] -> column "singer_id"

    Args:
        lemmas: List of words
        schema: Database schema
        threshold: Fuzzy matching threshold

    Returns:
        SchemaLink or None
    """
    # Try joining with underscore
    joined = '_'.join(lemmas)

    # Try as table name
    table_match = match_table(joined, schema, threshold)
    if table_match:
        table, score = table_match
        return SchemaLink(
            predicate='_'.join(lemmas),
            element_type='table',
            table=table,
            score=score
        )

    # Try as column name
    col_match = match_column(joined, schema, threshold=threshold)
    if col_match:
        table, col, score = col_match
        return SchemaLink(
            predicate='_'.join(lemmas),
            element_type='column',
            table=table,
            column=col,
            score=score
        )

    return None


def link(dmrs_obj: dmrs.Dmrs, schema: Schema) -> Dict[str, SchemaLink]:
    """
    Link each content predicate in the DMRS to a schema element.

    Matching cascade (try in order, take first match above threshold):
    1. Exact match (predicate lemma == table/column name)
    2. Inflection normalization ("students" -> "student" == table "student")
    3. Lemmatization via lemminflect
    4. Fuzzy match via rapidfuzz (threshold: 85)
    5. Multi-word matching (consecutive predicates -> "table_name")

    Args:
        dmrs_obj: DMRS parse
        schema: Database schema

    Returns:
        Dictionary mapping node IDs to SchemaLinks
    """
    links: Dict[str, SchemaLink] = {}

    # Get all nodes in the DMRS
    for node in dmrs_obj.nodes:
        node_id = str(node.id)
        pred = node.predicate

        # Skip non-content predicates (quantifiers, etc.)
        if not pred.startswith('_'):
            continue

        # Extract lemma
        lemma = extract_lemma_from_predicate(str(pred))

        # Try table match
        table_match = match_table(lemma, schema)
        if table_match:
            table, score = table_match
            links[node_id] = SchemaLink(
                predicate=str(pred),
                element_type='table',
                table=table,
                score=score
            )
            continue

        # Try column match
        col_match = match_column(lemma, schema)
        if col_match:
            table, col, score = col_match
            links[node_id] = SchemaLink(
                predicate=str(pred),
                element_type='column',
                table=table,
                column=col,
                score=score
            )
            continue

        # Check for CARG (constant argument) - for named entities and numbers
        if hasattr(node, 'carg') and node.carg:
            # This is a named entity or number
            # Try to match against table/column names first
            carg_table = match_table(node.carg, schema)
            if carg_table:
                table, score = carg_table
                links[node_id] = SchemaLink(
                    predicate=str(pred),
                    element_type='table',
                    table=table,
                    score=score * 0.8  # Lower confidence for CARG matches
                )
                continue

            # Otherwise, treat as a value
            links[node_id] = SchemaLink(
                predicate=str(pred),
                element_type='value',
                table='',  # Unknown table at this point
                value=node.carg,
                score=0.6
            )

    # TODO: Multi-word matching for consecutive nodes
    # This would require analyzing the DMRS graph structure to find
    # adjacent nodes that should be combined (e.g., "singer" + "id" -> "singer_id")

    return links


def get_linked_tables(links: Dict[str, SchemaLink]) -> List[str]:
    """
    Extract all unique tables referenced in the links.

    Args:
        links: Schema links dictionary

    Returns:
        List of unique table names
    """
    tables = set()
    for link in links.values():
        if link.table:
            tables.add(link.table)
    return list(tables)


def get_linked_columns(links: Dict[str, SchemaLink]) -> List[Tuple[str, str]]:
    """
    Extract all (table, column) pairs referenced in the links.

    Args:
        links: Schema links dictionary

    Returns:
        List of (table, column) tuples
    """
    columns = []
    for link in links.values():
        if link.element_type == 'column' and link.column:
            columns.append((link.table, link.column))
    return columns
