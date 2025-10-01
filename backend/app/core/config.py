from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    environment: str = "development"

    # Database
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str
    postgres_port: int

    # Redis
    redis_host: str
    redis_port: int
    redis_db: int = 0

    # MinIO
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str

    # Secret
    secret_key: str

    # FDC key
    fdc_api_key: str

    #Firebase
    firebase_credentials_path: str

    sendgrid_api_key: str

    twilio_account_sid: str
    twilio_auth_token: str

    #JWT
    access_token_expire_minutes: int = 30

    base_dir: str

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    class Config:
        env_file = ".env"


settings = Settings()
