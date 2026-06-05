from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
import base64
import roadmunk_SN_transfer

app = FastAPI()

class DataSyncPayload(BaseModel):
    project_data_b64: str
    demand_data_b64: str
    roadmunk_roadmap_id: str  # Added to track master map destination
    roadmunk_api_token: str   # Added to track authorization pass

@app.get("/")
def home():
    return {"status": "Online", "message": "Roadmunk Python Push Engine Active."}

@app.post("/run-script")
def execute_transfer_pipeline(payload: DataSyncPayload, x_api_key: str = Header(None)):
    if x_api_key != "Roadmunk-Pipeline-Secret-Key-77":
        raise HTTPException(status_code=401, detail="Unauthorized Access")

    try:
        project_bytes = base64.b64decode(payload.project_data_b64)
        demand_bytes = base64.b64decode(payload.demand_data_b64)

        # Pass data + Roadmunk details directly down into the pipeline engine
        generated_csv_files = roadmunk_SN_transfer.run_transfer_pipeline(
            project_excel_bytes=project_bytes,
            demand_excel_bytes=demand_bytes,
            roadmap_id=payload.roadmunk_roadmap_id,
            api_token=payload.roadmunk_api_token
        )
        
        return {
            "status": "Success/Pushed",
            "files": generated_csv_files
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
