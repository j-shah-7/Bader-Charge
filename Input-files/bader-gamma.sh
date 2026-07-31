#!/bin/bash
#SBATCH -J Bader-Gamma
#SBATCH -p parallel
#SBATCH -q normal
#SBATCH -N 1
#SBATCH -n 64
#SBATCH -c 2
#SBATCH -t 04:00:00
#SBATCH --mem-per-cpu=2gb
#SBATCH --mail-user=jfatheema@utexas.edu
#SBATCH --mail-type=END

set -euo pipefail

echo "============================================================"
echo "[START] $(date)"
echo "[INFO]  Job ID: ${SLURM_JOB_ID:-not-set}"
echo "[INFO]  Nodes:  ${SLURM_JOB_NODELIST:-not-set}"

echo "[STEP 1] Loading VASP modules"
module load gcc/12.4.0 openmpi/5.0.5 fftw/3.3.10-omp openblas/0.3.28-omp netlib-scalapack/2.2.0-mpi
module list
echo "[OK] Module setup succeeded"

cd "${SLURM_SUBMIT_DIR:?SLURM_SUBMIT_DIR is not set}"
echo "[OK] Working directory: $(pwd)"

echo "[STEP 2] Validating POSCAR, POTCAR, INCAR, and Gamma-only KPOINTS"
python3 validate_vasp_inputs.py --expected-kpoints heterostructure
echo "[OK] Input validation succeeded"

export OMP_NUM_THREADS=2
echo "[INFO] OMP_NUM_THREADS=${OMP_NUM_THREADS}"

echo "[STEP 3] Running vasp_gam"
time srun --cpu-bind=cores /projects/hpcl-mat269/proj-shared/liangbo/vasp_bin/vasp_gam > stdout
test -s OUTCAR
test -s CHGCAR
test -s AECCAR0
test -s AECCAR2
grep -q "General timing and accounting" OUTCAR
echo "[OK] VASP completed and charge-density files exist"

echo "[STEP 4] Running Bader partitioning and per-atom analysis"
bash run_bader_single.sh
echo "[OK] Bader analysis succeeded"

echo "[FINISH] $(date)"
echo "============================================================"
