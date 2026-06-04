from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
import roadmunk_SN_transfer  # Imports your data transformation code seamlessly

app = FastAPI()

class SyncRequest(BaseModel):
    client_id: str
    client_secret: str
    tenant_id: str

@app.get("/")
def home():
    return {"status": "Online", "message": "UT System Data Sync Service Running Engine."}

@app.post("/run-script")
def execute_transfer_pipeline(payload: SyncRequest, x_api_key: str = Header(None)):
    # Simple explicit authorization pass verification check
    if x_api_key != "UT-System-Secret-Vault-Key-99":
        raise HTTPException(status_code=401, detail="Unauthorized API Request Access Denied")

    try:
        # Trigger the execution pipeline worker directly
        processed_files = roadmunk_SN_transfer.run_transfer_pipeline(
            client_id=payload.client_id,
            client_secret=payload.client_secret,
            tenant_id=payload.tenant_id
        )
        
        return {
            "status": "Success",
            "message": "Data transfer integration successfully pipeline ran cleanly.",
            "synchronized_outputs": processed_files
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
