# SQUID: English questions to SQL

> **SQUID depends on a private repository for now (tolk), so only its owner can install it.**

SQUID turns an English question into SQL over a database schema. The sentence is read by [tolk](https://github.com/richarah/tolk) (the ACE
parser and the English Resource Grammar); SQUID's schema linking says which tables the words mean; sqlglot writes the SQL. There is no
neural component.

## What it does

`squid.compile(question, schema)` reads the question with tolk, passing the schema's table names to the parser as tagged input (so a
table name the grammar does not know still parses) and its tables as the predicates that steer the choice between readings. A tolk
question (`Ask`, `Describe`) becomes SQL; anything else raises `SquidCompileError` with tolk's refusal code and reason.

- A table is a noun. A table with two or more foreign keys is a relation: a verb whose subject is its first foreign key.
- Yes-or-no, who/which, how-many and negated questions over those tables compile ("Which dogs does Kim own?", "How many dogs does Kim own?",
  "Does Kim not own Fido?").
- A name is compared in lower case with the `name` column. A value that is in a `name` column (read when the schema comes from SQLite) is read
  as that value, so "Ga" is Ga and not Georgia; a name the question does not contain as written, or a value written in another case, is refused.
- Not supported, and refused: statements, rules, claims, comparisons, "every", an or, a past tense, and any word that is not a table.
- The first pipeline (ACE, DMRS, its own compiler) was removed. It did not run with the ACE binary tolk uses: ACE has no
  `--extra-lexicon` option, and its output parser could not read ACE's output. Its history is in git before the removal commit.

```python
import squid

schema = squid.Schema.from_sqlite("pets.db")
print(squid.compile("Which dogs does Kim own?", schema))
```

## Install

```bash
pip install -e '.[dev]'
```

SQUID depends on tolk by its git address, pinned at the `v0.1.6` tag. **That repository is private for now**, so the install needs git
credentials that can read it: only its owner can install SQUID until tolk is published.

tolk needs the ACE parser binary and the grammar image. In a checkout of tolk, `sh scripts/setup_erg.sh` puts them in its `erg/`; an
installed copy of tolk has no checkout beside it, so name that directory: `export TOLK_ERG_DIR=/path/to/tolk/erg`.

## Measured

Every number here is printed by a script in this repository.

| What | Result | Script |
|---|---|---|
| Spider development set, 1034 questions, scored by running the predicted and the gold SQL on the question's database | not refused: 0 of 1034 (0.0%); correct of those not refused: none; correct overall: 0 of 1034 (0.0%) | `scripts/benchmark_spider.py` |
| Differential test against tolk with its closed world on (15 questions over a small pets database) | 15 questions, 0 disagreements | `scripts/differential_tolk.py` |
| Tests | 62 passed (62 collected) | `scripts/readme_numbers.py` |

The Spider run is dated 2026-11-15, on the official development set (`dev.json` and its databases). Its full output is in
`benchmarks/spider_dev_2026-11-15.txt` and, per question, `benchmarks/spider_dev_2026-11-15.json`. Nothing was tuned for it. The ten most
frequent refusal reasons: 323 `UNSUPPORTED_FORCE: comm` (an imperative: "List the ..."), 271 `DEFINITE_NEEDS_STORE: _the_q` ("the" needs a
store of things; a database question has none), 73 `NO_EVENT_READING`, 21 `UNSUPPORTED_PREDICATE: more_comp`, 20 `UNIVERSAL_QUESTION`,
18 `UNKNOWN_WORD: schoolers`, 12 `GRAMMAR_ARTIFACT: place_n`, 10 `UNSUPPORTED_TENSE: tensed on _find_v_1`, 9 `NO_ANTECEDENT`,
8 `UNKNOWN_PREDICATE: _have_v_1 is no table of the schema`. One question raised an error instead of a refusal ("List the section_name in
reversed lexicographical order.": tolk's reader fails on the underscore in the word).

Spider asks for rows ("List the names of ...", "What are the ... of the ..."), most with a definite article; this path answers
yes-or-no, who/which and how-many questions about named things, so it covers almost none of them. These numbers say that and nothing more.

## Tests

```bash
pytest tests
```

The tests of the first pipeline were removed with it. The remaining tests cover the schema, linking, the tolk back end and the
differential test.

## Licence

MIT, see `LICENSE`.
