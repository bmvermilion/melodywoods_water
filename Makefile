# Makefile for Melody Woods Water Automation

.PHONY: build deploy test test-unit test-integration lint sync-layer dry-run logs-supply logs-tank logs-email clean

# Default AWS Profile and Stack Name
PROFILE ?= melody
STACK_NAME ?= melody-woods-water

# Prefer a local virtualenv, fall back to tools on PATH.
VENV ?= $(firstword $(wildcard .venv ../.venv))
PYTHON ?= $(if $(VENV),$(VENV)/bin/python3,python3)
SAM ?= $(if $(VENV),$(VENV)/bin/sam,sam)

# Sibling checkout of the library used by sync-layer. When absent (CI or a
# standalone clone) the vendored layer is used as-is.
PYSENSAPHONE_DIR ?= ../pysensaphone

# Set SKIP_INTEGRATION=1 to run only fast unit tests.
SKIP_INTEGRATION ?= 0

# Fail fast on syntax errors before anything reaches AWS.
lint:
	@echo "Byte-compiling Lambda handlers and the vendored layer..."
	$(PYTHON) -m compileall -q supply 88k_tank email layers/pysensaphone/python/pysensaphone

# The deployed layer is a vendored copy; keep it in step with the library repo.
sync-layer:
	@if [ -d "$(PYSENSAPHONE_DIR)/pysensaphone" ]; then \
		echo "Syncing pysensaphone from $(PYSENSAPHONE_DIR)..."; \
		cp $(PYSENSAPHONE_DIR)/pysensaphone/*.py layers/pysensaphone/python/pysensaphone/; \
		if [ -f "$(PYSENSAPHONE_DIR)/pysensaphone/encrypted_controls.pem" ]; then \
			cp $(PYSENSAPHONE_DIR)/pysensaphone/encrypted_controls.pem layers/pysensaphone/python/pysensaphone/; \
		fi; \
	else \
		echo "No pysensaphone checkout at $(PYSENSAPHONE_DIR); using the vendored layer."; \
	fi

build: lint sync-layer
	@echo "Building with SAM (using container)..."
	$(SAM) build --use-container

deploy: lint sync-layer test
	@echo "Deploying to AWS using profile: $(PROFILE)..."
	$(SAM) deploy --profile $(PROFILE)

test: lint test-unit test-integration

test-unit:
	@echo "Running local unit tests..."
	$(PYTHON) tests/unit/test_supply_logic.py && \
	$(PYTHON) tests/unit/test_tank_logic.py && \
	$(PYTHON) tests/unit/test_auth_logic.py

# Needs docker + sam + AWS creds; self-skips when unavailable.
test-integration:
	@if [ "$(SKIP_INTEGRATION)" = "1" ]; then \
		echo "Skipping integration tests (SKIP_INTEGRATION=1)"; \
	else \
		echo "Running SAM integration tests..."; \
		$(PYTHON) tests/unit/test_integration.py || exit 1; \
	fi

dry-run:
	@echo "Invoking Supply Lambda in DRY RUN mode..."
	$(SAM) local invoke supply -e events/supply_well3_test_event.json --parameter-overrides "ParameterKey=DryRun,ParameterValue=true"

logs-supply:
	$(SAM) logs -n supply --stack-name $(STACK_NAME) --profile $(PROFILE) --tail

logs-tank:
	$(SAM) logs -n tank88k --stack-name $(STACK_NAME) --profile $(PROFILE) --tail

logs-email:
	$(SAM) logs -n email --stack-name $(STACK_NAME) --profile $(PROFILE) --tail

clean:
	rm -rf .aws-sam
	find . -type d -name "__pycache__" -exec rm -rf {} +
