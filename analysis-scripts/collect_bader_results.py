#!/usr/bin/env python3
"""Collect all per-image Bader summaries into one CSV."""

import argparse
import csv
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default="Bader-calculations")
    parser.add_argument("--output", default="all_bader_summary.csv")
    args = parser.parse_args()
    root = Path(args.root)
    files = sorted(root.rglob("bader_summary.csv"))
    if not files:
        raise SystemExit(f"[FAIL] No bader_summary.csv files under {root}")

    rows = []
    for path in files:
        relative = path.parent.relative_to(root)
        parts = relative.parts
        metal = parts[0] if len(parts) > 0 else ""
        case = parts[1] if len(parts) > 1 else ""
        image = parts[2] if len(parts) > 2 else ""
        with path.open(newline="") as handle:
            for row in csv.DictReader(handle):
                rows.append(
                    {
                        "metal_folder": metal,
                        "case": case,
                        "image": image,
                        "element": row["element"],
                        "atom_count": row["atom_count"],
                        "bader_electrons": row["bader_electrons"],
                        "charge_transfer_e": row["charge_transfer_e"],
                        "nelect": row["nelect"],
                        "bader_total": row["bader_total"],
                        "abs_difference": row["abs_difference"],
                        "status": row["status"],
                        "directory": str(path.parent),
                    }
                )
        print(f"[OK] Collected {path.parent}")

    with Path(args.output).open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"[SUCCESS] Wrote {args.output} from {len(files)} calculations")


if __name__ == "__main__":
    main()
