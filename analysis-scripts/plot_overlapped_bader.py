#!/usr/bin/env python3
"""Overlay all image charge-transfer curves for one case directory."""

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("case_directory")
    parser.add_argument("--output", default="bader_comparison.png")
    args = parser.parse_args()
    case = Path(args.case_directory)
    files = sorted(case.glob("*/bader_per_atom.csv"))
    if not files:
        raise SystemExit(f"[FAIL] No image results found under {case}")

    fig, ax = plt.subplots(figsize=(9, 5))
    for path in files:
        with path.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        ax.plot(
            [int(row["atom_index"]) for row in rows],
            [float(row["charge_transfer_e"]) for row in rows],
            linewidth=0.8,
            label=path.parent.name,
        )
    ax.axhline(0, color="black", linewidth=0.6)
    ax.set(xlabel="Atom index", ylabel="Charge transfer (e)", title=str(case))
    ax.legend(title="Image", ncol=2, fontsize=8)
    fig.tight_layout()
    output = case / args.output
    fig.savefig(output, dpi=300)
    print(f"[SUCCESS] Wrote {output}")


if __name__ == "__main__":
    main()
