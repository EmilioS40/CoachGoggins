import os


class Settings:
    app_name: str = "Sport API"
    database_url: str = os.environ["DATABASE_URL"]


settings = Settings()

