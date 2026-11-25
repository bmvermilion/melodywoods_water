# Melody Woods Water Automation

This serverless application automates the water extraction and distribution
system for Melody Woods Water Company using AWS Lambda and Amazon EventBridge.

## Core Functions

### 1. 88k Tank Control (`tank88k`)
Autonomous management of the main 88k storage tank.

- **Fill Schedule**: Turns the 5hp pump on at 9:00 PM Pacific. Two UTC cron
  entries cover PST and PDT.
- **Level Optimization**:
  - Shuts off above **23.3 ft** (safety high).
  - Shuts off above **22.8 ft** between noon and 9:00 PM (peak-hour savings).
  - Turns on below **22.8 ft** at 7:59 AM or earlier (morning boost).
- **Monitoring**: Hourly check at 5 minutes past the hour.
- **Thresholds**: Read from SSM (`shutoff_level_88k`, `shutoff_noon_level_88k`)
  with the values above as fallbacks.

### 2. Water Extraction (`supply`)
Scheduled control of the supply pumps.

- **Timers**: Runs every 15 minutes and compares Pacific time against
  `well3_on` / `well3_off` in SSM. Well #5 and the spring use the same timer
  pattern (`well5_*`, `spring_*`). The Well #5 schedule is disabled in the
  template; the spring is not scheduled, and email/power alerts do not
  trigger it.
- **Flexible Scheduling**: Adjust the SSM timers instead of redeploying.
- **Alerts**: Handles `email_alarm` and `intermittent_pumping` events from the
  email handler. Alerts currently act on Well #3 only.

### 3. Safety Alert Handler (`email`)
Reacts to Sensaphone alarm emails.

- **Chlorine Safety**: A low-chlorine alarm from the Treatment Plant shuts off
  Well #3. Well #3 chlorine alarms are not currently used and are ignored. A
  reading of `0` or below is treated as a wiring/power artifact and ignored.
- **Power Protection**: Power loss at the Treatment Plant or Well #3 shuts off
  Well #3. Power restoration resumes it, subject to the Well #3 daily window.
- **Trigger**: The function is invoked by an SES receipt rule or a WorkMail
  organization. Neither trigger is created by this template; see
  [External setup](#external-setup).

## Technical Architecture

- **Language**: Python 3.11
- **Shared Library**: Lambda layer vendored at `layers/pysensaphone/python`,
  synced from the `pysensaphone` repo with `make sync-layer`. The layer is pure
  Python; `make build` strips local `cpython-3.x` extensions so a 3.12 build
  never ships to the 3.11 runtime.
- **Infrastructure**: AWS SAM (Serverless Application Model)
- **Triggers**: EventBridge Schedules (cron) and inbound email (SES, with
  WorkMail retained until its 2027 shutdown).

## Development & Operations

Run these from the repo root:

- `make build`: Lint and build the app with the vendored layer.
- `make sync-layer`: Copy the library from `../pysensaphone` into the vendored
  layer. Review and commit the diff before deploying.
- `make deploy`: Lint, test, and deploy. Prompts for changeset confirmation.
- `make deploy DRY_RUN=true`: Deploy with Sensaphone writes disabled.
- `make test`: Unit tests plus integration smoke tests (integration self-skips
  without Docker/SAM).
- `make test-unit`: Fast unit tests only.
- `make logs-supply`: Tail live logs for the supply function.
- `make clean`: Remove build artifacts and `__pycache__` directories.

## Safety: Dry Run Mode

`DryRun` defaults to `false`, so a normal deploy makes live pump changes. Use
dry-run mode during maintenance to log intended changes without touching the
pumps:

```bash
make deploy DRY_RUN=true
```

## External setup

The template assumes these already exist in the AWS account:

- **KMS key** for `encrypted_controls.pem`. The `KmsKeyId` default is the
  Melody Woods key ID; the ARN is built at deploy time from the target
  account, region, and partition. Override the key ID for another account.
- **SSM parameters** read by the handlers:
  - Timers: `well3_on`, `well3_off`, `well5_on`, `well5_off`, `spring_on`,
    `spring_off` (spring is not currently scheduled)
  - Tank thresholds: `shutoff_level_88k`, `shutoff_noon_level_88k`
  - `/sensaphone/session` is a SecureString cache created by the functions.
- **Encrypted credential blob** at
  `layers/pysensaphone/python/pysensaphone/encrypted_controls.pem`. It is not
  committed; `make sync-layer` copies it from the library checkout. `make
  build` and `make deploy` fail if it is missing.
- **Email trigger**: an SES receipt rule (or WorkMail organization). The SES
  path expects the raw message saved to
  `melody-woods-water-emails-<account-id>` with the SES message ID as the
  object key.
- **Login name**: `SENSAPHONE_USERNAME` is set in `template.yaml`; update it
  there if the Sensaphone account address changes.
