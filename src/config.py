from pydantic import BaseModel
from typing import List


class S3Config(BaseModel):
    endpoint: str
    bucket_name: str
    region: str
    enabled: bool


class DatabaseConfig(BaseModel):
    type: str = "mysql"
    enabled: bool
    container_name: str
    db_user: str
    dump_filename: str
    weekdays: List[str] | None = None


class TelegramConfig(BaseModel):
    enabled: bool = False
    chat_id: str


class EncryptionConfig(BaseModel):
    enabled: bool = False


class TargetConfig(BaseModel):
    path: str
    weekdays: List[str] | None = None


class BackupConfig(BaseModel):
    s3: S3Config
    databases: List[DatabaseConfig]
    telegram: TelegramConfig
    encryption: EncryptionConfig = EncryptionConfig()
    targets: List[TargetConfig]


class Config(BaseModel):
    backup: BackupConfig
