"""PyTorch environment setup code for kubeflow components."""

import psutil
import torch
import os

# set env variables to allow pytorch to use all CPUs
num_physical_cores = psutil.cpu_count(logical=False)
os.environ["OMP_NUM_THREADS"] = str(num_physical_cores)
os.environ["MKL_NUM_THREADS"] = str(num_physical_cores)
os.environ["OPENBLAS_NUM_THREADS"] = str(num_physical_cores)  # Only if using OpenBLAS
os.environ["NUMEXPR_NUM_THREADS"] = str(num_physical_cores)  # Not critical for PyTorch

# handle multi-node training
if os.environ.get("RANK") is not None:
    os.environ["NODE_RANK"] = os.environ.get("RANK")

# set number of threads for torch
torch.set_num_threads(num_physical_cores)
