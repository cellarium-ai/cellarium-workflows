#!/usr/bin/env bash
# Run a command while logging GPU utilization and memory to gpu_metrics.log.
# Usage: run_with_gpu_monitor.sh <command> [args...]
#
# Columns: timestamp, utilization.gpu (%), memory.used (MiB), memory.total (MiB)
#
# If nvidia-smi is not available (e.g. local CPU-only runs), the monitor is
# skipped silently and the command runs normally.

if command -v nvidia-smi &>/dev/null; then
    nvidia-smi \
        --query-gpu=timestamp,utilization.gpu,memory.used,memory.total \
        --format=csv,noheader,nounits \
        --loop=1 >> gpu_metrics.log 2>&1 &
    GPU_MONITOR_PID=$!
    trap "kill $GPU_MONITOR_PID 2>/dev/null || true" EXIT
fi

"$@"
