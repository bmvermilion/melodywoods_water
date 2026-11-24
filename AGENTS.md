# Melody Woods Water Project Context

## Project Overview
This project consists of two repositories:
1. **pysensaphone**: A Python library for interacting with the Sensaphone Sentinel REST API.
2. **melodywoods_water**: A collection of AWS Lambda functions (managed via SAM) that use `pysensaphone` to automate water system operations. This repo also owns the `Makefile`, the vendored Lambda layer, and CI.

A `pysensaphone` checkout sitting next to this repo (default `../pysensaphone`) is optional and only used by `make sync-layer` to refresh the vendored layer.

## Roadmap & Identified Changes

### pysensaphone
- [x] **Refactor Auth**: Removed hardcoded username/password from `sensaphone_auth.py`.
- [x] **Standardize Logging**: Replaced `print()` calls with the standard `logging` library.
- [x] **Improve Packaging**: Created `pyproject.toml` and removed the legacy `setup.py`/`MANIFEST.in`.
- [x] **Security**: Cleaned up the library.
- [ ] **Error Handling**: Implement custom exceptions for API errors.

### melodywoods_water
- [x] **Lambda Layers**: Moved the library into a shared Layer to avoid bundling `.tar.gz` in every folder.
- [x] **Environment Variables**: Moved hardcoded strings (device names, thresholds) to Lambda environment configuration.
- [x] **Shared Utilities**: Centralized timezone handling and scheduling logic (partially done via Globals).

### Infrastructure Migration
- [ ] **Amazon WorkMail Deprecation**: Amazon WorkMail is being discontinued on March 31, 2027.
    - [ ] Plan migration for the `email` Lambda trigger (currently `workmail.us-east-1.amazonaws.com`).
    - [ ] Evaluate **Amazon SES** (Simple Email Service) as a replacement for receiving Sensaphone alerts and triggering Lambda.

## Deployment Details
- **Makefile**: repo root (`make build`, `make deploy`, `make test`)
- **Vendored layer**: `layers/pysensaphone/python`
- **SAM Stack**: `melody-woods-water`
- **Region**: `us-east-1`
- **Profile**: `melody`
- **S3 Bucket**: `aws-sam-cli-managed-default-samclisourcebucket-1tvhxb0ku4qj7`

## CI
- `melodywoods_water`: GitHub Actions runs `make lint test-unit`.
- `pysensaphone`: GitHub Actions installs the package and runs its unit tests.
