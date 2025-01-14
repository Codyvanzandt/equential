from app.config import get_settings
from fastapi import FastAPI, HTTPException
from .database import init_db
from .models import User

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    await init_db()

@app.get("/user/{access_id}")
async def get_user(access_id: str):
    user = await User.find_one({"access_id": access_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": f"Welcome {user.full_name}!"} 