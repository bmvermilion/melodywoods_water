# Melody Woods Water Automation

This serverless application automates the water extraction and distribution system for Melody Woods Water Company using AWS Lambda and Amazon EventBridge.

## Core Functions

### 1. 88k Tank Control (`tank88k`)
Autonomous management of the main 88k storage tank.
- **Fill Schedule**: Automatically triggers a fill at 9:00 PM nightly.
- **Level Optimization**: 
  - Shuts off if the tank exceeds **23.3 ft** (Safety High).
  - Shuts off if the tank exceeds **22.8 ft** between 12:00 PM and 9:00 PM (Peak Hour Savings).
  - Ensures a morning boost before 7:00 AM if below **22.8 ft**.
- **Monitoring**: Performs an hourly check of all levels at 5 minutes past the hour.

### 2. Water Extraction (`supply`)
Scheduled control of Well #3 based on configurable timers.
- **Time Windows**: Runs every 15 minutes to check against `well3_on` and `well3_off` times stored in AWS SSM Parameter Store.
- **Flexible Scheduling**: Allows for 24/7 or intermittent pumping by simply enabling/disabling EventBridge rules or adjusting SSM parameters.

### 3. Safety Alert Handler (`email`)
Real-time reaction to Sensaphone emergency alerts.
- **Chlorine Safety**: If the Treatment Plant alerts for low chlorine, Well #3 is immediately shut off to prevent untreated water production.
- **Power Mismatch Protection**: If power is lost at either the Treatment Plant or Well #3, the well is shut off. It is automatically instructed to resume once power is restored (subject to its schedule).

## Technical Architecture
- **Language**: Python 3.11
- **Shared Library**: All functions utilize a shared **AWS Lambda Layer** containing the `pysensaphone` library.
- **Infrastructure**: Managed via AWS SAM (Serverless Application Model).
- **Triggers**: EventBridge Schedules (cron) and SES Inbound Email.

## Development & Operations
Use the root-level `Makefile` for standard tasks:
- `make build`: Prepare the application and layer.
- `make deploy`: Build, test, and deploy to AWS.
- `make test`: Run logic verification tests.
- `make logs-supply`: Tail live logs for the supply function.

## Safety: Dry Run Mode
`DryRun` defaults to `false`, so a normal deploy makes live pump changes. Use dry
run mode during maintenance to log intended changes without touching the pumps:

```bash
sam deploy --parameter-overrides DryRun=true
```
