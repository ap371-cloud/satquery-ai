from __future__ import annotations

import py_compile
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Compile project Python first so syntax/import-adjacent mistakes fail early.
python_files = sorted((ROOT / 'backend').rglob('*.py')) + sorted((ROOT / 'scripts').glob('*.py'))
for path in python_files:
    if path.name == Path(__file__).name:
        continue
    py_compile.compile(str(path), doraise=True)
print(f'PYTHON COMPILE PASS ({len(python_files)-1} files)')

for script in ['test_natural_language.py', 'test_e2e_matrix.py',
    'test_trust_contract.py', 'smoke_test.py']:
    print(f'\n=== {script} ===')
    subprocess.run([sys.executable, str(ROOT / 'scripts' / script)], cwd=ROOT, check=True)

print('\nALL SATQUERY TESTS PASS')
