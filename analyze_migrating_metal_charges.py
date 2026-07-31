#!/usr/bin/env python3
"""Build per-metal Bader charge tables for isolated and heterostructure paths.

Expected layout:

    Bader-calculations/<gold|silver|copper>/<calculation-type>/<image>/
        POSCAR
        bader_per_atom.csv

The migrating atom is the only metal atom in isolated calculations.  In a
heterostructure it is detected once per path as the metal atom with the largest
cumulative minimum-image displacement through the ordered POSCAR images.
Detection can be overridden with a CSV file (see --write-override-template).

Charge convention:

    charge_transfer_e = POTCAR ZVAL - Bader electrons

Positive values mean electron loss; negative values mean electron gain.
"""

from __future__ import annotations

import argparse
import csv
import math
import shutil
import sys
from collections import defaultdict
from pathlib import Path


METAL_BY_FOLDER = {"gold": "Au", "silver": "Ag", "copper": "Cu"}
OUTPUT_NAMES = {
    "gold": "gold_charge_table.csv",
    "silver": "silver_charge_table.csv",
    "copper": "copper_charge_table.csv",
}


def natural_image_key(path: Path):
    name = path.name
    return (0, int(name)) if name.isdigit() else (1, name)


def cross(u, v):
    return (
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    )


def dot(u, v):
    return sum(a * b for a, b in zip(u, v))


def frac_to_cart(frac, lattice):
    return tuple(
        frac[0] * lattice[0][j]
        + frac[1] * lattice[1][j]
        + frac[2] * lattice[2][j]
        for j in range(3)
    )


def cart_to_frac(cart, lattice):
    a, b, c = lattice
    det = dot(a, cross(b, c))
    if abs(det) < 1.0e-12:
        raise ValueError("POSCAR lattice is singular")
    return (
        dot(cart, cross(b, c)) / det,
        dot(cart, cross(c, a)) / det,
        dot(cart, cross(a, b)) / det,
    )


def read_poscar(path: Path):
    lines = path.read_text(errors="replace").splitlines()
    if len(lines) < 8:
        raise ValueError(f"{path}: POSCAR is too short")
    scale_fields = lines[1].split()
    if len(scale_fields) != 1:
        raise ValueError(f"{path}: only the usual single POSCAR scale is supported")
    scale = float(scale_fields[0])
    if scale <= 0:
        raise ValueError(f"{path}: negative/zero POSCAR scale is not supported")
    lattice = []
    for line in lines[2:5]:
        values = [float(x) * scale for x in line.split()[:3]]
        if len(values) != 3:
            raise ValueError(f"{path}: invalid lattice vector")
        lattice.append(tuple(values))

    symbols = lines[5].split()
    try:
        counts = [int(x) for x in lines[6].split()]
    except ValueError as exc:
        raise ValueError(f"{path}: VASP 5 element symbols are required") from exc
    if not symbols or len(symbols) != len(counts):
        raise ValueError(f"{path}: species/count columns do not agree")

    cursor = 7
    if lines[cursor].strip().lower().startswith("s"):
        cursor += 1
    mode = lines[cursor].strip().lower()
    cursor += 1
    if not (mode.startswith("d") or mode.startswith("c") or mode.startswith("k")):
        raise ValueError(f"{path}: coordinate mode is not Direct or Cartesian")

    total = sum(counts)
    if len(lines) < cursor + total:
        raise ValueError(f"{path}: expected {total} coordinate rows")
    frac_coords = []
    for line in lines[cursor : cursor + total]:
        values = [float(x) for x in line.split()[:3]]
        if len(values) != 3:
            raise ValueError(f"{path}: invalid coordinate row")
        if mode.startswith("d"):
            frac_coords.append(tuple(values))
        else:
            cart = tuple(x * scale for x in values)
            frac_coords.append(cart_to_frac(cart, lattice))

    elements = []
    species_indices = []
    for symbol, count in zip(symbols, counts):
        elements.extend([symbol] * count)
        species_indices.extend(range(1, count + 1))
    return {
        "symbols": symbols,
        "counts": counts,
        "elements": elements,
        "species_indices": species_indices,
        "lattice": lattice,
        "frac": frac_coords,
    }


def minimum_image_distance(frac_a, frac_b, lattice):
    delta = [b - a for a, b in zip(frac_a, frac_b)]
    delta = [value - round(value) for value in delta]
    cart = frac_to_cart(delta, lattice)
    return math.sqrt(dot(cart, cart))


def load_overrides(path: Path | None):
    overrides = {}
    if path is None:
        return overrides
    with path.open(newline="") as handle:
        for line_number, row in enumerate(csv.DictReader(handle), start=2):
            try:
                metal_folder = row["metal_folder"].strip().lower()
                calculation_type = row["calculation_type"].strip()
                atom_index = int(row["migrating_atom_global_index"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"{path}:{line_number}: invalid override row") from exc
            key = (metal_folder, calculation_type)
            if key in overrides:
                raise ValueError(f"{path}:{line_number}: duplicate override for {key}")
            overrides[key] = atom_index
    return overrides


def identify_migrating_atom(image_dirs, metal_symbol, override_index=None):
    structures = [read_poscar(folder / "POSCAR") for folder in image_dirs]
    reference = structures[0]
    signature = (reference["symbols"], reference["counts"], len(reference["elements"]))
    for folder, structure in zip(image_dirs[1:], structures[1:]):
        other = (structure["symbols"], structure["counts"], len(structure["elements"]))
        if other != signature:
            raise ValueError(f"{folder}/POSCAR: atom order/count differs within path")

    metal_indices = [
        i for i, element in enumerate(reference["elements"]) if element == metal_symbol
    ]
    if not metal_indices:
        raise ValueError(f"metal species {metal_symbol} is absent from POSCAR")

    path_lengths = {}
    for index in metal_indices:
        length = 0.0
        for previous, current in zip(structures, structures[1:]):
            length += minimum_image_distance(
                previous["frac"][index], current["frac"][index], current["lattice"]
            )
        path_lengths[index + 1] = length

    if override_index is not None:
        if override_index < 1 or override_index > len(reference["elements"]):
            raise ValueError(f"override atom {override_index} is outside the POSCAR")
        if reference["elements"][override_index - 1] != metal_symbol:
            actual = reference["elements"][override_index - 1]
            raise ValueError(
                f"override atom {override_index} is {actual}, not {metal_symbol}"
            )
        selected = override_index
        method = "manual_override"
    elif len(metal_indices) == 1:
        selected = metal_indices[0] + 1
        method = "only_metal_atom"
    else:
        selected = max(path_lengths, key=path_lengths.get)
        method = "largest_cumulative_displacement"

    ranked = sorted(path_lengths.values(), reverse=True)
    selected_score = path_lengths[selected]
    second_score = next(
        (path_lengths[i] for i in sorted(path_lengths, key=path_lengths.get, reverse=True)
         if i != selected),
        0.0,
    )
    ratio = math.inf if second_score == 0 and selected_score > 0 else (
        selected_score / second_score if second_score > 0 else 1.0
    )
    if len(metal_indices) == 1 or override_index is not None:
        confidence = "confirmed"
    elif ratio >= 2.0:
        confidence = "high"
    elif ratio >= 1.25:
        confidence = "moderate_review_recommended"
    else:
        confidence = "low_manual_override_recommended"

    return {
        "global_index": selected,
        "species_index": reference["species_indices"][selected - 1],
        "method": method,
        "path_length_A": selected_score,
        "second_path_length_A": second_score,
        "ratio": ratio,
        "confidence": confidence,
        "metal_count": len(metal_indices),
    }


def read_per_atom(path: Path, expected_atoms: int):
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"atom_index", "element", "species_index", "charge_transfer_e"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"{path}: required columns are missing")
    parsed = []
    for row in rows:
        parsed.append(
            {
                "atom_index": int(row["atom_index"]),
                "element": row["element"].strip(),
                "species_index": int(row["species_index"]),
                "charge": float(row["charge_transfer_e"]),
            }
        )
    parsed.sort(key=lambda row: row["atom_index"])
    if [row["atom_index"] for row in parsed] != list(range(1, expected_atoms + 1)):
        raise ValueError(f"{path}: atom indices do not equal 1..{expected_atoms}")
    return parsed


FIELDS = [
    "metal_folder", "metal_element", "calculation_type", "image",
    "migrating_atom_global_index", "migrating_atom_species_index",
    "migrating_atom_charge_e", "remaining_metal_atom_count",
    "remaining_metal_total_charge_e", "B_atom_count", "B_total_charge_e",
    "N_atom_count", "N_total_charge_e", "system_total_charge_e",
    "identification_method", "identification_confidence",
    "migrating_path_length_A", "second_metal_path_length_A",
    "path_length_ratio", "calculation_directory",
]


def format_float(value):
    if math.isinf(value):
        return "inf"
    return f"{value:.8f}"


def build_row(metal_folder, case, image_dir, metal_symbol, identity, atoms):
    migrating = next(
        row for row in atoms if row["atom_index"] == identity["global_index"]
    )
    if migrating["element"] != metal_symbol:
        raise ValueError(
            f"{image_dir}: selected atom is {migrating['element']}, not {metal_symbol}"
        )
    remaining_metal = [
        row for row in atoms
        if row["element"] == metal_symbol and row["atom_index"] != identity["global_index"]
    ]
    boron = [row for row in atoms if row["element"] == "B"]
    nitrogen = [row for row in atoms if row["element"] == "N"]
    return {
        "metal_folder": metal_folder,
        "metal_element": metal_symbol,
        "calculation_type": case,
        "image": image_dir.name,
        "migrating_atom_global_index": identity["global_index"],
        "migrating_atom_species_index": identity["species_index"],
        "migrating_atom_charge_e": format_float(migrating["charge"]),
        "remaining_metal_atom_count": len(remaining_metal),
        "remaining_metal_total_charge_e": format_float(
            sum(row["charge"] for row in remaining_metal)
        ),
        "B_atom_count": len(boron),
        "B_total_charge_e": format_float(sum(row["charge"] for row in boron)),
        "N_atom_count": len(nitrogen),
        "N_total_charge_e": format_float(sum(row["charge"] for row in nitrogen)),
        "system_total_charge_e": format_float(sum(row["charge"] for row in atoms)),
        "identification_method": identity["method"],
        "identification_confidence": identity["confidence"],
        "migrating_path_length_A": format_float(identity["path_length_A"]),
        "second_metal_path_length_A": format_float(identity["second_path_length_A"]),
        "path_length_ratio": format_float(identity["ratio"]),
        "calculation_directory": str(image_dir),
    }


def write_csv(path: Path, rows):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_override_template(path: Path, identities):
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metal_folder", "calculation_type", "migrating_atom_global_index"])
        for metal_folder, case, identity in identities:
            writer.writerow([metal_folder, case, identity["global_index"]])


def main():
    parser = argparse.ArgumentParser(
        description="Create Au, Ag, and Cu migrating/rest-metal/B/N Bader tables."
    )
    parser.add_argument("root", nargs="?", default="Bader-calculations")
    parser.add_argument("--output-dir", default="Bader-charge-tables")
    parser.add_argument("--overrides", type=Path)
    parser.add_argument(
        "--write-override-template", action="store_true",
        help="write detected_migrating_atom_overrides.csv in the output directory",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="fail if any image lacks POSCAR or bader_per_atom.csv",
    )
    parser.add_argument("--force", action="store_true", help="replace output directory")
    args = parser.parse_args()

    root = Path(args.root)
    output = Path(args.output_dir)
    if not root.is_dir():
        raise ValueError(f"calculation root does not exist: {root}")
    # Load this before --force can replace an output directory containing an
    # edited copy of the generated override template.
    overrides = load_overrides(args.overrides)
    if output.exists():
        if not args.force:
            raise ValueError(f"output exists: {output}; use --force to replace it")
        if output.is_dir():
            shutil.rmtree(output)
        else:
            output.unlink()
    output.mkdir(parents=True)
    print(f"[OK] Calculation root: {root}")
    print(f"[OK] Output directory created: {output}")

    if args.overrides:
        print(f"[OK] Loaded {len(overrides)} migrating-atom overrides")

    all_rows = []
    rows_by_metal = defaultdict(list)
    identities = []
    warnings = 0
    series_count = 0

    for metal_folder, metal_symbol in METAL_BY_FOLDER.items():
        metal_root = root / metal_folder
        if not metal_root.is_dir():
            print(f"[WARN] Missing metal folder: {metal_root}")
            warnings += 1
            continue
        for case_dir in sorted(path for path in metal_root.iterdir() if path.is_dir()):
            image_dirs = sorted(
                [path for path in case_dir.iterdir() if path.is_dir() and path.name.isdigit()],
                key=natural_image_key,
            )
            usable = [path for path in image_dirs if (path / "POSCAR").is_file()]
            if not usable:
                print(f"[WARN] No image POSCARs: {case_dir}")
                warnings += 1
                continue
            missing_poscars = [path for path in image_dirs if not (path / "POSCAR").is_file()]
            if missing_poscars:
                message = f"missing POSCAR in {len(missing_poscars)} images under {case_dir}"
                if args.strict:
                    raise ValueError(message)
                print(f"[WARN] {message}")
                warnings += 1

            override = overrides.get((metal_folder, case_dir.name))
            try:
                identity = identify_migrating_atom(usable, metal_symbol, override)
            except (OSError, ValueError) as exc:
                message = f"cannot identify migrating atom for {case_dir}: {exc}"
                if args.strict:
                    raise ValueError(message) from exc
                print(f"[WARN] {message}")
                warnings += 1
                continue
            identities.append((metal_folder, case_dir.name, identity))
            series_count += 1
            ratio_text = format_float(identity["ratio"])
            print(
                f"[OK] {metal_folder}/{case_dir.name}: migrating {metal_symbol} "
                f"global #{identity['global_index']} (species #{identity['species_index']}), "
                f"method={identity['method']}, confidence={identity['confidence']}, "
                f"path-ratio={ratio_text}"
            )

            analyzed = 0
            for image_dir in usable:
                per_atom = image_dir / "bader_per_atom.csv"
                if not per_atom.is_file():
                    message = f"missing bader_per_atom.csv: {image_dir}"
                    if args.strict:
                        raise ValueError(message)
                    print(f"[WARN] {message}")
                    warnings += 1
                    continue
                structure = read_poscar(image_dir / "POSCAR")
                atoms = read_per_atom(per_atom, len(structure["elements"]))
                if [row["element"] for row in atoms] != structure["elements"]:
                    raise ValueError(f"{per_atom}: species/order does not match POSCAR")
                row = build_row(
                    metal_folder, case_dir.name, image_dir, metal_symbol, identity, atoms
                )
                all_rows.append(row)
                rows_by_metal[metal_folder].append(row)
                analyzed += 1
                print(f"[OK] Analyzed {metal_folder}/{case_dir.name}/{image_dir.name}")
            print(f"[OK] Completed {analyzed}/{len(usable)} Bader images for {case_dir}")

    if not all_rows:
        raise ValueError("no completed bader_per_atom.csv files were found")

    write_csv(output / "all_metals_charge_table.csv", all_rows)
    print(f"[SUCCESS] Wrote {output / 'all_metals_charge_table.csv'}")
    for metal_folder, filename in OUTPUT_NAMES.items():
        rows = rows_by_metal.get(metal_folder, [])
        write_csv(output / filename, rows)
        print(f"[SUCCESS] Wrote {output / filename} ({len(rows)} rows)")

    if args.write_override_template:
        template = output / "detected_migrating_atom_overrides.csv"
        write_override_template(template, identities)
        print(f"[SUCCESS] Wrote {template}")

    print(
        f"[SUCCESS] Finished: {series_count} paths, {len(all_rows)} image rows, "
        f"{warnings} warning(s)"
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, StopIteration) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        raise SystemExit(1)
