.PHONY: install lint format FORCE

install: FORCE
	pip install -e .[dev]

lint: FORCE
	ruff check .
	ruff format --check .

format: FORCE
	ruff check --fix .
	ruff format .

test-examples: FORCE
	cellarium-workflow submit-batch-component \
		--tool onepass_mean_var_std \
		--subcommand fit \
		--config cellarium/workflows/example/onepass_train_config.yaml \
		--project dsp-cellarium \
		--location us-central1 \
		--machine-type n1-standard-4 \
		--accelerator-type nvidia-tesla-t4 \
		--accelerator-count 1 \
		--dry-run

FORCE:
