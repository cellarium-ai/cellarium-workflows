"""Git installation code for kubeflow components."""
import os

# re-install cellarium-ml if a git sha is provided
if git_sha != "":
    os.system('apt-get update')
    os.system('apt-get install -y git')
    cmd = f"pip install -U git+https://github.com/cellarium-ai/cellarium-ml.git@{git_sha}"
    print(cmd)
    os.system(cmd)
