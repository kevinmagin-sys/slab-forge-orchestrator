# config/database.py
from sqlalchemy import create_engine

# Uses an in-memory database for testing and trials
DATABASE_URI = "sqlite:///:memory:"
engine = create_engine(DATABASE_URI)
