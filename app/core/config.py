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
    
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    FRONTEND_SUCCESS_URL: str = "https://nutriomeals.com/payment-success"
    FRONTEND_CANCEL_URL: str = "https://nutriomeals.com/payment-cancel"
    
    REDIS_URL: str = "redis://localhost:6379/0"

settings = Settings()
