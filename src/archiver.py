import io
import os
import subprocess
import sys
import tarfile
from datetime import datetime
from typing import Sequence

from pydantic import BaseModel

from . import config




class File(BaseModel):
    path: str
    name: str
    size_mb: float = 0.0


PathSequence = Sequence[str]


class Archiver:
    """Handles archive creation and encryption."""

    def __init__(self, temp_dir: str, mount_root: str):
        self._temp_dir = temp_dir
        self._mount_root = mount_root

    def create_archive(
        self,
        targets: PathSequence,
        dump_files: PathSequence | None = None,
    ) -> File | None:
        """Create a tar.gz archive from targets and database dumps."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        archive_name = f"backup_{timestamp}.tar.gz"
        archive_path = os.path.join(self._temp_dir, archive_name)

        print(f"Archiving: Creating {archive_name}...")

        added_count = 0
        with tarfile.open(archive_path, "w:gz") as tar:
            if dump_files:
                for dump_file in dump_files:
                    dump_name = os.path.basename(dump_file)
                    print(f"  Adding database dump: {dump_name}")
                    tar.add(dump_file, arcname=dump_name)
                    added_count += 1

            for target in targets:
                full_path = os.path.join(
                    self._mount_root,
                    target.lstrip("./"),
                )

                if os.path.exists(full_path):
                    print(f"  Adding: {target}")
                    tar.add(full_path, arcname=target)
                    added_count += 1
                else:
                    print(f"  Warning: Path not found {full_path}")

            if added_count == 0:
                print("No files or databases were found/added to the backup.")
                return None

            # Create backup_info.txt in-memory and add to tar
            info_lines = [
                f"Backup Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"Backup Weekday: {datetime.now().strftime('%A')}",
                "",
                "Targets included:",
            ]
            if targets:
                for target in targets:
                    info_lines.append(f"  - {target}")
            else:
                info_lines.append("  (none)")

            info_lines.append("")
            info_lines.append("Database dumps included:")
            if dump_files:
                for dump_file in dump_files:
                    info_lines.append(f"  - {os.path.basename(dump_file)}")
            else:
                info_lines.append("  (none)")

            info_content = "\n".join(info_lines)
            info_bytes = info_content.encode("utf-8")

            info_tar = tarfile.TarInfo(name="backup_info.txt")
            info_tar.size = len(info_bytes)
            tar.addfile(info_tar, io.BytesIO(info_bytes))

        size_bytes = os.path.getsize(archive_path)
        if size_bytes == 0:
            print("Created backup archive is empty (0 bytes).")
            return None

        size_mb = size_bytes / (1024 * 1024)

        return File(
            path=archive_path,
            name=archive_name,
            size_mb=size_mb,
        )

    def encrypt_archive(
        self,
        file: File,
        encryption_config: config.EncryptionConfig,
    ) -> File:
        """Encrypt archive using 7z AES-256 encryption."""
        if not encryption_config.enabled:
            return file

        password = os.environ.get("BACKUP_PASSWORD")
        if not password:
            print("Error: Encryption enabled but BACKUP_PASSWORD not set")
            sys.exit(1)

        encrypt_message = (
            f"Encryption: Encrypting {file.name} "
            "with 7z password protection..."
        )
        print(encrypt_message)

        encrypted_path = os.path.splitext(file.path)[0] + ".7z"

        try:
            cmd = [
                "7z",
                "a",
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
        return File(
            path=encrypted_path,
            name=os.path.basename(encrypted_path),
            size_mb=size_mb,
        )
