# SQUID — SQL Unique Interpretation through Deep Parsing

**The first rule-based English-to-SQL compiler using hand-crafted grammar and deep linguistic parsing.**

SQUID compiles natural language questions to SQL using the [English Resource Grammar (ERG)](https://github.com/delph-in/erg) and its [DMRS (Dependency Minimal Recursion Semantics)](https://github.com/delph-in/docs/wiki/RmrsTop) output. **Zero neural components at runtime.** Every decision traces to a named grammar rule or a structural mapping rule.

## What Makes SQUID Different

| Feature | Neural Text-to-SQL | SQUID |
|---------|-------------------|-------|
| **Architecture** | Transformer (T5, GPT, etc.) | ERG grammar + rule-based compiler |
| **Runtime dependencies** | GPU, large models (billions of parameters) | ACE parser (C binary, <10MB) |
| **Accuracy** | Higher (SOTA: ~85% on Spider) | Lower (~40-60% estimated) |
| **Explainability** | Black box | Every output traces to named rules |
| **Auditability** | None | Full parse trees + compilation steps |
| **Domain adaptation** | Requires retraining | Add lexicon entries (no training) |
| **Latency** | ~500ms-2s | ~100-500ms (with persistent parser) |
| **EU AI Act compliance** | Difficult (Article 13 transparency) | Designed for traceability |

SQUID is designed for **regulated environments** where explainability and auditability are more important than state-of-the-art accuracy.

## Architecture

```
English question
  ↓
ACE parser + ERG grammar
  ↓
MRS (Minimal Recursion Semantics)
  ↓
DMRS (Dependency MRS)
  ↓
Schema-based disambiguation (score parses by schema fit)
  ↓
Schema linking (fuzzy match predicates to tables/columns)
  ↓
DMRS → SQL compiler (walk graph, emit sqlglot expressions)
  ↓
SQL query
```

### Key Components

1. **ACE parser** — Fast C-based unification parser for HPSG grammars
2. **ERG** — Hand-written grammar with ~40,000 lexical entries, ~85-95% coverage of well-formed English
3. **Schema lexicon injection** — Generate TDL lexical entries from database schema to handle domain vocabulary
4. **Schema-fit disambiguation** — Replace ERG's MaxEnt ranker with rule-based schema matching
5. **Schema linking** — Fuzzy match DMRS predicates to tables/columns using rapidfuzz + lemminflect
6. **Structural compiler** — ~40 fixed rules mapping DMRS predicates to SQL operations
7. **sqlglot** — Dialect-independent SQL generation

## Installation

### Prerequisites

- **Python 3.10+**
- **ACE parser** (C binary)
- **ERG grammar** (compiled .dat file)

### Install SQUID

```bash
pip install -e ../tolk -e .
```

This is the one command, run in a checkout of SQUID with a checkout of [tolk](https://github.com/richarah/tolk) beside it. tolk is a
dependency by local path for now: it is not published, so **tolk must be published before SQUID can be released.** tolk needs the ACE
binary and the grammar image in its own `erg/` directory (`sh ../tolk/scripts/setup_erg.sh`).

### Download ACE and ERG

```bash
bash scripts/setup_erg.sh
```

This downloads:
- ACE 0.9.34 (or latest)
- ERG 2024 grammar image

**Manual download** (if script fails):
- ACE: http://sweaglesw.org/linguistics/ace/download/
- ERG: https://github.com/delph-in/erg/releases

## Quickstart

```python
import squid

# Load a database schema
schema = squid.Schema.from_sqlite("my_database.db")

# Compile a question to SQL
sql = squid.compile("How many customers are there?", schema)
print(sql)
# Output: SELECT COUNT(*) FROM customers
```

### With Spider dataset

```python
import squid

# Load schema from Spider's tables.json
schema = squid.Schema.from_spider("spider/tables.json", "concert_singer")

# Compile a question
sql = squid.compile(
    "What are the names of singers who performed in the concert named 'Super bootcamp'?",
    schema
)
print(sql)
```

### Advanced: Pre-parsed DMRS

```python
import squid
from delphin import dmrs

# If you already have a DMRS parse
dmrs_obj = ...  # Your DMRS object

# Compile directly
schema = squid.Schema.from_sqlite("my_database.db")
sql = squid.from_dmrs(dmrs_obj, schema)
```

## Configuration

### Parse parameters

```python
sql = squid.compile(
    question="How many singers?",
    schema=schema,
    n_parses=10,                  # More parses = better disambiguation, slower
    max_chart_megabytes=2048,     # Max memory per parse
    max_edges=100000,             # Max chart edges
    timeout=30.0,                 # Timeout per sentence (seconds)
    dialect="postgres",           # SQL dialect: sqlite, postgres, mysql, etc.
)
```

**Performance tuning:**

- **Interactive use:** `n_parses=1`, `timeout=5.0` — Fast, less accurate
- **Batch processing:** `n_parses=5`, `timeout=30.0` — Balanced (default)
- **High accuracy:** `n_parses=10`, `timeout=60.0` — Slow, most accurate

### Persistent parser (recommended for batch)

```python
from squid.parser import ERGParser

# Keep parser alive across multiple queries
with ERGParser(grm_path="erg.dat", ace_path="ace") as parser:
    for question in questions:
        parses = parser.parse_to_dmrs(question)
        # ... process parses
```

## Benchmarking

Run SQUID on the Spider dev set:

```bash
python scripts/benchmark_spider.py \
    /path/to/spider \
    --output results.json \
    --limit 100
```

Expected accuracy: ~40-60% exact match (current implementation is a proof-of-concept; accuracy will improve with more comprehensive compiler rules).

## Schema Loading

### From SQLite

```python
schema = squid.Schema.from_sqlite("path/to/database.db")
```

### From SQLAlchemy

```python
from sqlalchemy import create_engine

engine = create_engine("postgresql://user:pass@localhost/dbname")
schema = squid.Schema.from_sqlalchemy(engine)
```

### From Spider format

```python
schema = squid.Schema.from_spider("spider/tables.json", "concert_singer")
```

## How It Works

### 1. Schema Lexicon Injection

The ERG doesn't know domain vocabulary like "singer" or "concert_id". SQUID generates TDL (Type Description Language) lexical entries from your schema:

```tdl
singer := n_-_c_le &
  [ STEM < "singer" >,
    SYNSEM.LKEYS.KEYREL.PRED "_singer_n_1_rel" ].
```

These are loaded into ACE alongside the ERG at parse time.

### 2. Schema-Fit Disambiguation

Instead of the ERG's MaxEnt parse ranker, SQUID scores parses by how well their predicates match the schema:

- Predicate matches table: +1.0
- Predicate matches column: +0.8
- Predicate matches value: +0.6
- Unknown content word: -0.5

The highest-scoring parse is selected.

### 3. Schema Linking

DMRS predicates are linked to schema elements using:

1. Exact match
2. Inflection normalization (plurals/singulars via inflect)
3. Lemmatization (via lemminflect)
4. Fuzzy matching (via rapidfuzz, threshold: 85%)

### 4. DMRS → SQL Compilation

The compiler walks the DMRS graph and applies ~40 structural rules:

- **Quantifiers** (which_q, _every_q, _some_q) → SELECT, EXISTS, UNIVERSAL
- **Comparisons** (comp, superl) → WHERE, ORDER BY + LIMIT
- **Aggregations** (much-many_a, _most_a_1) → COUNT, MAX, MIN, AVG, SUM
- **Connectives** (_and_c, _or_c, neg) → AND, OR, NOT
- **Constructions** (relative clauses, nominalizations) → JOINs, subqueries

The result is a `QueryPlan` (intermediate representation), which is converted to SQL via sqlglot.

## Limitations

### ERG Coverage

The ERG has ~85-95% coverage of well-formed English. If parsing fails:

- Simplify the question
- Avoid rare words or complex constructions
- Check `SquidParseError` details

### Compiler Completeness

The current compiler implements ~40 structural rules, which covers common SQL patterns but not all:

- **Supported:** SELECT, WHERE, JOIN, COUNT/MAX/MIN/AVG/SUM, ORDER BY, LIMIT
- **Partial:** GROUP BY, HAVING, nested subqueries
- **Not supported:** Window functions, CTEs, UNION/INTERSECT/EXCEPT

Contributions to expand coverage are welcome.

### Comparison with Neural Text-to-SQL

SQUID will **not** match the accuracy of SOTA neural models (T5-3B, GPT-4, etc.). Its design priorities are:

1. **Explainability** — Every step is auditable
2. **Determinism** — Same input always produces same output
3. **Transparency** — No learned parameters, no black box
4. **Efficiency** — Runs on CPU, no GPU required

If you need SOTA accuracy, use a neural model. If you need explainability and auditability (e.g., for regulatory compliance), use SQUID.

## Performance Optimization

SQUID includes several optimizations:

1. **mypyc compilation** — Core modules compile to C extensions (3-5x speedup)
2. **Persistent ACE process** — Avoid subprocess overhead
3. **Precomputed schema indices** — O(1) table/column lookups
4. **Batch similarity matching** — rapidfuzz.process.cdist for vectorized fuzzy matching
5. **String interning** — Reduce memory usage for repeated strings

Install with mypyc (requires C compiler):

```bash
pip install mypy
pip install .
```

Verify compilation:

```python
import squid.compiler
print(type(squid.compiler))
# Should show: <class 'module'> with .so extension
```

## Development

### Run tests

```bash
pytest tests/
```

### Type checking

```bash
mypy squid/
```

### Format code

```bash
black squid/ tests/
```

## Contributing

Contributions are welcome, especially:

- **Expanding compiler rules** — Add support for more SQL constructions
- **Improving schema linking** — Better fuzzy matching, synonym expansion
- **Adding test cases** — More unit and integration tests
- **Documentation** — Tutorials, examples, architecture docs

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License. See [LICENSE](LICENSE) for details.

## Citation

If you use SQUID in research, please cite:

```bibtex
@software{squid2025,
  title = {SQUID: SQL Unique Interpretation through Deep Parsing},
  author = {SQUID Contributors},
  year = {2025},
  url = {https://github.com/yourusername/squid}
}
```

## References

- **ERG:** Flickinger, D. (2000). [On building a more efficient grammar by exploiting types](https://aclanthology.org/J00-1002/). *Natural Language Engineering*, 6(1), 15-28.
- **DMRS:** Copestake, A. (2009). [Slacker semantics: Why superficiality, dependency and avoidance of commitment can be the right way to go](https://aclanthology.org/E09-1001/). *EACL 2009*.
- **ACE:** Crysmann, B., & Packard, W. (2012). [Towards efficient HPSG generation for German, a non-configurational language](https://aclanthology.org/C12-1070/). *COLING 2012*.
- **Spider:** Yu, T., et al. (2018). [Spider: A large-scale human-labeled dataset for complex and cross-domain semantic parsing and text-to-SQL task](https://arxiv.org/abs/1809.08887). *EMNLP 2018*.

## Acknowledgments

SQUID builds on decades of work in computational linguistics:

- The DELPH-IN consortium for the ERG and related tools
- Dan Flickinger for the ERG grammar
- The PyDelphin project for Python bindings
- The sqlglot project for dialect-independent SQL generation

---

**SQUID** — Explainable English-to-SQL for the real world.
