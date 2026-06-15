import os
import sys
from datetime import datetime

import boto3
import yaml

from . import config, notifier
from .archiver import Archiver, File
from .db import create_database_dumper

CONFIG_PATH = "/app/config.yaml"
# Root folder of the project INSIDE the container (we mount it)
MOUNT_ROOT = "/host_data"
TEMP_DIR = "/tmp/backup"


def should_run_today(weekdays: list[str] | None) -> bool:
    if not weekdays:
        return True

    # 0 = Monday, ..., 6 = Sunday
    days_map = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    today_name = days_map[datetime.now().weekday()]

    normalized_weekdays = [w.strip().lower()[:3] for w in weekdays]
    return today_name in normalized_weekdays


class Backuper:
    def __init__(
        self,
        config_path: str = CONFIG_PATH,
        temp_dir: str = TEMP_DIR,
        mount_root: str = MOUNT_ROOT,
    ):
        self._temp_dir: str = temp_dir
        self._mount_root: str = mount_root

        full_config = self._load_config(config_path)
        self._config: config.BackupConfig = full_config.backup

        s3_endpoint = os.environ.get("S3_ENDPOINT")
        if s3_endpoint:
            self._config.s3.endpoint = s3_endpoint

        s3_bucket_name = os.environ.get("S3_BUCKET_NAME")
        if s3_bucket_name:
            self._config.s3.bucket_name = s3_bucket_name

        s3_region = os.environ.get("S3_REGION")
        if s3_region:
            self._config.s3.region = s3_region

        telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if telegram_chat_id:
            self._config.telegram.chat_id = telegram_chat_id

        self._archiver = Archiver(temp_dir, mount_root)
        self._notifier: notifier.Notifier = (
            notifier.TelegramNotifier(self._config.telegram)
        )

    def Run(self) -> None:
        try:
            self._cleanup()

            today_databases = [
                db_config for db_config in self._config.databases
                if should_run_today(db_config.weekdays)
            ]
            today_targets = [
                target.path for target in self._config.targets
                if should_run_today(target.weekdays)
            ]

            if not today_databases and not today_targets:
                print("No targets or databases scheduled for backup today.")
                return

            os.makedirs(self._temp_dir, exist_ok=True)

            db_dumpers = [
                create_database_dumper(db_config, self._temp_dir)
                for db_config in today_databases
            ]
            dump_paths: list[str | None] = [
                dumper.create_dump() for dumper in db_dumpers
            ]
            dump_paths = [path for path in dump_paths if path is not None]
            archive_file = self._archiver.create_archive(
                today_targets,
                dump_paths,
            )
            if archive_file is None:
                print("Exiting backup process safely (nothing to backup).")
                return

            archive_file = self._archiver.encrypt_archive(
                archive_file,
                self._config.encryption,
            )
            self._upload_to_s3(
                archive_file,
                self._config.s3,
            )

            self._notifier.send_success(
                archive_file.name,
                archive_file.size_mb,
            )
        except Exception as e:
            error_text = f"CRITICAL ERROR: {e}"
            print(error_text)
            self._notifier.send_error(str(e))
            sys.exit(1)
        finally:
            self._cleanup()

    def _load_config(self, config_path: str) -> config.Config:
        if not os.path.exists(config_path):
            print(f"Error: Config not found at {config_path}")
            sys.exit(1)
        with open(config_path, "r") as f:
            return config.Config(**yaml.safe_load(f))

    def _upload_to_s3(self, file: File, s3_config: config.S3Config) -> None:
        print(f"S3: Uploading to bucket: {s3_config.bucket_name}")
        if not s3_config.enabled:
            print("S3: Upload skipped (disabled in config).")
            return

        session = boto3.session.Session()
        s3 = session.client(
            service_name='s3',
            endpoint_url=s3_config.endpoint,
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            region_name=s3_config.region,
        )

        try:
            s3.upload_file(file.path, s3_config.bucket_name, file.name)
            print("S3: Upload successful!")
        except Exception as e:
            print(f"S3 Error: {e}")
            sys.exit(1)

    def _cleanup(self) -> None:
        print("Cleanup: Removing temp files...")
        if os.path.exists(self._temp_dir):
            for entry_name in os.listdir(self._temp_dir):
                try:
                    os.remove(os.path.join(self._temp_dir, entry_name))
                except OSError:
                    pass
