"""The first pipeline, kept as it was and called from nowhere: question -> ACE with a schema lexicon -> DMRS -> schema fit -> linking ->
compiler -> SQL. It does not run with the ACE binary this repository uses (ACE has no `--extra-lexicon` option, and `ERGParser` cannot
read ACE's output); see SQUID_REPORT.md in the tolk repository. `squid.compile` goes through tolk now (see `squid/__init__.py`)."""

from __future__ import annotations

from delphin import dmrs

from squid.compiler import DMRSCompiler
from squid.disambiguator import disambiguate
from squid.lexicon import write_tdl
from squid.linker import link
from squid.parser import ERGParser, SquidParseError
from squid.schema import Schema


def compile(
    question: str,
    schema: Schema,
    grm_path: str = "erg.dat",
    ace_path: str = "ace",
    n_parses: int = 5,
    max_chart_megabytes: int = 1024,
    max_unpack_megabytes: int = 1536,
    max_edges: int = 50000,
    timeout: float = 30.0,
    dialect: str = "sqlite",
) -> str:
    """
    Compile an English question to SQL.

    This is the main entry point. It runs the full pipeline:
    question → parse → disambiguate → link → compile → SQL

    Args:
        question: Natural language question
        schema: Database schema
        grm_path: Path to ERG grammar image (default: "erg.dat")
        ace_path: Path to ACE binary (default: "ace")
        n_parses: Number of parses to generate (1-10, default: 5)
        max_chart_megabytes: Max chart memory in MB (default: 1024)
        max_unpack_megabytes: Max unpack memory in MB (default: 1536)
        max_edges: Max chart edges (default: 50000)
        timeout: Parse timeout in seconds (default: 30.0)
        dialect: SQL dialect for sqlglot (default: "sqlite")

    Returns:
        SQL query string

    Raises:
        SquidParseError: If parsing fails
        SquidCompileError: If compilation fails

    Example:
        >>> from squid import compile, Schema
        >>> schema = Schema.from_sqlite("my_database.db")
        >>> sql = compile("How many customers are there?", schema)
        >>> print(sql)
        SELECT COUNT(*) FROM customers
    """
    # Generate domain lexicon
    tdl_path = write_tdl(schema, output_path=None)

    # Parse with ERG
    parser = ERGParser(
        grm_path=grm_path,
        ace_path=ace_path,
        extra_lexicon=str(tdl_path),
        n_parses=n_parses,
        max_chart_megabytes=max_chart_megabytes,
        max_unpack_megabytes=max_unpack_megabytes,
        max_edges=max_edges,
        timeout=timeout,
    )

    try:
        parses = parser.parse_to_dmrs(question)
    except Exception as e:
        raise SquidParseError(f"ERG could not parse: {question!r}") from e

    if not parses:
        raise SquidParseError(f"ERG could not parse: {question!r}")

    # Disambiguate by schema fit
    best = disambiguate(parses, schema)

    # Link predicates to schema
    links = link(best, schema)

    # Compile to SQL
    compiler = DMRSCompiler(schema, links)
    return compiler.compile(best, dialect=dialect)


def from_dmrs(dmrs_obj: dmrs.Dmrs, schema: Schema, dialect: str = "sqlite") -> str:
    """
    Compile a pre-parsed DMRS to SQL.

    For users who want to handle parsing themselves.

    Args:
        dmrs_obj: DMRS parse
        schema: Database schema
        dialect: SQL dialect for sqlglot (default: "sqlite")

    Returns:
        SQL query string

    Raises:
        SquidCompileError: If compilation fails

    Example:
        >>> from squid import from_dmrs, Schema
        >>> from delphin import dmrs
        >>> # ... parse question to get dmrs_obj ...
        >>> schema = Schema.from_sqlite("my_database.db")
        >>> sql = from_dmrs(dmrs_obj, schema)
    """
    links = link(dmrs_obj, schema)
    compiler = DMRSCompiler(schema, links)
    return compiler.compile(dmrs_obj, dialect=dialect)
