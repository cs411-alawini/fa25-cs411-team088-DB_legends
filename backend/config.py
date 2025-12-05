import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt")
    # DATABASE_URL must be a Postgres DSN e.g. postgresql://user:pass@localhost:5432/dbname
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
    # Ensure header-only tokens and avoid 'sub' strictness on some stacks
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_TYPE = "Bearer"
    JWT_IDENTITY_CLAIM = "identity"
