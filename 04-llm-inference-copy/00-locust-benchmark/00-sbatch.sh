#!/bin/bash

# SPDX-FileCopyrightText: 2026 Isac Pasianotto <isac.pasianotto@phd.units.it>
# SPDX-FileCopyrightText: 2026 Niccolo Tosato <niccolo.tosato@phd.units.it>
#
# SPDX-License-Identifier: GPL-3.0-or-later

#SBATCH --job-name=llm-benchmark
#SBATCH --output=logs/benchmark_%j.out
#SBATCH --error=logs/benchmark_%j.err
#SBATCH --time=01:30:00            
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --partition=GENOA
#SBATCH --mem=128G


SCRIPT_DIR="$SLURM_SUBMIT_DIR"
echo "If present, source a virtual env ! Remember to install requirements.txt provided in the repository root"
MODELS=(
    "GPT-OSS-120B"
    "Qwen3-VL-235B-Thinking"
    "Llama-4-Scout-17B"
)

# ---------------------------------------------------------------------------
# Locust benchmark parameters
# ---------------------------------------------------------------------------
USERS=20          # concurrent virtual users
SPAWN_RATE=10     # users spawned per second
RUN_TIME="15m"   # how long to run each model

# ---------------------------------------------------------------------------
# Ensure log directory exists
# ---------------------------------------------------------------------------
mkdir -p "$SCRIPT_DIR/logs"

echo "Job $SLURM_JOB_ID started on $SLURM_JOB_NODELIST"
echo "Will benchmark ${#MODELS[@]} model(s) sequentially: ${MODELS[*]}"
echo ""

for MODEL_NAME in "${MODELS[@]}"; do
    export MODEL_NAME

    echo "============================================="
    echo "SLURM job       : $SLURM_JOB_ID"
    echo "Node(s)         : $SLURM_JOB_NODELIST"
    echo "Model           : $MODEL_NAME"
    echo "Users / Rate    : $USERS / $SPAWN_RATE"
    echo "Run time        : $RUN_TIME"
    echo "============================================="

    locust \
        -f "$SCRIPT_DIR/locustfile.py" \
        --headless \
        --users "$USERS" \
        --spawn-rate "$SPAWN_RATE" \
        --run-time "$RUN_TIME" \
        --csv "$SCRIPT_DIR/logs/stats_${MODEL_NAME}_${SLURM_JOB_ID}" \
        --html "$SCRIPT_DIR/logs/report_${MODEL_NAME}_${SLURM_JOB_ID}.html"

    RC=$?
    echo "Benchmark finished for $MODEL_NAME (exit code: $RC)"
    echo ""
done

echo "All models done."

