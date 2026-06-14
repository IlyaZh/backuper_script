# backuper_script

A lightweight backup utility for creating compressed archives of application files and optional MySQL database dumps, then uploading them to S3-compatible storage and sending Telegram notifications.

## Table of Contents

- [Features](#features)
- [Repository structure](#repository-structure)
- [Requirements](#requirements)
- [Configuration](#configuration)
- [Environment variables](#environment-variables)
- [Encryption](#encryption)
- [Running locally](#running-locally)
- [Docker usage](#docker-usage)
- [Customization](#customization)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Features

- Creates a `.tar.gz` archive containing configured target files/directories
- Generates a MySQL dump when database backup is enabled
- **Encrypts archives with AES-256** inside a `.7z` container when enabled
- Uploads backups to an S3-compatible bucket (Cloudflare R2, MinIO, AWS S3, etc.)
- Sends success/failure notifications to Telegram
- Docker Compose ready for easy cron scheduling

## Repository structure

```
.
├── main.py                 # Entry point for the backup script
├── config.example.yaml     # Sample configuration file
├── Dockerfile              # Container image definition
├── docker-compose.yml      # Docker Compose configuration
├── run-backup.sh           # Cron-friendly backup runner script
├── requirements.txt        # Python dependencies
└── src/
    ├── backup.py          # Main backup orchestration logic
    ├── archiver.py        # Archive creation and encryption
    ├── config.py          # Pydantic config models for backup settings
    └── notifier.py        # Telegram notification logic
```

## Requirements

- Python >= 3.11
- `mysqldump` available in the environment (installed in the container by the Dockerfile)
- Access to an S3-compatible endpoint and bucket
- Telegram bot token and chat ID if notifications are enabled

## Configuration

Copy `config.example.yaml` to `config.yaml` and customize it:

```yaml
backup:
  s3:
    endpoint: ""
    bucket_name: ""
    region: "auto"
    enabled: true

  databases:
    - type: "mysql"
      enabled: true
      container_name: "mysql"
      db_user: "backuper"
      dump_filename: "db_dump.sql"
      weekdays: ["mon", "wed", "fri"] # Optional: days of week to backup. If omitted, backups up every day.

  targets:
    - path: "www"
      weekdays: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] # Optional: days of week to backup.
    - path: "docker-compose.yml" # Runs every day if weekdays omitted

  telegram:
    enabled: true
    chat_id: ""

  encryption:
    enabled: false  # Set to true to enable archive encryption with 7z AES-256
```

### Important

- `endpoint`, `bucket_name`, `chat_id`, and other secrets are best provided through environment variables.
- The script uses `/app/config.yaml` as the config file path inside the container.
- The `backup.targets` paths are resolved relative to `/host_data` when running inside Docker.

## Environment variables

The script reads several environment values to support flexible deployment:

- `S3_ENDPOINT` - S3-compatible endpoint URL
- `S3_BUCKET_NAME` - bucket name for backup upload
- `S3_REGION` - AWS region or compatible region string
- `AWS_ACCESS_KEY_ID` - access key for S3 upload
- `AWS_SECRET_ACCESS_KEY` - secret key for S3 upload
- `TELEGRAM_BOT_TOKEN` - token for Telegram bot notifications
- `TELEGRAM_CHAT_ID` - chat ID to send Telegram messages
- `DB_PASSWORD` - MySQL user password for `mysqldump`
- `DB_HOST` - optional override for the MySQL container hostname
- `BACKUP_PASSWORD` - password for archive encryption (if encryption is enabled, the final archive becomes `.7z`)

## Encryption

The backup script supports optional AES-256 encryption using 7-Zip. When enabled, the unencrypted `.tar.gz` archive is placed inside a password-protected `.7z` container, and the original `.tar.gz` file is deleted.

### How to Enable Encryption

1. **Update Configuration:**
   In your `config.yaml` file, set `enabled` to `true` in the `encryption` block:
   ```yaml
   backup:
     ...
     encryption:
       enabled: true
   ```

2. **Set the Password:**
   Define the `BACKUP_PASSWORD` environment variable. 
   - If running with **Docker Compose**, add it to your `.env` file:
     ```env
     BACKUP_PASSWORD=your-secure-password
     ```
   - If running **manually**, pass it via the `-e` flag to `docker run`:
     ```bash
     -e BACKUP_PASSWORD="your-secure-password"
     ```

### Encryption Details

- **Algorithm:** AES-256.
- **Header Encryption:** Enabled (`-mhe=on`). This means that file names and metadata inside the `.7z` archive are encrypted as well. You cannot view the file names inside the archive without entering the password.
- **Output Extension:** The resulting file will have a `.tar.7z` extension (e.g., `backup_2026-06-14_12-00-00.tar.7z`).

### How to Decrypt and Extract Backups

Since the archive uses double wrapping (the `.tar.gz` is wrapped in `.7z`), you need to decrypt it and then extract the files.

#### Step 1: Decrypt the `.7z` archive
Run `7z` to extract the `.tar.gz` file from the encrypted `.7z` container:
```bash
7z x backup_2026-06-14_12-00-00.tar.7z
```
*You will be prompted to enter the password.*

This will extract the unencrypted compressed file: `backup_2026-06-14_12-00-00.tar.gz`.

#### Step 2: Extract the `.tar.gz` file
Run the standard `tar` command to extract the contents:
```bash
tar -xzf backup_2026-06-14_12-00-00.tar.gz
```

## Running locally

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run the backup script:

```bash
python main.py
```

Ensure `config.yaml` exists and environment variables are set before execution.

## Docker usage

### Option 1: Docker Compose (Recommended for Cron)

1. Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
# Edit .env with your S3, Telegram, and database credentials
```

2. Update `docker-compose.yml` to set your project path in the volume mount. 

   Optionally, instead of building the image locally, you can use the prebuilt image published to GitHub Container Registry (GHCR):
   ```yaml
   services:
     backuper:
       # Comment build and uncomment image:
       # image: ghcr.io/<your-github-username-or-org>/backuper_script:latest
   ```

3. Run backup:

   - **If building locally:**
     ```bash
     docker compose run --rm backuper python main.py
     ```
   - **If using the prebuilt GHCR image:**
     ```bash
     docker compose pull backuper
     docker compose run --rm backuper
     ```

4. **Schedule with Cron:**

Make the script executable and add to crontab:

```bash
chmod +x run-backup.sh
# Edit crontab
crontab -e
# Add line: 0 2 * * * /path/to/backuper_script/run-backup.sh
```

The script will run daily at 2:00 AM and load environment variables from `.env`.

### Option 2: Manual Docker Run

You can run the backup script using the prebuilt image from GHCR directly:

```bash
docker run --rm \
  -v /path/to/config.yaml:/app/config.yaml:ro \
  -v /path/to/project:/host_data:ro \
  -e AWS_ACCESS_KEY_ID="..." \
  -e AWS_SECRET_ACCESS_KEY="..." \
  -e S3_ENDPOINT="https://..." \
  -e S3_BUCKET_NAME="..." \
  -e S3_REGION="..." \
  -e TELEGRAM_BOT_TOKEN="..." \
  -e TELEGRAM_CHAT_ID="..." \
  -e DB_PASSWORD="..." \
  -e BACKUP_PASSWORD="..." \
  ghcr.io/<your-github-username-or-org>/backuper_script:latest
```

### Notes

- `config.yaml` is mounted at `/app/config.yaml` inside the container
- Backup source paths defined in `targets` are expected under `/host_data`
- The Docker image installs MySQL client tools so `mysqldump` works for database backups
- For encrypted archives, ensure `BACKUP_PASSWORD` is set in environment variables

## Customization

- Add, modify or remove paths in `backup.targets` to control what files/directories are included. Note that each target is structured: `{ path: "...", weekdays: [...] }`.
- **Scheduled Backups (Weekdays Mask)**: Limit backups of specific databases and target directories to certain days of the week by adding the `weekdays` parameter (e.g., `["mon", "wed", "fri"]`). If the `weekdays` parameter is omitted, it defaults to backing up every day.
- Disable database backup by setting `backup.database.enabled: false`
- Disable notifications by setting `backup.telegram.enabled: false`
- Disable S3 upload by setting `backup.s3.enabled: false`
- **Enable encryption** by setting `backup.encryption.enabled: true` and providing `BACKUP_PASSWORD` env var
  - Encrypted archives are saved as `.7z`
  - Uses native 7z AES-256 encryption

## Troubleshooting

- If the container cannot find files, verify the host volume mount and `targets` paths.
- If Telegram messages are not sent, check `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
- If MySQL dump fails, ensure `DB_PASSWORD` and `DB_HOST` are correct and the MySQL service is reachable.
