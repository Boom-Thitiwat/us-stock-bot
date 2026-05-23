# Run Without Keeping Your Computer On

This project can run in GitHub Actions every 15 minutes. Your computer can be off because GitHub runs the job in the cloud.

## 1. Rotate exposed keys

The previous API keys were stored directly in `bot.py`. Revoke/rotate these keys in Alpaca and LINE before using cloud automation.

## 2. Push this repository to GitHub

Commit and push the project to a GitHub repository. The workflow file is already at `.github/workflows/stock-bot.yml`.

## 3. Add repository secrets

In GitHub, open:

`Settings -> Secrets and variables -> Actions -> New repository secret`

Add these secrets:

- `ALPACA_API_KEY`
- `ALPACA_SECRET_KEY`
- `LINE_CHANNEL_TOKEN`
- `LINE_USER_ID`

## 4. Enable Actions

Open the `Actions` tab in GitHub and enable workflows if GitHub asks.

The bot will run:

- Every 15 minutes on Monday-Friday
- Once immediately when you click `Run workflow`

The workflow sets `RUN_CONTINUOUSLY=false`, so each cloud run scans once and exits. Market-hours checks still happen inside `bot.py`.

## Optional cloud worker

If you want a true always-on process instead of scheduled runs, deploy the same repo to a VPS, Railway, Render worker, or Fly.io and set:

`RUN_CONTINUOUSLY=true`
