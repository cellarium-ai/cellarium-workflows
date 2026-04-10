"""Git installation code for kubeflow components."""

import os

# re-install cellarium-ml if a git sha is provided
# if git_sha != "":  # noqa: F821
#     os.system("apt-get update")
#     os.system("apt-get install -y git")
#     cmd = f"pip install -U -q git+https://github.com/cellarium-ai/cellarium-ml.git@{git_sha}"  # noqa: F821
#     print(cmd)
#     os.system(cmd)

# faster
if git_sha != "":  # noqa: F821
    cmd = f"pip install -q https://github.com/cellarium-ai/cellarium-ml/archive/{git_sha}.tar.gz"  # noqa: F821
    print(cmd)
    os.system(cmd)
