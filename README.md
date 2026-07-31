# VASP Bader workflow for h-BN structures

This workflow prepares, submits, postprocesses, and summarizes static Bader
calculations for:

- isolated Au/Ag/Cu atoms on monolayer h-BN (`4 x 4 x 1` KPOINTS, `vasp_std`);
- metal/h-BN heterostructures (Gamma-only KPOINTS, `vasp_gam`).

The structure type is detected from the POSCAR contents. Exactly one non-B/N
atom means `isolated`; more than one means `heterostructure`.

## Where the files go

Merge the downloaded workflow into the main `Bader` folder so the layout is:

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
└── POSCAR-withpotcar/
```

The supplied `bader-441.sh` and `bader-gamma.sh` are based on the Pathfinder
SLURM scripts supplied by the user. They retain the VASP executable paths and
the requested resource settings.

## 1. Prepare all folders

Run from the main `Bader` folder:

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

The plotting scripts require Matplotlib. The calculation and CSV analysis
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

The supplied SLURM scripts retain `-c 4` and `OMP_NUM_THREADS=2` exactly as in
the user's working scripts. This reserves four CPUs per MPI task while using
two OpenMP threads. Confirm that this is intentional for the local VASP build
and scheduler policy before submitting all jobs.
