from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """MindBridge 集中配置

    配置优先从系统环境变量和项目根目录的 .env 文件读取；
    如果没有配置，则使用这里定义的默认值。
    """

    app_name: str = "MindBridge Learn"
    app_version: str = "0.1.0"
    environment: str = "development"

    server_host: str = "127.0.0.1"
    server_port: int = 8000

    model_config = SettingsConfigDict(
        env_file = ".env",
        env_file_encoding = "utf-8",
        extra = "ignore",
    )

@lru_cache
def get_settings() -> Settings:
    """返回全局复用的配置对象"""

    return Settings()
