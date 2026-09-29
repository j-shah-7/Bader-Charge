# Synthetic Ag path for workflow demonstration

These are **invented numbers**, not VASP/Bader output or research evidence.
The four atom rows and three path images (00, 01, 02) demonstrate the CSV
format expected by the repository's analysis scripts. Atom #1 is designated
as the example migrating Ag atom. Its illustrative charge transfer is +0.20,
+0.45, and +0.70 e, respectively; the other values balance the toy charge
total. The `bader_summary.csv` rows are consistent with the per-atom rows,
using example reference valences Ag=11, B=3, N=5.

From the repository root:

```bash
python3 analysis-scripts/collect_bader_results.py examples/synthetic-ag-path \
    --output /tmp/example_bader_summary.csv
python3 analysis-scripts/neb_charge_summary.py /tmp/example_bader_summary.csv \
    --output /tmp/example_neb_charge_summary.csv
python3 analysis-scripts/plot_migrating_metal.py \
    examples/synthetic-ag-path/silver/vacancy-path --atom-index 1 \
    --output /tmp/example_ag_charge.png
```

The plot command requires Matplotlib. For actual work, verify that atom order
is identical across path images and identify the migrant's POSCAR atom index
explicitly. Do not interpret these illustrative values as physical results.
