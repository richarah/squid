"""The two errors SQUID raises: a question the schema cannot answer, and a sentence the parser cannot read."""


class SquidParseError(Exception):
    """The question could not be read."""


class SquidCompileError(Exception):
    """The question is not one the schema can answer. The message carries tolk's refusal code and reason."""
