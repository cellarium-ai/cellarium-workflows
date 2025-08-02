"""Git installation code for kubeflow components."""
import os

# re-install cellarium-ml if a git sha is provided
if git_sha != "":
    cmd = f"pip install -U git+https://github.com/cellarium-ai/cellarium-ml.git@{git_sha}"
    os.system(cmd)
