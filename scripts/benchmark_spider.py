#!/usr/bin/env python3
"""
Benchmark SQUID on the Spider dev set.

Reports exact match accuracy and saves detailed results.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

import squid


def load_spider_dev(spider_dir: Path) -> List[Dict]:
    """Load Spider dev set questions."""
    dev_file = spider_dir / "dev.json"
    if not dev_file.exists():
        raise FileNotFoundError(f"Spider dev.json not found: {dev_file}")

    with open(dev_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def normalize_sql(sql: str) -> str:
    """
    Normalize SQL for comparison.

    This is a simplified normalization. For rigorous evaluation,
    use the official Spider test suite evaluation script.
    """
    # Convert to lowercase
    sql = sql.lower()

    # Remove extra whitespace
    sql = ' '.join(sql.split())

    # Remove trailing semicolon
    sql = sql.rstrip(';')

    return sql


def exact_match(predicted: str, gold: str) -> bool:
    """Check if predicted SQL matches gold SQL (after normalization)."""
    return normalize_sql(predicted) == normalize_sql(gold)


def benchmark(
    spider_dir: Path,
    ace_path: str = "ace",
    grm_path: str = "erg.dat",
    output_file: Path | None = None,
    limit: int | None = None,
) -> None:
    """
    Run SQUID on Spider dev set and compute exact match accuracy.

    Args:
        spider_dir: Path to Spider dataset directory
        ace_path: Path to ACE binary
        grm_path: Path to ERG grammar
        output_file: Optional file to save detailed results
        limit: Optional limit on number of examples to process
    """
    print("Loading Spider dev set...")
    dev_data = load_spider_dev(spider_dir)

    if limit:
        dev_data = dev_data[:limit]
        print(f"Limited to first {limit} examples")

    tables_json = spider_dir / "tables.json"
    if not tables_json.exists():
        raise FileNotFoundError(f"Spider tables.json not found: {tables_json}")

    print(f"Processing {len(dev_data)} examples...")

    results = []
    correct = 0
    failed_parse = 0
    failed_compile = 0

    for idx, example in enumerate(dev_data):
        question = example['question']
        gold_sql = example['sql']
        db_id = example['db_id']

        print(f"\n[{idx+1}/{len(dev_data)}] DB: {db_id}")
        print(f"Question: {question}")

        try:
            # Load schema for this database
            schema = squid.Schema.from_spider(str(tables_json), db_id)

            # Compile question to SQL
            predicted_sql = squid.compile(
                question,
                schema,
                grm_path=grm_path,
                ace_path=ace_path,
                n_parses=5,
                dialect="sqlite",
            )

            print(f"Predicted: {predicted_sql}")
            print(f"Gold:      {gold_sql}")

            # Check exact match
            match = exact_match(predicted_sql, gold_sql)
            if match:
                correct += 1
                print("Result: MATCH")
            else:
                print("Result: NO MATCH")

            results.append({
                'index': idx,
                'db_id': db_id,
                'question': question,
                'gold_sql': gold_sql,
                'predicted_sql': predicted_sql,
                'match': match,
                'error': None,
            })

        except squid.SquidParseError as e:
            failed_parse += 1
            print(f"Parse error: {e}")
            results.append({
                'index': idx,
                'db_id': db_id,
                'question': question,
                'gold_sql': gold_sql,
                'predicted_sql': None,
                'match': False,
                'error': f"ParseError: {e}",
            })

        except squid.SquidCompileError as e:
            failed_compile += 1
            print(f"Compile error: {e}")
            results.append({
                'index': idx,
                'db_id': db_id,
                'question': question,
                'gold_sql': gold_sql,
                'predicted_sql': None,
                'match': False,
                'error': f"CompileError: {e}",
            })

        except Exception as e:
            print(f"Unexpected error: {e}")
            results.append({
                'index': idx,
                'db_id': db_id,
                'question': question,
                'gold_sql': gold_sql,
                'predicted_sql': None,
                'match': False,
                'error': f"Error: {e}",
            })

    # Print summary
    print("\n" + "="*80)
    print("BENCHMARK RESULTS")
    print("="*80)
    print(f"Total examples: {len(dev_data)}")
    print(f"Correct: {correct}")
    print(f"Parse failures: {failed_parse}")
    print(f"Compile failures: {failed_compile}")
    print(f"Exact match accuracy: {correct / len(dev_data) * 100:.2f}%")
    print("="*80)

    # Save detailed results
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'summary': {
                    'total': len(dev_data),
                    'correct': correct,
                    'parse_failures': failed_parse,
                    'compile_failures': failed_compile,
                    'accuracy': correct / len(dev_data),
                },
                'results': results,
            }, f, indent=2)
        print(f"\nDetailed results saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark SQUID on Spider dev set"
    )
    parser.add_argument(
        "spider_dir",
        type=Path,
        help="Path to Spider dataset directory"
    )
    parser.add_argument(
        "--ace",
        type=str,
        default="ace",
        help="Path to ACE binary (default: ace)"
    )
    parser.add_argument(
        "--grammar",
        type=str,
        default="erg.dat",
        help="Path to ERG grammar (default: erg.dat)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file for detailed results (JSON)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of examples to process"
    )

    args = parser.parse_args()

    try:
        benchmark(
            spider_dir=args.spider_dir,
            ace_path=args.ace,
            grm_path=args.grammar,
            output_file=args.output,
            limit=args.limit,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
