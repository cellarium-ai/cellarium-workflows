"""
Custom GPU monitoring callback for comprehensive GPU stats including utilization.
"""

from typing import Any
import lightning.pytorch as pl
from lightning.pytorch.callbacks import Callback
from lightning.pytorch.accelerators.cuda import get_nvidia_gpu_stats
from lightning.pytorch.utilities.types import STEP_OUTPUT


class GPUUtilizationMonitor(Callback):
    """
    A callback that monitors comprehensive GPU stats including utilization, memory usage,
    temperature, and fan speed using nvidia-smi.

    This provides more detailed GPU information than the default DeviceStatsMonitor
    which only logs PyTorch CUDA memory stats.
    """

    def __init__(self, log_every_n_steps: int = 50):
        """
        Args:
            log_every_n_steps: How frequently to log GPU stats (in training steps)
        """
        super().__init__()
        self.log_every_n_steps = log_every_n_steps
        self._step_count = 0

    def _log_gpu_stats(self, trainer: "pl.Trainer", stage: str) -> None:
        """Log comprehensive GPU stats if nvidia-smi is available."""
        if not trainer._logger_connector.should_update_logs:
            return

        device = trainer.strategy.root_device
        if device.type != "cuda":
            return

        try:
            # Get comprehensive GPU stats from nvidia-smi
            gpu_stats = get_nvidia_gpu_stats(device)

            # Prefix the metrics with our callback name and stage
            prefixed_stats = {}
            for key, value in gpu_stats.items():
                prefixed_stats[f"GPUMonitor.{stage}.{key}"] = value

            # Log to all loggers
            for logger in trainer.loggers:
                logger.log_metrics(prefixed_stats, step=trainer.global_step)

        except FileNotFoundError:
            # nvidia-smi not available, fall back to basic torch stats
            if hasattr(trainer.accelerator, "get_device_stats"):
                basic_stats = trainer.accelerator.get_device_stats(device)
                prefixed_stats = {
                    f"GPUMonitor.{stage}.{k}": v for k, v in basic_stats.items()
                }
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
        """Log GPU stats every N training steps."""
        self._step_count += 1
        if self._step_count % self.log_every_n_steps == 0:
            self._log_gpu_stats(trainer, "train")

    def on_validation_batch_end(
        self,
        trainer: "pl.Trainer",
        pl_module: "pl.LightningModule",
        outputs: STEP_OUTPUT,
        batch: Any,
        batch_idx: int,
        dataloader_idx: int = 0,
    ) -> None:
        """Log GPU stats during validation."""
        if batch_idx == 0:  # Log only on first validation batch to avoid spam
            self._log_gpu_stats(trainer, "val")
