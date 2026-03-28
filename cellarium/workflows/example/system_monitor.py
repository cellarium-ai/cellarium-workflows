"""
Lightweight system monitoring callback for key metrics.
"""

from typing import Any, Dict
import lightning.pytorch as pl
from lightning.pytorch.callbacks import Callback
from lightning.pytorch.utilities.types import STEP_OUTPUT

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    from lightning.pytorch.accelerators.cuda import get_nvidia_gpu_stats

    NVIDIA_SMI_AVAILABLE = True
except ImportError:
    NVIDIA_SMI_AVAILABLE = False


class SystemMonitor(Callback):
    """
    Lightweight callback that logs only the essential system metrics:
    - CPU utilization percentage
    - Memory utilization percentage
    - GPU utilization percentage (if available)
    - GPU memory usage (if available)
    """

    def __init__(self, log_every_n_steps: int = 50):
        """
        Args:
            log_every_n_steps: How frequently to log system stats (in training steps)
        """
        super().__init__()
        self.log_every_n_steps = log_every_n_steps
        self._step_count = 0

    def _get_system_stats(self, trainer: "pl.Trainer") -> Dict[str, float]:
        """Get essential system stats."""
        stats = {}

        # CPU and Memory stats
        if PSUTIL_AVAILABLE:
            stats["cpu_percent"] = psutil.cpu_percent()
            stats["memory_percent"] = psutil.virtual_memory().percent

        # GPU stats
        device = trainer.strategy.root_device
        if device.type == "cuda":
            try:
                if NVIDIA_SMI_AVAILABLE:
                    # Get comprehensive GPU stats from nvidia-smi
                    gpu_stats = get_nvidia_gpu_stats(device)
                    # Extract just the key metrics we care about
                    stats["gpu_utilization_percent"] = gpu_stats.get(
                        "utilization.gpu (%)", 0.0
                    )
                    stats["gpu_memory_used_mb"] = gpu_stats.get("memory.used (MB)", 0.0)
                    stats["gpu_memory_free_mb"] = gpu_stats.get("memory.free (MB)", 0.0)
                    stats["gpu_memory_utilization_percent"] = gpu_stats.get(
                        "utilization.memory (%)", 0.0
                    )
                else:
                    # Fallback to basic torch memory stats
                    import torch

                    if torch.cuda.is_available():
                        mem_allocated = (
                            torch.cuda.memory_allocated(device) / 1024**2
                        )  # MB
                        mem_reserved = (
                            torch.cuda.memory_reserved(device) / 1024**2
                        )  # MB
                        stats["gpu_memory_allocated_mb"] = mem_allocated
                        stats["gpu_memory_reserved_mb"] = mem_reserved
            except Exception:
                # Silently skip GPU stats if there's any error
                pass

        return stats

    def _log_stats(self, trainer: "pl.Trainer", stage: str) -> None:
        """Log system stats."""
        if not trainer._logger_connector.should_update_logs:
            return

        stats = self._get_system_stats(trainer)
        if not stats:
            return

        # Prefix metrics with stage
        prefixed_stats = {f"system_{stage}_{k}": v for k, v in stats.items()}

        # Log to all loggers
        for logger in trainer.loggers:
            logger.log_metrics(prefixed_stats, step=trainer.global_step)

    def on_train_batch_end(
        self,
        trainer: "pl.Trainer",
        pl_module: "pl.LightningModule",
        outputs: STEP_OUTPUT,
        batch: Any,
        batch_idx: int,
    ) -> None:
        """Log system stats every N training steps."""
        self._step_count += 1
        if self._step_count % self.log_every_n_steps == 0:
            self._log_stats(trainer, "train")

    def on_validation_epoch_start(
        self, trainer: "pl.Trainer", pl_module: "pl.LightningModule"
    ) -> None:
        """Log system stats at start of validation."""
        self._log_stats(trainer, "val")
