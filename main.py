from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import Any
import base64
import roadmunk_SN_transfer
import traceback
import os
import subprocess

app = FastAPI()

class DataSyncPayload(BaseModel):
    project_data_b64: Any
    demand_data_b64: Any
    roadmunk_roadmap_id: str  
    roadmunk_api_token: str   

@app.get("/")
def home():
    return {"status": "Online", "message": "Headless Engine Active."}

@app.post("/run-script")
def execute_transfer_pipeline(payload: DataSyncPayload, x_api_key: str = Header(None)):
    if x_api_key != "Roadmunk-Pipeline-Secret-Key-77":
        raise HTTPException(status_code=401, detail="Unauthorized Access")

    try:
        print("--- 📥 Brand-New Request Received at Gateway 📥 ---")
        
        # Live Fallback: Force installation if Render cleared the cache folder
        print("🔍 Verifying virtual browser binaries status...")
        try:
            # Run a fast internal shell check to guarantee Chromium is available locally
            subprocess.run(["playwright", "install", "chromium"], check=True)
            print("✅ Virtual browser runtime verified and ready.")
        except Exception as install_err:
            print(f"⚠️ Dynamic runtime browser installation notice: {install_err}")

        target_mapping_destination = str(payload.roadmunk_roadmap_id).strip()
        print(f"📍 Target Route Target: {target_mapping_destination}")
        
        def extract_bytes(payload_field):
            if not payload_field:
                return b""
            if isinstance(payload_field, dict) and "$content" in payload_field:
                return base64.b64decode(payload_field["$content"])
            if isinstance(payload_field, str):
                if "base64," in payload_field:
                    payload_field = payload_field.split("base64,")[1]
                try:
                    clean_str = payload_field.strip().replace("\n", "").replace("\r", "")
                    padded_str = clean_str + "=" * ((4 - len(clean_str) % 4) % 4)
                    return base64.b64decode(padded_str)
                except Exception:
                    return payload_field.encode('utf-8')
            if isinstance(payload_field, (bytes, bytearray)):
                return payload_field
            return bytes(payload_field)

        print("🔄 Extracting project data matrix binary...")
        project_bytes = extract_bytes(payload.project_data_b64)
        
        print("🔄 Extracting demand data matrix binary...")
        demand_bytes = extract_bytes(payload.demand_data_b64)
        
        print(f"✅ Handoff verified. Sizes -> Proj: {len(project_bytes)} bytes | Dmd: {len(demand_bytes)} bytes")
        print("🤖 Launching internal browser orchestration thread...")

        generated_csv_files = roadmunk_SN_transfer.run_transfer_pipeline(
            project_excel_bytes=project_bytes,
            demand_excel_bytes=demand_bytes,
            roadmap_id=target_mapping_destination,  
            api_token=payload.roadmunk_api_token
        )
        
        return {
            "status": "Success",
            "message": "Headless workflow run completed seamlessly."
        }
    except Exception as e:
        print("❌ CRITICAL EXCEPTION CAUGHT INSIDE ENDPOINT ENVIRONMENT:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
