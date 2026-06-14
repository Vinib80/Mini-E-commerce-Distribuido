from fastapi import FastAPI
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
