# backend-fastapi/app/main.py
import uvicorn
from fastapi import FastAPI
from app.routers import health, auth

app = FastAPI()

app.include_router(health.router)
app.include_router(auth.router)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)