# Melody Woods Water Project Context

## Project Overview
This project consists of two repositories:
1. **pysensaphone**: A Python library for interacting with the Sensaphone Sentinel REST API.
2. **melodywoods_water**: A collection of AWS Lambda functions (managed via SAM) that use `pysensaphone` to automate water system operations. This repo also owns the `Makefile`, the vendored Lambda layer, and CI.

A `pysensaphone` checkout sitting next to this repo (default `../pysensaphone`) is optional and only used by `make sync-layer` to refresh the vendored layer.

## Roadmap & Identified Changes

### pysensaphone
- [x] **Refactor Auth**: Removed the hardcoded password. The username defaults to the WorkMail address and can be overridden with `SENSAPHONE_USERNAME`.
- [x] **Standardize Logging**: Replaced `print()` calls with the standard `logging` library.
- [x] **Improve Packaging**: Created `pyproject.toml` and removed the legacy `setup.py`/`MANIFEST.in`.
- [x] **Security**: Cleaned up the library.
- [ ] **API Error Handling**: Raise `SensaphoneAPIError` / `SensaphoneAuthError` instead of returning `False` or `None` from API helpers.

### melodywoods_water
- [x] **Lambda Layers**: Moved the library into a shared Layer to avoid bundling `.tar.gz` in every folder.
- [~] **Configuration**: Timers and tank thresholds come from SSM; device and zone names still live in the handlers. `DRY_RUN` and `SENSAPHONE_USERNAME` are environment variables.
- [x] **Shared Utilities**: Centralized timezone handling and scheduling logic.
- [x] **Spring pump**: Timer control remains available (`spring_*`), but it is not scheduled and email/power alerts intentionally do not trigger it.

### Infrastructure Migration
- [ ] **Amazon WorkMail Deprecation**: Amazon WorkMail is being discontinued on March 31, 2027.
    - [x] Implement the SES inbound path alongside WorkMail.
    - [x] Grant the email role `workmailmessageflow:GetRawMessageContent` for the legacy path.
    - [ ] Complete the SES cutover and remove the WorkMail invoke permission.

### Alert Behavior Decisions
- **Well #3 chlorine**: not used. The handler intentionally ignores Well #3 chlorine alarms; `tests/unit/test_email_logic.py` asserts that no supply call is made.
- **Zero/negative chlorine**: ignored on purpose. A Treatment Plant reading of `0` or below is treated as a wiring fault or power-loss artifact, not a low-chlorine alarm.

## Deployment Details
- **Makefile**: repo root (`make build`, `make deploy`, `make test`)
- **Vendored layer**: `layers/pysensaphone/python`; update with `make sync-layer`
- **Dry run**: `make deploy DRY_RUN=true`
- **SAM Stack**: `melody-woods-water`
- **Region**: `us-east-1`
- **Profile**: `melody`
- **S3 Bucket**: `aws-sam-cli-managed-default-samclisourcebucket-1tvhxb0ku4qj7`
- **External**: KMS key, SSM parameters, SES receipt rule / WorkMail organization, and the encrypted credential blob. See the README.

## CI
- `melodywoods_water`: GitHub Actions runs `make lint test-unit`.
- `pysensaphone`: GitHub Actions installs the package and runs its unit tests.
