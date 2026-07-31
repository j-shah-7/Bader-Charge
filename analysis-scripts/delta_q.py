#!/usr/bin/env python3
"""Upgrade a legacy two-column Bader CSV using POSCAR/POTCAR ZVAL data."""

import argparse
import csv
from pathlib import Path

from bader_analysis import poscar_species, potcar_zvals


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?", default="bader_per_atom.csv")
    parser.add_argument("--output")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else input_path.with_name(
        input_path.stem + "_delta.csv"
    )
    symbols, counts, elements, species_indices = poscar_species(Path("POSCAR"))
    pot_data = potcar_zvals(Path("POTCAR"))
    if symbols != [item[0] for item in pot_data]:
        raise SystemExit("[FAIL] POSCAR/POTCAR species order mismatch")
    zvals = dict(pot_data)

    with input_path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != len(elements):
        raise SystemExit(
            f"[FAIL] CSV has {len(rows)} atoms; POSCAR has {len(elements)}"
        )

    out = []
    for row, element, species_index in zip(rows, elements, species_indices):
        electrons_text = row.get("bader_electrons", row.get("bader_charge"))
        if electrons_text is None:
            raise SystemExit("[FAIL] No bader_electrons or bader_charge column")
        electrons = float(electrons_text)
        row.update(
            {
                "element": element,
                "species_index": species_index,
                "reference_valence": zvals[element],
                "charge_transfer_e": zvals[element] - electrons,
            }
        )
        out.append(row)

    fields = list(out[0].keys())
    with output_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out)
    print(f"[SUCCESS] Wrote {output_path}")


if __name__ == "__main__":
    main()
