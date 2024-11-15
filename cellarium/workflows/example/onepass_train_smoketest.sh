#!/bin/bash

# copy the local yaml file to the bucket
gsutil cp onepass_train_smoketest_config.yaml gs://cellarium-human-primary-data/curriculum/human_all_primary_20241108/configs/onepass_train_smoketest_config.yaml

# submit a pipeline
python ../submit_single_component.py \
    --tool onepass_mean_var_std \
    --subcommand fit \
    --config gs://cellarium-human-primary-data/curriculum/human_all_primary_20241108/configs/onepass_train_smoketest_config.yaml \
    --accelerator-count 0
