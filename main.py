from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

# Define the structure of data coming from Power Automate
class FlowData(BaseModel):
    name: str
    email: str

@app.get("/")
def home():
    return {"status": "Online", "message": "Python automation backend is active."}

@app.post("/run-script")
def execute_automation(data: FlowData):
    try:
        # Run your core Python script logic right here
        result_message = f"Hello {data.name}! Your Python script executed flawlessly on Render. Verified email: {data.email}."
        
        return {
            "status": "Success",
            "message": result_message
        }
    except Exception as e:
        return {"status": "Error", "message": str(e)}