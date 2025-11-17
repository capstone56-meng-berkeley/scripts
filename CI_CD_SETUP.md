# CI/CD Setup Guide

This guide explains how to set up automated image augmentation in CI/CD environments.

## Overview

The augmentation script supports secure credential management for automated environments through environment variables. Credentials are:
- Created from environment variables at runtime
- Stored in temporary files
- Automatically cleaned up on completion or error

## Security Features

✅ **No credentials in code repository**
✅ **Automatic cleanup of temporary files**
✅ **Support for environment variable secrets**
✅ **Trap handlers for cleanup on errors/interrupts**

## Environment Variables

### Required for Google Drive Mode

| Variable | Description | Example |
|----------|-------------|---------|
| `CREDENTIALS_JSON` | Full Google OAuth credentials JSON | See `.env.example` |
| `INPUT_FOLDER_ID` | Google Drive folder ID for input images | `1VScZDE8q1xdHIq1k...` |
| `OUTPUT_FOLDER_ID` | Google Drive folder ID for output | `1aMGETWlwL8sWvDv_...` |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `TOKEN_JSON` | Pre-authenticated token (skip OAuth flow) | None |
| `MAX_FILES_TO_PROCESS` | Limit number of files | Process all |
| `SHEET_ID` | Google Sheets ID for tracking | None |
| `SHEET_WORKSHEET` | Worksheet name | `database` |
| `SHEET_ID_COLUMN` | Column with file IDs | `C` |
| `SHEET_RESULT_COLUMN` | Column for results | `F` |

## Local Development Setup

### 1. Create `.env` file

```bash
cd scripts
cp .env.example .env
```

### 2. Edit `.env` with your credentials

Get your credentials from Google Cloud Console:
1. Go to https://console.cloud.google.com/
2. Create/select your project
3. Enable Google Drive API and Google Sheets API
4. Create OAuth 2.0 credentials (Desktop app)
5. Download `credentials.json`
6. Copy the entire JSON content to `CREDENTIALS_JSON` in `.env`

### 3. Load environment variables

```bash
source .env
```

### 4. Run the script

```bash
./run_augmenter.sh --n-samples 3
```

## GitHub Actions Setup

### 1. Add Secrets to Repository

Go to: Repository → Settings → Secrets and variables → Actions

Add these secrets:

- **`CREDENTIALS_JSON`**: Full contents of your `credentials.json` file
- **`TOKEN_JSON`** (Optional): Pre-authenticated token
- **`INPUT_FOLDER_ID`**: Your input folder ID
- **`OUTPUT_FOLDER_ID`**: Your output folder ID
- **`SHEET_ID`** (Optional): Google Sheets ID

### 2. Create Workflow File

```bash
# Copy the example workflow
cp .github/workflows/augmentation.yml.example .github/workflows/augmentation.yml

# Commit and push
git add .github/workflows/augmentation.yml
git commit -m "Add augmentation workflow"
git push
```

### 3. Run Workflow

1. Go to: Repository → Actions
2. Select "Image Augmentation" workflow
3. Click "Run workflow"
4. Enter parameters (n_samples, max_files)
5. Click "Run workflow"

### 4. View Results

- Check workflow logs for progress
- Download artifacts for warnings/state files
- Check Google Drive for augmented images
- Check Google Sheets for tracking updates

## Getting Pre-Authenticated Token (Optional)

To avoid interactive OAuth in CI/CD:

### Method 1: Run Locally First

```bash
# Run once locally to authenticate
./run_augmenter.sh --n-samples 1

# Copy the generated token
cat token.json
```

Add the token content as `TOKEN_JSON` secret in GitHub.

### Method 2: Service Account (Recommended for Production)

1. Create a Service Account in Google Cloud Console
2. Download the service account JSON key
3. Share your Google Drive folders with the service account email
4. Use the service account key as `CREDENTIALS_JSON`

## Security Best Practices

### ✅ DO:
- Use repository secrets for credentials
- Enable branch protection on main/master
- Rotate credentials regularly
- Use service accounts for production
- Review workflow logs for sensitive data leaks

### ❌ DON'T:
- Commit credentials to repository
- Share credentials in plain text
- Use personal OAuth tokens in shared repos
- Log credential values
- Disable cleanup mechanisms

## Troubleshooting

### "Credentials file not found"
- Ensure `CREDENTIALS_JSON` environment variable is set
- Check that the JSON is valid (use a JSON validator)

### "Token expired" or authentication errors
- Generate a new token by running locally
- Update `TOKEN_JSON` secret
- Or remove `TOKEN_JSON` and use interactive auth

### Cleanup not working
- Check trap handlers are enabled
- Ensure script has execute permissions
- Look for `cleanup()` function errors in logs

### Files not uploading to Drive
- Verify folder IDs are correct
- Check service account has write access
- Ensure Drive API is enabled

## Advanced Configuration

### Custom Workflow Triggers

```yaml
on:
  # Run on schedule (daily at 2 AM UTC)
  schedule:
    - cron: '0 2 * * *'

  # Run on push to main
  push:
    branches: [ main ]

  # Manual trigger
  workflow_dispatch:
```

### Matrix Builds (Multiple Configurations)

```yaml
strategy:
  matrix:
    n_samples: [2, 3, 5]

steps:
  - name: Run augmentation
    run: ./run_augmenter.sh --n-samples ${{ matrix.n_samples }}
```

## Support

For issues or questions:
- Check the main [README.md](README_MODULAR.md) for general usage
- Review [ARCHITECTURE.md](ARCHITECTURE.md) for system design
- Open an issue on GitHub
