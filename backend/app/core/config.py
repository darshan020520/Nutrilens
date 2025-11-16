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

    # MongoDB (for agent state & conversation history)
    mongodb_host: str = "mongodb"
    mongodb_port: int = 27017
    mongodb_user: str = "nutri"
    mongodb_password: str = "nutri"
    mongodb_db: str = "nutrilens_agent"

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
    from_email: str

    twilio_account_sid: str
    twilio_auth_token: str

    #JWT
    access_token_expire_minutes: int = 30

    base_dir: str

    # AWS S3 (for receipt images)
    s3_access_key: str
    s3_secret_key: str
    s3_region: str
    s3_bucket: str

    # Receipt Scanner Microservice
    receipt_scanner_url: str

    # OpenAI (for LLM normalizer)
    openai_api_key: str

    # Spoonacular (for recipe fetching)
    spoonacular_api_key: str

    # Receipt Processing Settings
    receipt_auto_add_threshold: float

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    @property
    def mongodb_url(self) -> str:
        return (
            f"mongodb://{self.mongodb_user}:{self.mongodb_password}"
            f"@{self.mongodb_host}:{self.mongodb_port}/{self.mongodb_db}?authSource=admin"
        )

    class Config:
        env_file = ".env"


settings = Settings()
