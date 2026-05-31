import os
import subprocess
from typing import Optional

from .. import config
from .base import DatabaseDumper


class MySQLDumper(DatabaseDumper):
    def create_dump(self) -> Optional[str]:
        if not self._config.enabled:
            return None

        print("MySQL: Creating dump...")
        os.makedirs(self._temp_dir, exist_ok=True)

        dump_file = os.path.join(self._temp_dir, self._config.dump_filename)
        auth_config_path = os.path.join(self._temp_dir, "mysql_auth.cnf")

        password = os.environ.get("DB_PASSWORD")

        with open(auth_config_path, "w") as auth_file:
            auth_file.write("[client]\n")
            auth_file.write(f"host={self._config.container_name}\n")
            auth_file.write(f"user={self._config.db_user}\n")
            auth_file.write(f'password="{password}"\n')

        cmd = [
            "mysqldump",
            f"--defaults-extra-file={auth_config_path}",
            "--all-databases",
            "--skip-ssl",
            "--no-tablespaces",
        ]

        try:
            with open(dump_file, "w") as output_file:
                subprocess.run(cmd, stdout=output_file, check=True)
            print(f"MySQL: Dump created at {dump_file}")
            return dump_file
        except subprocess.CalledProcessError as e:
            print(f"MySQL Error: {e}")
            raise
        finally:
            if os.path.exists(auth_config_path):
                os.remove(auth_config_path)
