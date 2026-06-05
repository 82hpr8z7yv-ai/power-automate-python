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

@app.get("/")
def home():
    return {"status": "Online", "message": "Roadmunk Python Push Engine Active."}

@app.post("/run-script")
def execute_transfer_pipeline(payload: DataSyncPayload, x_api_key: str = Header(None)):
    if x_api_key != "Roadmunk-Pipeline-Secret-Key-77":
        raise HTTPException(status_code=401, detail="Unauthorized Access")

    try:
        print("--- Incoming Request Validated ---")
        print(f"Project Data Type: {type(payload.project_data_b64)}")
        
        # Safe log overview snippet
        sample = str(payload.project_data_b64)[:100]
        print(f"Project Data Sample: {sample}")
        
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
                except Exception as e:
                    print(f"⚠️ Base64 decode failed, falling back to string encode: {e}")
                    return payload_field.encode('utf-8')
            if isinstance(payload_field, (bytes, bytearray)):
                return payload_field
            return bytes(payload_field)

        print("Extracting project Excel bytes...")
        project_bytes = extract_bytes(payload.project_data_b64)
        
        print("Extracting demand Excel bytes...")
        demand_bytes = extract_bytes(payload.demand_data_b64)
        
        print(f"✅ Extracted project size: {len(project_bytes)} bytes | demand size: {len(demand_bytes)} bytes")

        # Pass data directly down to our data processing execution engine
        generated_csv_files = roadmunk_SN_transfer.run_transfer_pipeline(
            project_excel_bytes=project_bytes,
            demand_excel_bytes=demand_bytes,
            roadmap_id=payload.roadmunk_roadmap_id,
            api_token=payload.payload.roadmunk_api_token if hasattr(payload, 'payload') else payload.roadmunk_api_token
        )
        
        return {
            "status": "Success",
            "message": "Data stream processed cleanly."
        }
    except Exception as e:
        print("❌ CRITICAL EXCEPTION CAUGHT:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) # <-- Parenthesis explicitly closed here!
