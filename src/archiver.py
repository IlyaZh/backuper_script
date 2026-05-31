import os
import sys
import subprocess
from datetime import datetime

from pydantic import BaseModel

from . import config


class File(BaseModel):
    path: str
    name: str
    size_mb: float = 0.0


class Archiver:
    """Handles archive creation and encryption."""

    def __init__(self, temp_dir: str, mount_root: str):
        self._temp_dir = temp_dir
        self._mount_root = mount_root

    def create_archive(self, targets: list, dump_file: str = None) -> File:
        """Create tar.gz archive from targets and optional database dump."""
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

    def encrypt_archive(self, file: File, encryption_config: config.EncryptionConfig) -> File:
        """Encrypt archive using 7z AES-256 encryption."""
        if not encryption_config.enabled:
            return file

        password = os.environ.get("BACKUP_PASSWORD")
        if not password:
            print("Error: Encryption enabled but BACKUP_PASSWORD not set")
            sys.exit(1)

        print(f"Encryption: Encrypting {file.name} with 7z password protection...")

        encrypted_path = os.path.splitext(file.path)[0] + ".7z"

        try:
            cmd = [
                "7z", "a",
                "-t7z",
                f"-p{password}",
                "-mhe=on",
                encrypted_path,
                file.path,
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            print("Encryption: Archive encrypted successfully!")
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode().strip()
            print(f"Encryption Error: {stderr}")
            sys.exit(1)
        except FileNotFoundError:
            print("Error: 7z not found. Please install p7zip-full.")
            sys.exit(1)

        os.remove(file.path)

        size_mb = os.path.getsize(encrypted_path) / (1024 * 1024)
        return File(path=encrypted_path, name=os.path.basename(encrypted_path), size_mb=size_mb)
