"""The numbers README.md quotes, other than the Spider score (scripts/benchmark_spider.py, saved under benchmarks/).

    python scripts/readme_numbers.py      the test counts, and the differential test's result against tolk
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

collected = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "tests"], capture_output=True, text=True, cwd=ROOT).stdout
print("tests:", collected.strip().splitlines()[-1])
ran = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests"], capture_output=True, text=True, cwd=ROOT).stdout
print("suite:", ran.strip().splitlines()[-1])
diff = subprocess.run([sys.executable, "scripts/differential_tolk.py"], capture_output=True, text=True, cwd=ROOT).stdout
print("differential:", diff.strip().splitlines()[-1])
