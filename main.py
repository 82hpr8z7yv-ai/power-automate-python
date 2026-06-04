from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
import roadmunk_SN_transfer

app = FastAPI()

class DataSyncPayload(BaseModel):
    project_data: str  # Plain text CSV contents of the project file
    demand_data: str   # Plain text CSV contents of the demand file

@app.get("/")
def home():
    return {"status": "Online", "message": "Personal OneDrive Data Sync Engine Active."}

@app.post("/run-script")
def execute_transfer_pipeline(payload: DataSyncPayload, x_api_key: str = Header(None)):
    # Standard security key check
    if x_api_key != "Personal-Secret-Vault-Key-99":
        raise HTTPException(status_code=401, detail="Unauthorized Access Denied")

    try:
        # Trigger the clean processing core
        generated_files = roadmunk_SN_transfer.run_transfer_pipeline(
            project_csv_string=payload.project_data,
            demand_csv_string=payload.demand_data
        )
        
        return {
            "status": "Success",
            "files": generated_files
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
