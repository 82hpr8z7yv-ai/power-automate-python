from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import Any
import base64
import roadmunk_SN_transfer
import traceback

app = FastAPI()

class DataSyncPayload(BaseModel):
    project_data_b64: Any
    demand_data_b64: Any
    roadmunk_roadmap_id: str  
    roadmunk_api_token: str   
    user_email: str  # Added to accept email parameter Safely

@app.get("/")
def home():
    return {"status": "Online", "message": "Docker Browser Engine Active."}

@app.post("/run-script")
def execute_transfer_pipeline(payload: DataSyncPayload, x_api_key: str = Header(None)):
    if x_api_key != "Roadmunk-Pipeline-Secret-Key-77":
        raise HTTPException(status_code=401, detail="Unauthorized Access")

    try:
        print("--- 📥 Request Received at Container Gateway 📥 ---")
        
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

        project_bytes = extract_bytes(payload.project_data_b64)
        demand_bytes = extract_bytes(payload.demand_data_b64)
        
        print(f"✅ Handoff verified. Sizes -> Proj: {len(project_bytes)} bytes | Dmd: {len(demand_bytes)} bytes")

        roadmunk_SN_transfer.run_transfer_pipeline(
            project_excel_bytes=project_bytes,
            demand_excel_bytes=demand_bytes,
            roadmap_id=str(payload.roadmunk_roadmap_id).strip(),  
            api_token=payload.roadmunk_api_token,
            user_email=payload.user_email.strip()  # Passed down to processing script
        )
        
        return {
            "status": "Success",
            "message": "Data stream processed natively via interactive session."
        }
    except Exception as e:
        print("❌ CRITICAL EXCEPTION CAUGHT:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
