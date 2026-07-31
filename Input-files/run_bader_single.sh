#!/usr/bin/env bash
set -euo pipefail

echo "  [BADER 1/4] Checking charge-density files and tools"
for f in CHGCAR AECCAR0 AECCAR2 chgsum.pl bader bader_analysis.py; do
    test -s "$f" || { echo "[FAIL] Missing or empty: $f" >&2; exit 1; }
done
echo "  [OK] Required Bader inputs are present"

echo "  [BADER 2/4] Summing AECCAR0 + AECCAR2"
perl ./chgsum.pl AECCAR0 AECCAR2 > chgsum.log 2>&1
test -s CHGCAR_sum
echo "  [OK] CHGCAR_sum created"

echo "  [BADER 3/4] Partitioning CHGCAR with all-electron reference"
chmod u+x ./bader
./bader CHGCAR -ref CHGCAR_sum > bader.log 2>&1
test -s ACF.dat
echo "  [OK] ACF.dat created"

echo "  [BADER 4/4] Writing charge-transfer tables"
python3 ./bader_analysis.py
test -s bader_per_atom.csv
test -s bader_summary.csv
echo "  [SUCCESS] bader_per_atom.csv and bader_summary.csv created"
