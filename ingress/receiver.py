import os
import sys
import cv2
import json
import uuid
from datetime import datetime
from typing import List, Any, Dict, Optional
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import DBAPIError as SQLAlchemyDBAPIError

# --- System Configuration ---
CONFIDENCE_GATE = 0.80
STAGING_DIR = os.environ.get("STAGING_DIR", "/var/forge/staging/")

# Ensure structural folder layout is validated on disk before payload extraction
try:
    os.makedirs(STAGING_DIR, exist_ok=True)
except PermissionError:
    STAGING_DIR = os.environ.get("STAGING_DIR", "/tmp/forge/staging/")
    os.makedirs(STAGING_DIR, exist_ok=True)

# --- Conformance Stubs & Infrastructure Layer ---
SessionLocal = sessionmaker()

class SearchQueryCriteria(BaseModel):
    MPN: str = ""
    UPC: str = ""
    Model: str = ""

def SaveToDisk(file_bytes: bytes, target_path: str) -> None:
    with open(target_path, "wb") as f:
        f.write(file_bytes)

def ExtractIdentifiers(extracted_text: str) -> SearchQueryCriteria:
    return SearchQueryCriteria(MPN="MOCK-MPN-123", UPC="MOCK-UPC-456", Model="MOCK-MOD")

def DispatchStorefrontBrokerJob(asset_id: uuid.UUID, payload: Dict[str, Any]) -> None:
    pass

def TriggerDisposalRoutingTask(asset_id: uuid.UUID) -> None:
    pass

class VisionEngineCore:
    @staticmethod
    def apply_high_pass_filter(matrix: Any) -> Any: 
        return matrix
    @staticmethod
    def extract_alphanumeric_strings(matrix: Any) -> str: 
        return "Extracted serial metrics text"
    @staticmethod
    def free_matrix_memory(matrix: Any) -> None: 
        del matrix


# ============================================================================
# STAGE 1: OPERATOR CAPTURE INTERFACE (Fired on Mobile Image Upload)
# ============================================================================
def HandleOperatorCapture(AssetID: uuid.UUID, UploadedFiles: List[bytes]) -> None:
    try:
        if not UploadedFiles:
            print(f"[WARNING] Discarded capture block: No image payloads provided for ID: {AssetID}")
            return
            
        DataPlateImage = UploadedFiles[0]
        GalleryImages = UploadedFiles[1:]
        
        SaveToDisk(DataPlateImage, f"{STAGING_DIR}{AssetID}_primary.png")
        
        for Index, Image in enumerate(GalleryImages):
            SaveToDisk(Image, f"{STAGING_DIR}{AssetID}_gallery_{Index}.png")
            
        with SessionLocal() as Session:
            with Session.begin():
                stmt = text("""
                    INSERT INTO asset_pipeline (id, status, created_at)
                    VALUES (:id, 'CAPTURED', CURRENT_TIMESTAMP)
                """)
                Session.execute(stmt, {"id": AssetID})
                
        print(f"[STATUS] Stage 1 Complete: Images staged on disk. Asset record initialized. ID: {AssetID}")
        
    except IOError as FileFault:
        print(f"[CRITICAL] Disk write failed during image capture stage. Fault: {FileFault}", file=sys.stderr)
        sys.exit(1)


# ============================================================================
# STAGE 2: BACKGROUND VISION & CATALOG MATCHING ENGINE (Fired via Worker)
# ============================================================================
def ProcessVisionAndMatching(AssetID: uuid.UUID) -> None:
    try:
        target_path = f"{STAGING_DIR}{AssetID}_primary.png"
        if not os.path.exists(target_path):
            raise FileNotFoundError(f"Staged primary asset file not found: {target_path}")

        RawMatrix = cv2.imread(target_path)
        ProcessedMatrix = VisionEngineCore.apply_high_pass_filter(RawMatrix)
        ExtractedText = VisionEngineCore.extract_alphanumeric_strings(ProcessedMatrix)
        
        VisionEngineCore.free_matrix_memory(RawMatrix)
        VisionEngineCore.free_matrix_memory(ProcessedMatrix)
        
        SearchQuery = ExtractIdentifiers(ExtractedText)
        
        with SessionLocal() as Session:
            with Session.begin():
                stmt_select = text("""
                    SELECT id, title, specs, base_price 
                    FROM master_catalog 
                    WHERE mpn = :mpn OR upc = :upc
                    LIMIT 1
                """)
                result = Session.execute(stmt_select, {"mpn": SearchQuery.MPN, "upc": SearchQuery.UPC})
                CatalogMatch = result.fetchone()
                
                if CatalogMatch is not None:
                    stmt_update_match = text("""
                        UPDATE asset_pipeline 
                        SET status = 'MATCHED', 
                            parsed_text = :parsed_text,
                            catalog_ref = :catalog_ref,
                            suggested_payload = :suggested_payload,
                            confidence_score = 1.0
                        WHERE id = :id
                    """)
                    Session.execute(stmt_update_match, {
                        "parsed_text": json.dumps(SearchQuery.model_dump()),
                        "catalog_ref": CatalogMatch.id,
                        "suggested_payload": json.dumps(CatalogMatch.specs),
                        "id": AssetID
                    })
                else:
                    stmt_update_fail = text("""
                        UPDATE asset_pipeline 
                        SET status = 'PARSED_NO_MATCH', 
                            parsed_text = :parsed_text,
                            confidence_score = 0.5
                        WHERE id = :id
                    """)
                    Session.execute(stmt_update_fail, {
                        "parsed_text": json.dumps(SearchQuery.model_dump()),
                        "id": AssetID
                    })
                
        print(f"[STATUS] Stage 2 Complete: Vision extraction finished. Catalog state updated. ID: {AssetID}")
        
    except Exception as ProcessFault:
        with SessionLocal() as Session:
            with Session.begin():
                stmt_crash = text("UPDATE asset_pipeline SET status = 'VISION_FAILED' WHERE id = :id")
                Session.execute(stmt_crash, {"id": AssetID})
        print(f"[CRITICAL] Vision matching step aborted unexpectedly. Fault: {ProcessFault}", file=sys.stderr)


# ============================================================================
# STAGE 3: LISTER REVIEW CONSOLE WORKSPACE (Keyboard-Only Event Listener)
# ============================================================================
def HandleListerAction(AssetID: uuid.UUID, UserActionKey: str, ModifiedPayload: Dict[str, Any]) -> None:
    with SessionLocal() as Session:
        with Session.begin():
            stmt_lock = text("SELECT status FROM asset_pipeline WHERE id = :id FOR UPDATE NOWAIT")
            try:
                result = Session.execute(stmt_lock, {"id": AssetID})
                CurrentState = result.fetchone()
            except SQLAlchemyDBAPIError as lock_err:
                print(f"[WARNING] Lock contention hit: Record {AssetID} is busy. Fault: {lock_err}", file=sys.stderr)
                return

            if CurrentState is not None and CurrentState.status == 'LISTED':
                print(f"[WARNING] Conflict prevented: This asset has already been processed and listed. ID: {AssetID}", file=sys.stderr)
                return

            if UserActionKey == "SPACEBAR":
                stmt_approve = text("""
                    UPDATE asset_pipeline 
                    SET status = 'LISTED', 
                        final_payload = :final_payload,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :id
                """)
                Session.execute(stmt_approve, {
                    "final_payload": json.dumps(ModifiedPayload),
                    "id": AssetID
                })
                
                DispatchStorefrontBrokerJob(AssetID, ModifiedPayload)
                print(f"[STATUS] Asset finalized and published via SPACEBAR confirmation. ID: {AssetID}")
                
            elif UserActionKey == "ESCAPE":
                stmt_reject = text("""
                    UPDATE asset_pipeline 
                    SET status = 'SCRAP_REJECTED', 
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :id
                """)
                Session.execute(stmt_reject, {"id": AssetID})
                
                TriggerDisposalRoutingTask(AssetID)
                print(f"[STATUS] Asset flagged as SCRAP via ESCAPE action. Record dropped from review queue. ID: {AssetID}")
