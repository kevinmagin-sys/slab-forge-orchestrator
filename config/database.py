# config/database.py
from sqlalchemy import create_engine
from .settings import get_settings

settings = get_settings()
engine = create_engine(settings.DATABASE_URI)
