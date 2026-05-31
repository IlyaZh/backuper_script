import os
import sys
from datetime import datetime

import boto3
import yaml

from . import config, notifier
from .archiver import Archiver, File

CONFIG_PATH = "/app/config.yaml"
# Root folder of the project INSIDE the container (we mount it)
MOUNT_ROOT = "/host_data" 
TEMP_DIR = "/tmp/backup"

class Backuper:
    def __init__(self, config_path: str = CONFIG_PATH, temp_dir: str = TEMP_DIR, mount_root: str = MOUNT_ROOT):
        self._temp_dir: str = temp_dir
        self._mount_root: str = mount_root
        
        full_config = self._load_config(config_path)
        self._config: config.BackupConfig = full_config.backup

        if os.environ.get("S3_ENDPOINT"):
            self._config.s3.endpoint = os.environ.get("S3_ENDPOINT")
        if os.environ.get("S3_BUCKET_NAME"):
            self._config.s3.bucket_name = os.environ.get("S3_BUCKET_NAME")
        if os.environ.get("S3_REGION"):
            self._config.s3.region = os.environ.get("S3_REGION")
        
        if os.environ.get("TELEGRAM_CHAT_ID"):
            self._config.telegram.chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        
        if os.environ.get("DB_HOST"): 
             self._config.database.container_name = os.environ.get("DB_HOST")

        self._archiver = Archiver(temp_dir, mount_root)
        self._notifier: notifier.Notifier = notifier.TelegramNotifier(self._config.telegram)

    def Run(self):        
        try:
            self._cleanup()
            
            os.makedirs(self._temp_dir, exist_ok=True)
            
            dump_file_path = self._create_db_dump(self._config.database)
            archive_file = self._archiver.create_archive(self._config.targets, dump_file_path)
            archive_file = self._archiver.encrypt_archive(archive_file, self._config.encryption)
            self._upload_to_s3(archive_file, self._config.s3)

            self._notifier.send_success(archive_file.name, archive_file.size_mb)
        except Exception as e:
            print(f"CRITICAL ERROR: {e}")
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

    def _create_db_dump(self, db_config: config.DatabaseConfig) -> str | None:
        if not db_config.enabled:
            return None
        
        print("MySQL: Creating dump...")
        os.makedirs(self._temp_dir, exist_ok=True)
        dump_file = os.path.join(self._temp_dir, db_config.dump_filename)

        auth_config_path = os.path.join(self._temp_dir, "mysql_auth.cnf")
        
        # IMPORTANT: We connect to host 'mysql' (the service name in the docker network)
        # Password is taken from environment variable
        password = os.environ.get("DB_PASSWORD")
        
        with open(auth_config_path, "w") as f:
            f.write("[client]\n")
            f.write(f"host={db_config.container_name}\n")
            f.write(f"user={db_config.db_user}\n")
            f.write(f'password="{password}"\n')
        
        cmd = [
            "mysqldump",
            f"--defaults-extra-file={auth_config_path}",
            "--all-databases",
            "--skip-ssl",
            "--no-tablespaces"
        ]
        
        try:
            with open(dump_file, "w") as f:
                subprocess.run(cmd, stdout=f, check=True)
            print(f"MySQL: Dump created at {dump_file}")
            return dump_file
        except subprocess.CalledProcessError as e:
            print(f"MySQL Error: {e}")
            sys.exit(1)

        finally:
            if os.path.exists(auth_config_path):
                os.remove(auth_config_path)



    def _upload_to_s3(self, file: File, s3_config: config.S3Config):
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
            region_name=s3_config.region
        )
        
        try:
            s3.upload_file(file.path, s3_config.bucket_name, file.name)
            print("S3: Upload successful!")
        except Exception as e:
            print(f"S3 Error: {e}")
            sys.exit(1)



    def _cleanup(self):
        print("Cleanup: Removing temp files...")
        if os.path.exists(self._temp_dir):
            for f in os.listdir(self._temp_dir):
                try:
                    os.remove(os.path.join(self._temp_dir, f))
                except:
                    pass


