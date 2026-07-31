#!/usr/bin/env python3
"""Fail-fast validation for one prepared Bader calculation directory."""

import argparse
import re
import sys
from pathlib import Path


def poscar_species_counts(path: Path):
    lines = path.read_text(errors="replace").splitlines()
    if len(lines) < 8:
        raise ValueError("POSCAR is too short")
    species = lines[5].split()
    try:
        counts = [int(x) for x in lines[6].split()]
    except ValueError as exc:
        raise ValueError("VASP 5-style species and count lines are required") from exc
    if len(species) != len(counts) or not species:
        raise ValueError("POSCAR species/count columns do not agree")
    return species, counts


def potcar_species(path: Path):
    species = []
    for line in path.read_text(errors="replace").splitlines():
        if "TITEL" not in line:
            continue
        fields = line.split("=", 1)[-1].split()
        if len(fields) >= 2:
            species.append(fields[1].split("_")[0])
    if not species:
        raise ValueError("No TITEL records found in POTCAR")
    return species


def incar_tags(path: Path):
    tags = {}
    for raw in path.read_text(errors="replace").splitlines():
        line = raw.split("#", 1)[0].split("!", 1)[0].strip()
        if "=" in line:
            key, value = line.split("=", 1)
            tags[key.strip().upper()] = value.strip().upper()
    return tags


def kpoint_mesh(path: Path):
    lines = [x.strip() for x in path.read_text(errors="replace").splitlines() if x.strip()]
    if len(lines) < 4:
        raise ValueError("KPOINTS is too short")
    try:
        return tuple(int(x) for x in lines[3].split()[:3])
    except ValueError as exc:
        raise ValueError("Cannot read the automatic KPOINTS mesh") from exc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--expected-kpoints",
        required=True,
        choices=("isolated", "heterostructure"),
    )
    args = parser.parse_args()

    for name in ("POSCAR", "POTCAR", "INCAR", "KPOINTS"):
        path = Path(name)
        if not path.is_file() or path.stat().st_size == 0:
            raise SystemExit(f"[FAIL] Missing or empty required file: {name}")

    pos_species, counts = poscar_species_counts(Path("POSCAR"))
    pot_species = potcar_species(Path("POTCAR"))
    if pos_species != pot_species:
        raise SystemExit(
            "[FAIL] POSCAR/POTCAR species mismatch:\n"
            f"       POSCAR: {' '.join(pos_species)}\n"
            f"       POTCAR: {' '.join(pot_species)}"
        )
    print(f"[OK] POSCAR/POTCAR order: {' '.join(pos_species)}")
    print(f"[OK] Atom counts: {' '.join(map(str, counts))} (total {sum(counts)})")

    metal_count = sum(c for s, c in zip(pos_species, counts) if s not in {"B", "N"})
    detected = "isolated" if metal_count == 1 else "heterostructure"
    if detected != args.expected_kpoints:
        raise SystemExit(
            f"[FAIL] Structure detected as {detected}, but job expects "
            f"{args.expected_kpoints}"
        )
    print(f"[OK] Structure type: {detected} ({metal_count} metal atoms)")

    expected_mesh = (4, 4, 1) if detected == "isolated" else (1, 1, 1)
    actual_mesh = kpoint_mesh(Path("KPOINTS"))
    if actual_mesh != expected_mesh:
        raise SystemExit(
            f"[FAIL] KPOINTS mesh is {actual_mesh}; expected {expected_mesh}"
        )
    print(f"[OK] KPOINTS mesh: {'x'.join(map(str, actual_mesh))}")

    tags = incar_tags(Path("INCAR"))
    for tag in ("LAECHG", "LCHARG"):
        if tags.get(tag) not in {".TRUE.", "TRUE", "T"}:
            raise SystemExit(f"[FAIL] INCAR must set {tag}=.TRUE.")
    if tags.get("NSW") not in {"0", "0.0"}:
        raise SystemExit("[FAIL] INCAR must set NSW=0 for this static calculation")
    print("[OK] INCAR requests CHGCAR, AECCAR0, and AECCAR2")
    print("[SUCCESS] All VASP input checks passed")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        raise SystemExit(1)
