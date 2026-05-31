# backuper_script

A lightweight backup utility for creating compressed archives of application files and optional MySQL database dumps, then uploading them to S3-compatible storage and sending Telegram notifications.

## Table of Contents

- [Features](#features)
- [Repository structure](#repository-structure)
- [Requirements](#requirements)
- [Configuration](#configuration)
- [Environment variables](#environment-variables)
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

  database:
    enabled: true
    container_name: "mysql"
    db_user: "backuper"
    dump_filename: "db_dump.sql"

  targets:
    - "www"
    - "docker-compose.yml"

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

2. Update `docker-compose.yml` and set your project path in the volume mount:

```yaml
volumes:
  - /path/to/your/project:/host_data:ro  # Change this path
```

3. Run backup:

```bash
docker compose run --rm backuper python main.py
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

Build the image:

```bash
docker build -t backuper_script .
```

Run the container with mounted config and data:

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
  backuper_script python main.py
```

### Notes

- `config.yaml` is mounted at `/app/config.yaml` inside the container
- Backup source paths defined in `targets` are expected under `/host_data`
- The Docker image installs MySQL client tools so `mysqldump` works for database backups
- For encrypted archives, ensure `BACKUP_PASSWORD` is set in environment variables

## Customization

- Add or remove paths in `backup.targets` to control what files/directories are included
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
