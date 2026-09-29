# Bader charge analysis for metal/h-BN switching paths

Python and SLURM tools to prepare static VASP charge-density calculations, run
Bader partitioning, and compare atom-resolved charge transfer across images of
Au, Ag, or Cu interacting with h-BN. This repository supports the computational
workflow behind studies of metal migration and defect-assisted switching in
two-dimensional materials.

**What it produces:** `bader_per_atom.csv` for each image,
`bader_summary.csv` for each element, combined image tables, and plots of
charge transfer along a path. Here `charge_transfer_e = POTCAR ZVAL - Bader
electrons`; a positive value indicates electron loss by that atom.

## Try the analysis without VASP

A small **synthetic illustration**, clearly separate from research results,
is in [`examples/synthetic-ag-path/`](examples/synthetic-ag-path/). It contains
three image folders with four atoms each, so you can try the collection and
plotting scripts without VASP, POTCAR, HPC access, or the Bader executable:

```bash
python3 analysis-scripts/collect_bader_results.py examples/synthetic-ag-path \
    --output /tmp/example_bader_summary.csv
python3 analysis-scripts/neb_charge_summary.py /tmp/example_bader_summary.csv \
    --output /tmp/example_neb_charge_summary.csv
python3 analysis-scripts/plot_migrating_metal.py \
    examples/synthetic-ag-path/silver/vacancy-path --atom-index 1 \
    --output /tmp/example_ag_charge.png
```

Only the last command requires Matplotlib. In this illustrative example the
selected Ag atom changes from +0.20 to +0.70 e across images 00–02. These
numbers are invented to demonstrate the data format and **are not calculated
research results**. The script requires an explicit atom index because the
migrating atom cannot safely be inferred from element alone.

## Full VASP workflow

The full setup requires your own licensed VASP installation, POTCAR files,
structure inputs, and cluster configuration. Neither VASP nor POTCAR data is
provided here. Review `Input-files/bader-441.sh` and
`Input-files/bader-gamma.sh` before submitting jobs: the module versions,
partition, email, and VASP binary paths are site-specific. The bundled Bader
executable should likewise be checked against its redistribution terms before
reuse or redistribution.

This workflow prepares, submits, postprocesses, and summarizes static Bader
calculations for:

- isolated Au/Ag/Cu atoms on monolayer h-BN (`4 x 4 x 1` KPOINTS, `vasp_std`);
- metal/h-BN heterostructures (Gamma-only KPOINTS, `vasp_gam`).

The structure type is detected from the POSCAR contents. Exactly one non-B/N
atom means `isolated`; more than one means `heterostructure`.

## Where the files go

For a full calculation, put this repository's files in a working directory with your own `POSCAR-withpotcar/` inputs. The expected layout is:

```text
Bader/
├── setup_bader_calculations.py
├── submit_all.sh
├── postprocess_all.sh
├── Input-files/
│   ├── INCAR
│   ├── KPOINTS-441
│   ├── KPOINTS-Gamma
│   ├── bader-441.sh
│   ├── bader-gamma.sh
│   ├── validate_vasp_inputs.py
│   └── run_bader_single.sh
├── analysis-scripts/
├── postprocess-scripts/
│   ├── bader
│   └── chgsum.pl
└── POSCAR-withpotcar/   # user-provided; absent from this repository
```

The included SLURM templates were configured for one HPC site. Edit the module loads, executable paths, scheduler settings, and email before using them elsewhere.

## 1. Prepare all folders

The repository does not include `POSCAR-withpotcar/`; create it with your own
POSCAR/POTCAR inputs before running setup. Run from the repository root:

```bash
chmod +x submit_all.sh postprocess_all.sh
python3 setup_bader_calculations.py --dry-run
python3 setup_bader_calculations.py
```

The output is `Bader-calculations/<metal>/<case>/<image>/`. Each image folder
contains POSCAR, matching POTCAR, INCAR, the correct KPOINTS, `bader-job.sh`,
and the Bader tools.

The setup stops before copying anything if a populated source folder has a
missing POTCAR, a duplicate image number, or a POSCAR/POTCAR species-order
mismatch. Existing destination folders are not replaced unless `--force` is
explicitly supplied. Even with `--force`, the script refuses to remove a folder
that contains VASP/Bader results or any unrecognized file.

## 2. Review and submit

First list what would be submitted:

```bash
./submit_all.sh Bader-calculations --dry-run
```

Then submit:

```bash
./submit_all.sh
```

Each job validates the structure type, POSCAR/POTCAR order, KPOINTS mesh, and
required INCAR flags before VASP starts. After VASP, it checks CHGCAR, AECCAR0,
and AECCAR2, runs `chgsum.pl`, runs Bader with `CHGCAR_sum` as the reference,
and writes:

- `ACF.dat`
- `bader_per_atom.csv`
- `bader_summary.csv`

`charge_transfer_e = POTCAR ZVAL - Bader electrons`. Positive values mean the
atom lost electron density; negative values mean it gained electron density.

## 3. Re-run postprocessing without rerunning VASP

If VASP completed but postprocessing did not:

```bash
./postprocess_all.sh
```

## 4. Combine and plot results

From the main `Bader` folder:

```bash
python3 analysis-scripts/collect_bader_results.py
python3 analysis-scripts/neb_charge_summary.py
python3 analysis-scripts/plot_all_bader.py
python3 analysis-scripts/plot_overlapped_bader.py \
  Bader-calculations/gold/bvac-isolated-vert-diff
```

The plotting scripts require Matplotlib (`python3 -m pip install matplotlib`). The calculation and CSV analysis
scripts use only the Python standard library.

`delta_q.py` remains available for upgrading old two-column
`bader_per_atom.csv` files, but new runs do not need it because
`bader_analysis.py` now writes `charge_transfer_e` directly.

## Important calculation note

The revised INCAR uses `ISTART=0`, `ICHARG=2`, and `NSW=0`, so it does not
silently require WAVECAR/CHGCAR restart files. It retains the original
`ISMEAR=1`, `SIGMA=0.10`, D3, and 520 eV settings. If the original calculations
were spin-polarized or used different occupation settings, update this INCAR
to match them before preparing the folders.

The committed SLURM templates request `-c 2` and set `OMP_NUM_THREADS=2`.
Confirm the MPI/OpenMP layout, number of tasks, memory, and scheduler policy
for your site before submitting jobs.
