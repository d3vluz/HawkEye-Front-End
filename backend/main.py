"""
HawkEye Backend API - Ponto de entrada da aplicação.

Sistema de inspeção automatizada de qualidade industrial
usando visão computacional para análise de pins e hastes.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from contextlib import asynccontextmanager
from app.core.config import settings
from app.api import images_router, batches_router, metrics_router
from app.core.db import connect_db, disconnect_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await disconnect_db()

def create_app() -> FastAPI:
    """Cria e configura a aplicação FastAPI."""
    
    app = FastAPI(
        title=settings.APP_TITLE,
        version=settings.APP_VERSION,
        description="API para inspeção automatizada de qualidade industrial",
        lifespan=lifespan,
    )
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    import os
    os.makedirs("/data/images", exist_ok=True)
    os.makedirs("/data/images", exist_ok=True)
    app.mount("/data/images", StaticFiles(directory="/data/images"), name="images")
    app.mount("/api/files", StaticFiles(directory="/data/images"), name="api_files")
    app.include_router(images_router)
    app.include_router(batches_router)
    app.include_router(metrics_router)
    
    return app


# Criar instância da aplicação
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)