r"""D:\MyActivity\MyInfoBusiness\MyPythonApps\10 Typical_infrastructure\app\settings.py"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Typical infrastructure"
    sqlite_path: str = "app.db"


settings = Settings()

