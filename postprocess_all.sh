#!/usr/bin/env bash
set -u

ROOT="${1:-Bader-calculations}"
[[ -d "$ROOT" ]] || { echo "[FAIL] Directory not found: $ROOT" >&2; exit 1; }

mapfile -d '' dirs < <(find "$ROOT" -type f -name CHGCAR -printf '%h\0' | sort -z)
[[ ${#dirs[@]} -gt 0 ]] || { echo "[FAIL] No CHGCAR files found under $ROOT" >&2; exit 1; }

ok=0
failed=0
for dir in "${dirs[@]}"; do
    echo "------------------------------------------------------------"
    echo "[PROCESS] $dir"
    if (cd "$dir" && bash run_bader_single.sh); then
        ((ok+=1))
        echo "[OK] $dir"
    else
        ((failed+=1))
        echo "[FAIL] $dir" >&2
    fi
done

echo "------------------------------------------------------------"
echo "[SUMMARY] Successful: $ok; failed: $failed"
[[ $failed -eq 0 ]]
