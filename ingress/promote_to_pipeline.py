#!/usr/bin/env python3
"""Promote an extraction result into the asset_pipeline DB table.

This script reads a JSON extraction result (default: static/uploads/extraction_promoted.json),
creates a local SQLite DB if necessary, ensures the `asset_pipeline` table exists, and
inserts a new record marking the asset as promoted.
"""
import json
import os
import sys
import uuid
from datetime import datetime
from sqlalchemy import create_engine, Table, Column, String, Float, Text, MetaData, DateTime

# Ensure workspace root is on sys.path for local imports
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from config.settings import get_settings


def get_db_uri():
    settings = get_settings()
    uri = settings.DATABASE_URI
    # If default in-memory, switch to a local file for persistence
    if uri == "sqlite:///:memory:":
        uri = "sqlite:///pipeline.db"
    return uri


def ensure_table(engine):
    meta = MetaData()
    asset_pipeline = Table(
        "asset_pipeline",
        meta,
        Column("id", String, primary_key=True),
        Column("status", String),
        Column("parsed_text", Text),
        Column("confidence_score", Float),
        Column("catalog_ref", String),
        Column("suggested_payload", Text),
        Column("created_at", DateTime),
        Column("updated_at", DateTime),
    )
    meta.create_all(engine)
    return asset_pipeline


def promote(extraction_json_path: str):
    if not os.path.exists(extraction_json_path):
        raise SystemExit(f"Extraction file not found: {extraction_json_path}")

    with open(extraction_json_path, "r") as fh:
        payload = json.load(fh)

    match = payload.get("match", {})
    analysis = payload.get("analysis", {})

    engine = create_engine(get_db_uri())
    table = ensure_table(engine)

    conn = engine.connect()
    new_id = str(uuid.uuid4())
    now = datetime.utcnow()

    ins = table.insert().values(
        id=new_id,
        status="PROMOTED",
        parsed_text=json.dumps({"analysis": analysis, "match": match}),
        confidence_score=float(match.get("score", 0.0) or 0.0),
        catalog_ref=None,
        suggested_payload=None,
        created_at=now,
        updated_at=now,
    )
    trans = conn.begin()
    try:
        conn.execute(ins)
        trans.commit()
    except Exception:
        trans.rollback()
        raise
    finally:
        conn.close()

    print(f"Promoted extraction into asset_pipeline with id={new_id}")
    return new_id


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--extraction", default="static/uploads/extraction_promoted.json")
    args = p.parse_args()
    promote(args.extraction)
