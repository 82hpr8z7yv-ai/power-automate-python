from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
import base64
import roadmunk_SN_transfer

app = FastAPI()

class DataSyncPayload(BaseModel):
    project_data_b64: str  # Base64 string of the project Excel file
    demand_data_b64: str   # Base64 string of the demand Excel file

@app.get("/")
def home():
    return {"status": "Online", "message": "Roadmunk Pipeline Interface Active."}

@app.post("/run-script")
def execute_transfer_pipeline(payload: DataSyncPayload, x_api_key: str = Header(None)):
    # Security pass check
    if x_api_key != "Roadmunk-Pipeline-Secret-Key-77":
        raise HTTPException(status_code=401, detail="Unauthorized Access")

    try:
        # Decode the file streams back from Power Automate binary text
        project_bytes = base64.b64decode(payload.project_data_b64)
        demand_bytes = base64.b64decode(payload.demand_data_b64)

        # Run the transformation script
        generated_csv_files = roadmunk_SN_transfer.run_transfer_pipeline(project_bytes, demand_bytes)
        
        return {
            "status": "Success",
            "files": generated_csv_files
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
