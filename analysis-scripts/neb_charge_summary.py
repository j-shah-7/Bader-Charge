#!/usr/bin/env python3
"""Create one element-resolved table per NEB path from collected results."""

import argparse
import csv
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?", default="all_bader_summary.csv")
    parser.add_argument("--output", default="neb_charge_summary.csv")
    args = parser.parse_args()

    with Path(args.input).open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit("[FAIL] Input summary is empty")

    elements = sorted({row["element"] for row in rows})
    grouped = {}
    for row in rows:
        key = (row["metal_folder"], row["case"], row["image"])
        grouped.setdefault(key, {})[row["element"]] = row["charge_transfer_e"]

    fields = ["metal_folder", "case", "image"] + [
        f"sum_charge_transfer_{element}_e" for element in elements
    ]
    with Path(args.output).open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for key in sorted(grouped, key=lambda x: (x[0], x[1], int(x[2]))):
            values = grouped[key]
            out = dict(zip(fields[:3], key))
            for element in elements:
                out[f"sum_charge_transfer_{element}_e"] = values.get(element, "")
            writer.writerow(out)
    print(f"[SUCCESS] Wrote {args.output} with {len(grouped)} image rows")


if __name__ == "__main__":
    main()
