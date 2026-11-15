#!/usr/bin/env python3
"""Run SQUID (the tolk path of `squid.compile`) on the Spider development set and score by execution.

For each question the predicted SQL and the gold SQL are run on the question's own database and their rows compared: as lists when the gold
query has an ORDER BY, as multisets otherwise. A question squid refuses (`SquidCompileError`) has no predicted SQL. Any other exception is
counted as an error, with its type and message, and is never folded into a refusal. Nothing here is tuned.

    TOLK_ERG_DIR=/path/to/tolk/erg python scripts/benchmark_spider.py /path/to/spider_data [--limit N] [--out results.json]

Prints three numbers: the share of questions not refused, the share of those that are correct, and the share correct overall; and the ten
most frequent refusal reasons."""

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import squid

TIMEOUT_STEPS = 2_000_000  # a query that runs this many virtual-machine steps is given up on and counts as wrong


def connect(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    db.text_factory = lambda b: b.decode("utf-8", errors="replace")
    steps = [0]

    def stop() -> int:
        steps[0] += 1
        return 1 if steps[0] > TIMEOUT_STEPS // 1000 else 0

    db.set_progress_handler(stop, 1000)
    db.steps = steps  # type: ignore[attr-defined]
    return db


def rows_of(db: sqlite3.Connection, sql: str) -> list[tuple]:
    db.steps[0] = 0  # type: ignore[attr-defined]
    return [tuple(r) for r in db.execute(sql).fetchall()]


def same_rows(predicted: list[tuple], gold: list[tuple], gold_sql: str) -> bool:
    if "order by" in gold_sql.lower():
        return predicted == gold
    return sorted(map(repr, predicted)) == sorted(map(repr, gold))


def score(spider: Path, limit: int | None) -> list[dict]:
    dev = json.loads((spider / "dev.json").read_text(encoding="utf-8"))[:limit]
    schemas: dict[str, squid.Schema] = {}
    results = []
    for n, item in enumerate(dev, 1):
        path = spider / "database" / item["db_id"] / f"{item['db_id']}.sqlite"
        if item["db_id"] not in schemas:
            schemas[item["db_id"]] = squid.Schema.from_sqlite(str(path))
        row = {"question": item["question"], "db": item["db_id"], "gold": item["query"], "predicted": None, "status": None, "reason": None}
        try:
            row["predicted"] = squid.compile(item["question"], schemas[item["db_id"]])
        except squid.SquidCompileError as e:
            row["status"], row["reason"] = "refused", str(e)
        except Exception as e:  # reported by type and message in the output; nothing is hidden
            row["status"], row["reason"] = "error", f"{type(e).__name__}: {e}"
        if row["predicted"] is not None:
            db = connect(path)
            try:
                gold = rows_of(db, item["query"])
                try:
                    ok = same_rows(rows_of(db, row["predicted"]), gold, item["query"])
                    row["status"] = "correct" if ok else "wrong"
                except sqlite3.Error as e:
                    row["status"], row["reason"] = "wrong", f"predicted SQL did not run: {e}"
            finally:
                db.close()
        results.append(row)
        if n % 100 == 0:
            print(f"  {n}/{len(dev)}", file=sys.stderr, flush=True)
    return results


def report(results: list[dict]) -> str:
    n = len(results)
    status = Counter(r["status"] for r in results)
    made = status["correct"] + status["wrong"]
    refused = status["refused"] + status["error"]
    lines = [f"questions: {n}",
             f"not refused (an SQL was produced): {made} = {made / n:.1%}  (refused {status['refused']}, errors {status['error']})",
             f"correct of those not refused: {status['correct']} of {made} = {status['correct'] / made:.1%}" if made else "correct of those not refused: none",
             f"correct overall: {status['correct']} of {n} = {status['correct'] / n:.1%}",
             "", "ten most frequent refusal reasons:"]
    reasons = Counter(r["reason"] for r in results if r["status"] in ("refused", "error"))
    lines += [f"  {c:4d}  {why}" for why, c in reasons.most_common(10)]
    lines += ["", f"by refusal code (refused {refused}):"]
    codes = Counter(r["reason"].split(":")[0] for r in results if r["status"] in ("refused", "error"))
    lines += [f"  {c:4d}  {why}" for why, c in codes.most_common()]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("spider", type=Path, help="the unpacked official Spider data: dev.json and database/")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    results = score(args.spider, args.limit)
    if args.out:
        args.out.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(report(results))


if __name__ == "__main__":
    main()
