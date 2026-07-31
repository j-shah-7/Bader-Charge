#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-Bader-calculations}"
DRY_RUN=0
if [[ "${2:-}" == "--dry-run" || "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=1
    [[ "${1:-}" == "--dry-run" ]] && ROOT="Bader-calculations"
fi

[[ -d "$ROOT" ]] || { echo "[FAIL] Directory not found: $ROOT" >&2; exit 1; }
mapfile -d '' jobs < <(find "$ROOT" -type f -name bader-job.sh -print0 | sort -z)
[[ ${#jobs[@]} -gt 0 ]] || { echo "[FAIL] No bader-job.sh files found" >&2; exit 1; }

echo "[INFO] Found ${#jobs[@]} Bader jobs under $ROOT"
submitted=0
for job in "${jobs[@]}"; do
    dir="$(dirname "$job")"
    if [[ -s "$dir/bader_summary.csv" ]]; then
        echo "[SKIP] Already analyzed: $dir"
        continue
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
        echo "[DRY RUN] Would submit: $dir"
    else
        echo "[SUBMIT] $dir"
        (cd "$dir" && sbatch bader-job.sh)
        ((submitted+=1))
        echo "[OK] Submitted: $dir"
    fi
done
echo "[SUCCESS] Submission pass complete; submitted $submitted jobs"
