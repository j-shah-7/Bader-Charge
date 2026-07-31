#!/usr/bin/env python3
"""Analyze ACF.dat using species and ZVAL read from POSCAR/POTCAR."""

import argparse
import csv
import re
import sys
from pathlib import Path


def poscar_species(path):
    lines = path.read_text(errors="replace").splitlines()
    if len(lines) < 8:
        raise ValueError("POSCAR is too short")
    symbols = lines[5].split()
    counts = [int(x) for x in lines[6].split()]
    if not symbols or len(symbols) != len(counts):
        raise ValueError("POSCAR species/count columns do not agree")
    expanded = []
    species_indices = []
    for symbol, count in zip(symbols, counts):
        expanded.extend([symbol] * count)
        species_indices.extend(range(1, count + 1))
    return symbols, counts, expanded, species_indices


def potcar_zvals(path):
    datasets = re.split(r"(?=^\s*TITEL\s*=)", path.read_text(errors="replace"), flags=re.M)
    result = []
    for block in datasets:
        title = re.search(r"^\s*TITEL\s*=\s*\S+\s+(\S+)", block, re.M)
        zval = re.search(r"\bZVAL\s*=\s*([-+0-9.Ee]+)", block)
        if title and zval:
            result.append((title.group(1).split("_")[0], float(zval.group(1))))
    if not result:
        raise ValueError("Could not read TITEL/ZVAL datasets from POTCAR")
    return result


def read_acf(path, expected_atoms):
    atoms = []
    for line in path.read_text(errors="replace").splitlines():
        fields = line.split()
        if len(fields) < 7:
            continue
        try:
            index = int(fields[0])
            xyz = tuple(float(x) for x in fields[1:4])
            electrons = float(fields[4])
            min_dist = float(fields[5])
            volume = float(fields[6])
        except ValueError:
            continue
        if 1 <= index <= expected_atoms:
            atoms.append((index, *xyz, electrons, min_dist, volume))
    atoms.sort()
    if [row[0] for row in atoms] != list(range(1, expected_atoms + 1)):
        raise ValueError(
            f"ACF.dat does not contain exactly atoms 1..{expected_atoms}"
        )
    return atoms


def read_nelect(path):
    if not path.is_file():
        return None
    values = re.findall(
        r"\bNELECT\s*=\s*([-+0-9.Ee]+)", path.read_text(errors="replace")
    )
    return float(values[-1]) if values else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tolerance", type=float, default=0.05)
    args = parser.parse_args()

    symbols, counts, elements, species_indices = poscar_species(Path("POSCAR"))
    pot_data = potcar_zvals(Path("POTCAR"))
    pot_symbols = [item[0] for item in pot_data]
    if symbols != pot_symbols:
        raise ValueError(
            f"POSCAR species {symbols} do not match POTCAR species {pot_symbols}"
        )
    zval_by_species = dict(pot_data)
    atoms = read_acf(Path("ACF.dat"), len(elements))

    rows = []
    for atom, element, species_index in zip(atoms, elements, species_indices):
        index, x, y, z, electrons, min_dist, volume = atom
        reference = zval_by_species[element]
        charge_transfer = reference - electrons
        rows.append(
            [
                index, element, species_index, x, y, z, electrons,
                reference, charge_transfer, min_dist, volume,
            ]
        )

    with Path("bader_per_atom.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "atom_index", "element", "species_index", "x_A", "y_A", "z_A",
                "bader_electrons", "reference_valence", "charge_transfer_e",
                "min_distance_A", "atomic_volume_A3",
            ]
        )
        writer.writerows(rows)

    nelect = read_nelect(Path("OUTCAR"))
    bader_total = sum(row[6] for row in rows)
    difference = abs(nelect - bader_total) if nelect is not None else None
    status = (
        "NO_NELECT" if difference is None
        else "OK" if difference <= args.tolerance
        else "CHECK_GRID_OR_RUN"
    )

    element_sums = {}
    for row in rows:
        element_sums.setdefault(row[1], [0, 0.0, 0.0])
        element_sums[row[1]][0] += 1
        element_sums[row[1]][1] += row[6]
        element_sums[row[1]][2] += row[8]

    with Path("bader_summary.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "element", "atom_count", "bader_electrons",
                "charge_transfer_e", "nelect", "bader_total",
                "abs_difference", "tolerance", "status",
            ]
        )
        for element in symbols:
            count, electrons, transfer = element_sums[element]
            writer.writerow(
                [
                    element, count, f"{electrons:.8f}", f"{transfer:.8f}",
                    "" if nelect is None else f"{nelect:.8f}",
                    f"{bader_total:.8f}",
                    "" if difference is None else f"{difference:.8f}",
                    f"{args.tolerance:.8f}", status,
                ]
            )

    print(f"[OK] Analyzed {len(rows)} atoms: {' '.join(symbols)}")
    print(f"[OK] Total Bader electrons: {bader_total:.8f}")
    if nelect is None:
        print("[WARN] NELECT was not found in OUTCAR")
    else:
        print(f"[OK] NELECT: {nelect:.8f}; absolute difference: {difference:.8f}")
    print(f"[{status}] Charge conservation status")
    print("[SUCCESS] Wrote bader_per_atom.csv and bader_summary.csv")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        raise SystemExit(1)
