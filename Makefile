# Makefile for Melody Woods Water Automation

.PHONY: build deploy test test-unit test-integration lint check-layer sync-layer dry-run logs-supply logs-tank logs-email clean

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

# Set DRY_RUN=true to deploy with Sensaphone writes disabled.
DRY_RUN ?= false

# Fail fast on syntax errors before anything reaches AWS.
lint:
	@echo "Byte-compiling Lambda handlers and the vendored layer..."
	$(PYTHON) -m compileall -q supply 88k_tank email layers/pysensaphone/python/pysensaphone

# The layer needs the encrypted credential blob at runtime. It is not committed,
# so fail loudly instead of deploying a layer that cannot decrypt credentials.
check-layer:
	@test -s layers/pysensaphone/python/pysensaphone/encrypted_controls.pem || \
		(echo "ERROR: missing encrypted_controls.pem. Run 'make sync-layer' with a ../pysensaphone checkout."; exit 1)

# The deployed layer is a vendored copy; refresh it explicitly from the library
# repo, review the diff, and commit it.
sync-layer:
	@if [ -d "$(PYSENSAPHONE_DIR)/pysensaphone" ]; then \
		echo "Syncing pysensaphone from $(PYSENSAPHONE_DIR)..."; \
		cp $(PYSENSAPHONE_DIR)/pysensaphone/*.py layers/pysensaphone/python/pysensaphone/; \
		if [ -f "$(PYSENSAPHONE_DIR)/pysensaphone/encrypted_controls.pem" ]; then \
			cp $(PYSENSAPHONE_DIR)/pysensaphone/encrypted_controls.pem layers/pysensaphone/python/pysensaphone/; \
		fi; \
		echo "Review and commit the layer diff before deploying."; \
	else \
		echo "No pysensaphone checkout at $(PYSENSAPHONE_DIR); using the vendored layer."; \
	fi

build: lint check-layer
	@echo "Building with SAM (using container)..."
	$(SAM) build --use-container

deploy: check-layer test
	@echo "Deploying to AWS using profile: $(PROFILE)..."
	$(SAM) deploy --profile $(PROFILE) --parameter-overrides DryRun=$(DRY_RUN)

test: lint test-unit test-integration

test-unit:
	@echo "Running local unit tests..."
	$(PYTHON) tests/unit/test_supply_logic.py && \
	$(PYTHON) tests/unit/test_tank_logic.py && \
	$(PYTHON) tests/unit/test_email_logic.py && \
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
