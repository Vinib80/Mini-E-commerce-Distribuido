import os
import uvicorn
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()
from contextlib import asynccontextmanager
from .database import init_db
from .routes import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

app.include_router(router)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5003))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
