import os
import yaml
import tarfile
import boto3
import subprocess
from datetime import datetime
import sys
import config
from pydantic import BaseModel
import notifier

CONFIG_PATH = "/app/config.yaml"
# Root folder of the project INSIDE the container (we mount it)
MOUNT_ROOT = "/host_data" 
TEMP_DIR = "/tmp/backup"

class File(BaseModel):
    path: str
    name: str
    size_mb: float = 0.0

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

        self._notifier: notifier.Notifier = notifier.TelegramNotifier(self._config.telegram)

    def Run(self):        
        try:
            os.makedirs(self._temp_dir, exist_ok=True)
            
            dump_file_path = self._create_db_dump(self._config.database)
            archive_file = self._create_archive(self._config.targets, dump_file_path)
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

    def _create_archive(self, targets, dump_file) -> File:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        archive_name = f"backup_{timestamp}.tar.gz"
        archive_path = os.path.join(self._temp_dir, archive_name)
        
        print(f"Archiving: Creating {archive_name}...")
        
        with tarfile.open(archive_path, "w:gz") as tar:
            # 1. Add database dump
            if dump_file:
                tar.add(dump_file, arcname=os.path.basename(dump_file))
            
            # 2. Add project files
            for target in targets:
                full_path = os.path.join(self._mount_root, target.lstrip("./"))
                
                if os.path.exists(full_path):
                    print(f"  Adding: {target}")
                    tar.add(full_path, arcname=target)
                else:
                    print(f"  Warning: Path not found {full_path}")

        size_mb = os.path.getsize(archive_path) / (1024 * 1024)
                    
        return File(path=archive_path, name=archive_name, size_mb=size_mb)

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

def main():
    backuper = Backuper()
    backuper.Run()
    print("Done.")

if __name__ == "__main__":
    main()
