#!/usr/bin/env python3
"""Create one static Bader calculation folder for every source POSCAR."""

import argparse
import csv
import hashlib
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Record:
    source: Path
    potcar: Path
    relative_case: Path
    image: str
    species: tuple
    counts: tuple
    structure_type: str


def poscar_info(path):
    lines = path.read_text(errors="replace").splitlines()
    if len(lines) < 8:
        raise ValueError(f"{path}: POSCAR is too short")
    species = tuple(lines[5].split())
    try:
        counts = tuple(int(x) for x in lines[6].split())
    except ValueError as exc:
        raise ValueError(f"{path}: VASP 5 species/count lines required") from exc
    if not species or len(species) != len(counts):
        raise ValueError(f"{path}: species/count columns do not agree")
    return species, counts


def potcar_species(path):
    out = []
    for line in path.read_text(errors="replace").splitlines():
        if "TITEL" in line:
            fields = line.split("=", 1)[-1].split()
            if len(fields) >= 2:
                out.append(fields[1].split("_")[0])
    if not out:
        raise ValueError(f"{path}: no TITEL records found")
    return tuple(out)


def image_number(path):
    matches = re.findall(r"(?<!\d)(\d{2})(?!\d)", path.name)
    if not matches:
        raise ValueError(f"{path}: cannot identify a two-digit image number")
    # The image is the first standalone two-digit token.  Some descriptive
    # suffixes contain later numbers such as "4x16nodes".
    return matches[0]


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def collect(source_root):
    records = []
    empty = []
    for case in sorted(p for p in source_root.rglob("*") if p.is_dir()):
        poscars = sorted(p for p in case.glob("POSCAR*") if p.is_file())
        if not poscars:
            if case.parent.name in {"gold", "silver", "copper"}:
                empty.append(case.relative_to(source_root))
            continue
        potcar = case / "POTCAR"
        if not potcar.is_file():
            raise ValueError(f"{case}: POTCAR is missing")
        pot_order = potcar_species(potcar)
        seen_images = set()
        for poscar in poscars:
            species, counts = poscar_info(poscar)
            if species != pot_order:
                raise ValueError(
                    f"{poscar}: POSCAR order {species} != POTCAR order {pot_order}"
                )
            image = image_number(poscar)
            if image in seen_images:
                raise ValueError(f"{case}: duplicate image number {image}")
            seen_images.add(image)
            metal_count = sum(
                count for symbol, count in zip(species, counts)
                if symbol not in {"B", "N"}
            )
            if metal_count < 1:
                raise ValueError(f"{poscar}: no metal atoms detected")
            structure_type = "isolated" if metal_count == 1 else "heterostructure"
            records.append(
                Record(
                    source=poscar,
                    potcar=potcar,
                    relative_case=case.relative_to(source_root),
                    image=image,
                    species=species,
                    counts=counts,
                    structure_type=structure_type,
                )
            )
    return records, empty


def require_assets(root, input_dir):
    assets = {
        "INCAR": input_dir / "INCAR",
        "KPOINTS-441": input_dir / "KPOINTS-441",
        "KPOINTS-Gamma": input_dir / "KPOINTS-Gamma",
        "bader-441.sh": input_dir / "bader-441.sh",
        "bader-gamma.sh": input_dir / "bader-gamma.sh",
        "validator": input_dir / "validate_vasp_inputs.py",
        "runner": input_dir / "run_bader_single.sh",
        "analyzer": root / "analysis-scripts" / "bader_analysis.py",
        "bader": root / "postprocess-scripts" / "bader",
        "chgsum": root / "postprocess-scripts" / "chgsum.pl",
    }
    missing = [str(path) for path in assets.values() if not path.is_file()]
    if missing:
        raise ValueError("Missing workflow assets:\n  " + "\n  ".join(missing))
    return assets


def safe_prepared_folder(path):
    """Only pristine setup outputs may be replaced; calculation data never are."""
    allowed = {
        "POSCAR", "POTCAR", "INCAR", "KPOINTS", "bader-job.sh",
        "validate_vasp_inputs.py", "run_bader_single.sh",
        "bader_analysis.py", "bader", "chgsum.pl",
    }
    return path.is_dir() and all(
        child.name in allowed and not child.is_dir() for child in path.iterdir()
    )


def main():
    parser = argparse.ArgumentParser(
        description="Prepare all static VASP+Bader calculations safely."
    )
    parser.add_argument("--source", default="POSCAR-withpotcar")
    parser.add_argument("--input-files", default="Input-files")
    parser.add_argument("--output", default="Bader-calculations")
    parser.add_argument(
        "--force", action="store_true",
        help="Replace previously prepared image folders (not VASP results).",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = Path.cwd()
    source_root = Path(args.source).resolve()
    input_dir = Path(args.input_files).resolve()
    output_root = Path(args.output).resolve()
    if not source_root.is_dir():
        raise ValueError(f"Source directory not found: {source_root}")
    assets = require_assets(root, input_dir)

    print("[STEP 1] Auditing every source POSCAR and POTCAR")
    records, empty = collect(source_root)
    if not records:
        raise ValueError("No POSCAR files were found")
    for folder in empty:
        print(f"[SKIP] Empty source folder: {folder}")
    isolated = sum(r.structure_type == "isolated" for r in records)
    hetero = len(records) - isolated
    print(f"[OK] {len(records)} matching POSCAR/POTCAR pairs")
    print(f"[OK] {isolated} isolated structures -> 4x4x1")
    print(f"[OK] {hetero} heterostructures -> Gamma only")

    destinations = [output_root / r.relative_case / r.image for r in records]
    existing = [p for p in destinations if p.exists()]
    if existing and not args.force:
        raise ValueError(
            f"{len(existing)} destination folders already exist. "
            "Use --force only if you intend to replace their prepared inputs."
        )
    unsafe = [p for p in existing if not safe_prepared_folder(p)]
    if unsafe:
        raise ValueError(
            "Refusing to replace folders containing calculation results or "
            "unrecognized files. Move/rename the existing output tree first:\n  "
            + "\n  ".join(map(str, unsafe[:10]))
        )

    print("[STEP 2] Preparing calculation folders")
    if args.dry_run:
        for record, dest in zip(records, destinations):
            print(f"[DRY RUN] {record.source} -> {dest} ({record.structure_type})")
        print("[SUCCESS] Dry run completed; no files were written")
        return

    output_root.mkdir(parents=True, exist_ok=True)
    manifest_rows = []
    for record, dest in zip(records, destinations):
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)

        shutil.copy2(record.source, dest / "POSCAR")
        shutil.copy2(record.potcar, dest / "POTCAR")
        shutil.copy2(assets["INCAR"], dest / "INCAR")
        if record.structure_type == "isolated":
            shutil.copy2(assets["KPOINTS-441"], dest / "KPOINTS")
            shutil.copy2(assets["bader-441.sh"], dest / "bader-job.sh")
        else:
            shutil.copy2(assets["KPOINTS-Gamma"], dest / "KPOINTS")
            shutil.copy2(assets["bader-gamma.sh"], dest / "bader-job.sh")
        shutil.copy2(assets["validator"], dest / "validate_vasp_inputs.py")
        shutil.copy2(assets["runner"], dest / "run_bader_single.sh")
        shutil.copy2(assets["analyzer"], dest / "bader_analysis.py")
        # Keep the 4.7 MB Bader binary in one central location.  These relative
        # links remain valid anywhere inside the generated three-level tree.
        (dest / "bader").symlink_to("../../../../postprocess-scripts/bader")
        (dest / "chgsum.pl").symlink_to("../../../../postprocess-scripts/chgsum.pl")
        for executable in ("bader-job.sh", "run_bader_single.sh"):
            (dest / executable).chmod((dest / executable).stat().st_mode | 0o100)

        if sha256(record.source) != sha256(dest / "POSCAR"):
            raise RuntimeError(f"Copy verification failed for {record.source}")
        copied_species, copied_counts = poscar_info(dest / "POSCAR")
        if copied_species != record.species or copied_counts != record.counts:
            raise RuntimeError(f"Structure verification failed in {dest}")
        manifest_rows.append(
            [
                str(record.relative_case),
                record.image,
                record.structure_type,
                "4x4x1" if record.structure_type == "isolated" else "Gamma-only",
                " ".join(record.species),
                " ".join(map(str, record.counts)),
                sum(record.counts),
                str(record.source),
                str(dest),
            ]
        )
        print(
            f"[OK] {record.relative_case}/{record.image}: "
            f"{record.structure_type}, {sum(record.counts)} atoms"
        )

    manifest = output_root / "setup_manifest.csv"
    with manifest.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "case", "image", "structure_type", "kpoints",
                "species", "counts", "total_atoms", "source", "destination",
            ]
        )
        writer.writerows(manifest_rows)
    print(f"[OK] Manifest written: {manifest}")
    print(f"[SUCCESS] Prepared {len(records)} Bader calculation folders")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        raise SystemExit(1)
