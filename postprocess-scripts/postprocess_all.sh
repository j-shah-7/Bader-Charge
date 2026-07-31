#!/usr/bin/env bash
# postprocess_all.sh
# Run from parent directory that contains subdirectories to process.

set -euo pipefail

ROOTDIR="$(pwd)"
SUMMARY_CSV="${ROOTDIR}/bader_summary.csv"

# If the summary file exists, back it up with a timestamp
if [ -f "$SUMMARY_CSV" ]; then
    mv "$SUMMARY_CSV" "${SUMMARY_CSV}.$(date +%Y%m%d_%H%M%S).bak"
fi

echo "dir,NELECT,Bader_total,difference,status,num_atoms,poscar_elements" > "${SUMMARY_CSV}"
echo "Starting post-processing in ${ROOTDIR} ..."

# iterate only over directories (non-recursive) - change if you want recursive
for d in */ ; do
    # Skip hidden or special dirs
    [[ "$d" == "./" ]] && continue
    echo "------------------------------------------------------------"
    echo "Processing directory: $d"
    cd "$d" || { echo "Failed to cd into $d"; continue; }

    # Check presence of files required
    if [[ ! -f "CHGCAR" ]]; then
        echo "  ✖ CHGCAR not found in $(pwd). Skipping."
        cd "$ROOTDIR"; continue
    fi

    # 1) If AECCAR0 and AECCAR2 exist, run chgsum.pl
    if [[ -f "AECCAR0" && -f "AECCAR2" ]]; then
        echo "  -> Running chgsum.pl AECCAR0 AECCAR2 ..."
        if perl -e 'exit 0' >/dev/null 2>&1; then
            if ! perl chgsum.pl AECCAR0 AECCAR2 >/dev/null 2>&1; then
                echo "     ⚠ chgsum.pl failed (check AECCAR files)."
            else
                echo "     CHGCAR_sum created."
            fi
        else
            echo "     ⚠ perl not available: cannot run chgsum.pl"
        fi
    else
        echo "  -> AECCAR0/AECCAR2 not both present; skipping chgsum.pl (assuming CHGCAR is full valence+core)."
    fi

    # 2) Make bader executable if present in cwd
    if [[ -f "./bader" ]]; then
        chmod +x ./bader || true
    else
        echo "  ✖ bader executable not found in this directory. Expecting './bader' or provide path."
        # Try to find bader in PATH
        if command -v bader >/dev/null 2>&1; then
            echo "  -> Found bader in PATH."
            BADER_CMD="bader"
        else
            echo "  ✖ bader not found in PATH either. Skipping."
            cd "$ROOTDIR"; continue
        fi
    fi

    # prefer local ./bader if exists, else system bader
    if [[ -f "./bader" ]]; then
        BADER_CMD="./bader"
    else
        BADER_CMD="$(command -v bader)"
    fi

    # 3) Run Bader
    echo "  -> Running: ${BADER_CMD} CHGCAR -ref CHGCAR_sum (or -ref AECCAR sum output)"
    if ! "${BADER_CMD}" CHGCAR -ref CHGCAR_sum >/dev/null 2>&1; then
        echo "     ⚠ bader execution failed (exit code nonzero). Check CHGCAR and CHGCAR_sum."
        cd "$ROOTDIR"; continue
    fi
    echo "     ACF.dat generated."

    # 4) Run the Python analysis/plotting script (supplied below)
    # It will append one summary row into the root bader_summary.csv
    # Call it with --outcsv pointing to the global summary file.
    if python3 - <<'PY'
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath("__file__")))
print("  -> Running inline check script ...")
PY
then
        :
    fi

    # Run the external python script (assumes it is next to postprocess_all.sh in parent dir)
    # If the script is placed in the root dir named bader_analysis.py
    if [[ -f "${ROOTDIR}/bader_analysis.py" ]]; then
        python3 "${ROOTDIR}/bader_analysis.py" --dir "$(pwd)" --append-csv "${SUMMARY_CSV}"
    else
        echo "  ✖ bader_analysis.py not found in root dir (${ROOTDIR}). Skipping analysis step."
    fi

    cd "$ROOTDIR" || exit 1
done

echo "------------------------------------------------------------"
echo "Post-processing done. Global summary: ${SUMMARY_CSV}"

