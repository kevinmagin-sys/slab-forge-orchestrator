#!/usr/bin/env python3
"""Initialize the `master_catalog` table and seed a mock entry for testing."""
import os
import sys
import json
import uuid
from datetime import datetime
from sqlalchemy import create_engine, MetaData, Table, Column, String, Text

# Ensure repo root is importable
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from config.settings import get_settings


def get_engine():
    settings = get_settings()
    uri = settings.DATABASE_URI
    if uri == "sqlite:///:memory:":
        uri = "sqlite:///pipeline.db"
    return create_engine(uri)


def init_and_seed(engine):
    meta = MetaData()
    master_catalog = Table(
        "master_catalog",
        meta,
        Column("id", String, primary_key=True),
        Column("mpn", String, index=True),
        Column("upc", String, index=True),
        Column("title", String),
        Column("specs", Text),
    )
    meta.create_all(engine)

    # seed a mock row that matches our ExtractIdentifiers mock
    row_id = str(uuid.uuid4())
    mock = {
        "id": row_id,
        "mpn": "MOCK-MPN-123",
        "upc": "MOCK-UPC-456",
        "title": "Mock Industrial Part",
        "specs": json.dumps({"weight": "1kg", "material": "steel"}),
    }

    with engine.connect() as conn:
        # check if already seeded
        res = conn.execute(master_catalog.select().where(master_catalog.c.mpn == mock["mpn"]))
        if res.fetchone():
            print("Master catalog already seeded with mock entry.")
            return
        ins = master_catalog.insert().values(**mock)
        trans = conn.begin()
        try:
            conn.execute(ins)
            trans.commit()
        except Exception:
            trans.rollback()
            raise
    print(f"Seeded master_catalog with id={row_id}")


if __name__ == "__main__":
    engine = get_engine()
    init_and_seed(engine)
