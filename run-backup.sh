#!/bin/bash

# Backup script for cron execution
# Usage: Add to crontab: 0 2 * * * /path/to/backuper_script/run-backup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load environment variables from .env file
if [ -f .env ]; then
    set -a
    source .env
    set +a
else
    echo "Error: .env file not found!"
    exit 1
fi

# Run backup container
echo "Starting backup at $(date)"
docker compose run --rm backuper python main.py

echo "Backup completed at $(date)"
