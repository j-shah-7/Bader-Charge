#!/usr/bin/env python3
"""Plot the charge transfer of one explicitly selected atom across path images."""

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_directory", type=Path)
    parser.add_argument("--atom-index", type=int, required=True,
                        help="One-based POSCAR atom index, constant across images")
    parser.add_argument("--output", type=Path, default=Path("migrating_atom_charge.png"))
    args = parser.parse_args()
    if args.atom_index < 1:
        parser.error("--atom-index must be positive")

    files = sorted(args.case_directory.glob("*/bader_per_atom.csv"),
                   key=lambda path: (0, int(path.parent.name))
                   if path.parent.name.isdigit() else (1, path.parent.name))
    if not files:
        parser.error(f"No image results under {args.case_directory}")

    images, charges, elements = [], [], set()
    for path in files:
        with path.open(newline="") as handle:
            matches = [row for row in csv.DictReader(handle)
                       if int(row["atom_index"]) == args.atom_index]
        if len(matches) != 1:
            raise SystemExit(f"{path}: expected exactly one atom #{args.atom_index}")
        images.append(path.parent.name)
        charges.append(float(matches[0]["charge_transfer_e"]))
        elements.add(matches[0]["element"])
    if len(elements) != 1:
        raise SystemExit("Selected atom index changes element across images")

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(range(len(images)), charges, marker="o")
    ax.axhline(0, color="black", linewidth=0.7)
    ax.set(xticks=range(len(images)), xticklabels=images,
           xlabel="Path image", ylabel="Charge transfer (e)",
           title=f"{next(iter(elements))} atom #{args.atom_index}")
    fig.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=200)
    plt.close(fig)
    print(f"[SUCCESS] Wrote {args.output}")


if __name__ == "__main__":
    main()
