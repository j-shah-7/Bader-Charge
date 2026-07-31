#!/usr/bin/env python3
"""Plot charge transfer by atom index for every completed image."""

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default="Bader-calculations")
    args = parser.parse_args()
    files = sorted(Path(args.root).rglob("bader_per_atom.csv"))
    if not files:
        raise SystemExit("[FAIL] No bader_per_atom.csv files found")
    for path in files:
        with path.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        x = [int(row["atom_index"]) for row in rows]
        y = [float(row["charge_transfer_e"]) for row in rows]
        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.plot(x, y, linewidth=0.8)
        ax.axhline(0, color="black", linewidth=0.6)
        ax.set(xlabel="Atom index", ylabel="Charge transfer (e)",
               title=str(path.parent))
        fig.tight_layout()
        output = path.parent / "bader_charge_transfer.png"
        fig.savefig(output, dpi=300)
        plt.close(fig)
        print(f"[OK] {output}")
    print(f"[SUCCESS] Created {len(files)} plots")


if __name__ == "__main__":
    main()
