from abc import ABC, abstractmethod
from typing import Optional

from .. import config


class DatabaseDumper(ABC):
    def __init__(self, config: config.DatabaseConfig, temp_dir: str):
        self._config = config
        self._temp_dir = temp_dir

    @abstractmethod
    def create_dump(self) -> Optional[str]:
        pass


class NullDatabaseDumper(DatabaseDumper):
    def create_dump(self) -> Optional[str]:
        return None


def create_database_dumper(db_config: config.DatabaseConfig, temp_dir: str) -> DatabaseDumper:
    if not db_config.enabled:
        return NullDatabaseDumper(db_config, temp_dir)

    db_type = getattr(db_config, "type", "mysql") or "mysql"
    db_type = db_type.lower()

    if db_type == "mysql":
        from .mysql import MySQLDumper

        return MySQLDumper(db_config, temp_dir)

    raise ValueError(f"Unsupported database type: {db_type}")
