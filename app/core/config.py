from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Nutrio Meals API"
    APP_ENV: str = "development"

    DATABASE_URL: str

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    class Config:
        env_file = ".env"
        
    EMAIL_USERNAME: str
    EMAIL_PASSWORD: str
    EMAIL_FROM: str
    EMAIL_SERVER: str = "smtp.gmail.com"
    EMAIL_PORT: int = 587    
    EMAIL_TLS: bool = True
    EMAIL_SSL: bool = False

settings = Settings()
