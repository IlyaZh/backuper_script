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
- Uploads backups to an S3-compatible bucket (Cloudflare R2, MinIO, AWS S3, etc.)
- Sends success/failure notifications to Telegram
- Container-ready with a simple Dockerfile

## Repository structure

- `backup.py` - main backup orchestration script
- `config.py` - Pydantic config models for backup settings
- `notifier.py` - Telegram notification logic
- `config.example.yaml` - sample configuration file
- `Dockerfile` - container image definition
- `requirements.txt` - Python dependencies

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

## Running locally

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run the backup script:

```bash
python backup.py
```

Ensure `config.yaml` exists and environment variables are set before execution.

## Docker usage

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
  backuper_script python backup.py
```

### Notes

- `config.yaml` is mounted at `/app/config.yaml` inside the container.
- Backup source paths defined in `targets` are expected under `/host_data`.
- The Docker image installs MySQL client tools so `mysqldump` works for database backups.

## Customization

- Add or remove paths in `backup.targets` to control what files/directories are included.
- Disable database backup by setting `backup.database.enabled: false`.
- Disable notifications by setting `backup.telegram.enabled: false`.
- Disable S3 upload by setting `backup.s3.enabled: false`.

## Troubleshooting

- If the container cannot find files, verify the host volume mount and `targets` paths.
- If Telegram messages are not sent, check `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
- If MySQL dump fails, ensure `DB_PASSWORD` and `DB_HOST` are correct and the MySQL service is reachable.
