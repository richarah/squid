"""Values and names that are in the database are read as those values.

The grammar reads some words as something else: "Ga" is Georgia, "Mo" is Missouri, "Rose" a quality. A query that compared the grammar's
reading would return no rows, and nothing would say why. So each value of the schema that the question contains, written exactly as the
row has it, is given to the parser as an unknown capitalised word (a name it has no reading for) and put back after; and a name in
the result that the question does not contain as written is refused, whatever put it there. What cannot be read as the value is refused."""

from __future__ import annotations

import dataclasses
import re
import string

import tolk

from squid.schema import Schema


def _words(text: str) -> str:
    return text.lower()


def _present(name: str, question: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(name.lower()) + r"(?!\w)", question.lower()) is not None


def _all_values(schema: Schema) -> list[str]:
    return sorted({v for vs in schema.values.values() for v in vs if v and v.strip()}, key=lambda v: (-len(v), v))


def _placeholders(question: str, count: int) -> list[str]:
    """Capitalised letter-only words the question does not contain, one per value."""
    out, i = [], 0
    while len(out) < count:
        name = "Zq" + "".join(string.ascii_lowercase[int(d)] for d in str(i))
        i += 1
        if not _present(name, question) and not any(name.lower() in o.lower() or o.lower() in name.lower() for o in out):
            out.append(name)
    return out


def _consts(x) -> list:
    if isinstance(x, tolk.Describe):
        return [x.entity]
    atoms = list(getattr(x, "body", ())) + [a for alt in getattr(x, "alternatives", ()) for a in alt]
    return [t for a in atoms for t in a.args if isinstance(t, tolk.Const)]


def _rename(x, names: dict[str, str]):
    def term(t):
        return dataclasses.replace(t, id=names[t.id]) if isinstance(t, tolk.Const) and t.id in names else t

    def atoms(group):
        return tuple(dataclasses.replace(a, args=tuple(term(t) for t in a.args)) for a in group)

    if isinstance(x, tolk.Describe):
        return dataclasses.replace(x, entity=term(x.entity))
    return dataclasses.replace(x, body=atoms(x.body), alternatives=tuple(atoms(alt) for alt in x.alternatives))


def read(question: str, schema: Schema, known: frozenset, vocabulary: dict[str, str]):
    """tolk's reading of the question, with each value of the schema in it read as that value; a tolk.Refusal when that cannot be
    guaranteed."""
    wanted = [v for v in _all_values(schema) if re.search(r"(?<!\w)" + re.escape(v) + r"(?!\w)", question)]
    for v in _all_values(schema):
        for m in re.finditer(r"(?<!\w)" + re.escape(v) + r"(?!\w)", question, re.IGNORECASE):
            if m.group(0) != v and v not in wanted:
                return tolk.Refusal("AMBIGUOUS_VALUE", f"{m.group(0)!r} is written differently from the value {v!r} in the database")
    text, held = question, {}
    for value, mark in zip(wanted, _placeholders(question, len(wanted))):
        before = text
        text = re.sub(r"(?<!\w)" + re.escape(value) + r"(?!\w)", mark, text)
        if text != before:
            held[mark.lower()] = value.lower()
    x = tolk.read(text, known, vocabulary)
    if not isinstance(x, (tolk.Ask, tolk.Describe)):
        return x
    present = {c.id for c in _consts(x)}
    lost = [v for mark, v in held.items() if mark not in present]
    if lost:
        return tolk.Refusal("VALUE_NOT_A_NAME", f"{lost[0]!r} is in the database but the sentence does not use it as a name")
    x = _rename(x, held)
    for c in _consts(x):
        if c.kind == "named" and not _present(c.id, question):
            return tolk.Refusal("NAME_NOT_AS_WRITTEN", f"the grammar read the question's word as {c.id!r}")
    return x
