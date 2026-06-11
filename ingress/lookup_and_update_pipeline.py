#!/usr/bin/env python3
"""Lookup master_catalog for a promoted asset and update asset_pipeline.

Usage: python3 ingress/lookup_and_update_pipeline.py --extraction static/uploads/extraction_promoted.json
"""
import json
import os
import sys
from datetime import datetime
from sqlalchemy import create_engine, text

# Ensure repo root on path
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from config.settings import get_settings
from ingress.receiver import ExtractIdentifiers


def get_engine():
    settings = get_settings()
    uri = settings.DATABASE_URI
    if uri == "sqlite:///:memory:":
        uri = "sqlite:///pipeline.db"
    return create_engine(uri)


def find_pipeline_id(engine):
    q = text("SELECT id FROM asset_pipeline ORDER BY created_at DESC LIMIT 1")
    with engine.connect() as conn:
        r = conn.execute(q).fetchone()
        return r[0] if r else None


def lookup_master_and_update(engine, pipeline_id, search_query):
    # search_query is object with MPN, UPC, Model
    q = text("SELECT id, title, specs FROM master_catalog WHERE mpn = :mpn OR upc = :upc LIMIT 1")
    with engine.connect() as conn:
        try:
            row = conn.execute(q, {"mpn": search_query.MPN, "upc": search_query.UPC}).fetchone()
        except Exception as e:
            # master_catalog table missing or other DB error — mark no match
            now = datetime.utcnow()
            update = text("""
                UPDATE asset_pipeline
                SET status = 'PARSED_NO_MATCH',
                    confidence_score = 0.5,
                    updated_at = :updated_at
                WHERE id = :id
            """)
            conn.execute(update, {"updated_at": now, "id": pipeline_id})
            print(f"Catalog lookup failed ({e}). Pipeline {pipeline_id} marked PARSED_NO_MATCH")
            return False
        now = datetime.utcnow()
        if row:
            catalog_id = row[0]
            update = text("""
                UPDATE asset_pipeline
                SET status = 'MATCHED',
                    catalog_ref = :catalog_ref,
                    suggested_payload = :suggested_payload,
                    confidence_score = 1.0,
                    updated_at = :updated_at
                WHERE id = :id
            """)
            conn.execute(update, {
                "catalog_ref": catalog_id,
                "suggested_payload": row[2] if row[2] is not None else None,
                "updated_at": now,
                "id": pipeline_id,
            })
            print(f"Pipeline {pipeline_id} updated with catalog_ref={catalog_id}")
            return True
        else:
            update = text("""
                UPDATE asset_pipeline
                SET status = 'PARSED_NO_MATCH',
                    confidence_score = 0.5,
                    updated_at = :updated_at
                WHERE id = :id
            """)
            conn.execute(update, {"updated_at": now, "id": pipeline_id})
            print(f"No catalog match found. Pipeline {pipeline_id} marked PARSED_NO_MATCH")
            return False


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--extraction", default="static/uploads/extraction_promoted.json")
    p.add_argument("--pipeline-id", default=None)
    args = p.parse_args()

    if not os.path.exists(args.extraction):
        raise SystemExit("extraction file not found")

    with open(args.extraction) as fh:
        payload = json.load(fh)

    # build a search query using receiver.ExtractIdentifiers (mock implementation)
    ocr_text = (payload.get("analysis", {}).get("ocr_text") or "")
    search_query = ExtractIdentifiers(ocr_text)

    engine = get_engine()

    pipeline_id = args.pipeline_id or find_pipeline_id(engine)
    if not pipeline_id:
        raise SystemExit("No pipeline record found to update")

    lookup_master_and_update(engine, pipeline_id, search_query)


if __name__ == "__main__":
    main()
