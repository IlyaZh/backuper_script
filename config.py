from pydantic import BaseModel
from typing import List

class S3Config(BaseModel):
    endpoint: str
    bucket_name: str
    region: str
    enabled: bool

class DatabaseConfig(BaseModel):
    enabled: bool
    container_name: str
    db_user: str
    dump_filename: str

class TelegramConfig(BaseModel):
    enabled: bool = False
    chat_id: str

class BackupConfig(BaseModel):
    s3: S3Config
    database: DatabaseConfig
    telegram: TelegramConfig
    targets: List[str]

class Config(BaseModel):
    backup: BackupConfig