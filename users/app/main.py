# pyrefly: ignore [missing-import]
import os
# pyrefly: ignore [missing-import]
import uvicorn
# pyrefly: ignore [missing-import]
from fastapi import FastAPI
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

load_dotenv()
from contextlib import asynccontextmanager
from .database import init_db
from .routes import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializa o banco de dados no startup
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

# Inclui as rotas definidas no arquivo routes.py
app.include_router(router)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
