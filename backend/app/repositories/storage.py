"""
Repository para operações de storage no disco local.
Substitui o Supabase Storage.
"""
import os
import hashlib
import cv2
import numpy as np
import shutil
from fastapi import HTTPException

from app.core.config import settings

# Diretório base para storage local montado via Docker
STORAGE_DIR = "/data/images"


def _ensure_dir(path: str):
    """Garante que o diretório exista."""
    os.makedirs(os.path.dirname(path), exist_ok=True)


def calculate_sha256(file_content: bytes) -> str:
    """Calcula o hash SHA256 do conteúdo do arquivo."""
    return hashlib.sha256(file_content).hexdigest()


def get_public_url(storage_path: str, bucket: str = None) -> str:
    """
    Obtém a URL da API para acesso a uma imagem local.
    Assumimos que as imagens serão expostas como arquivos estáticos.
    """
    if not storage_path:
        return ""
    # Retorna uma rota relativa da API (precisa estar configurada no FastAPI)
    return f"/api/files/{storage_path}"


def download_image(storage_path: str, bucket: str = None) -> np.ndarray:
    """
    Carrega uma imagem do disco local.
    """
    full_path = os.path.join(STORAGE_DIR, storage_path)
    try:
        img = cv2.imread(full_path, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Não foi possível decodificar ou encontrar: {full_path}")
        return img
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Erro ao carregar imagem: {str(e)}"
        )


def upload_image(
    file_content: bytes,
    storage_path: str,
    content_type: str = "image/png",
    bucket: str = None
) -> str:
    """
    Salva uma imagem no disco local.
    """
    try:
        full_path = os.path.join(STORAGE_DIR, storage_path)
        _ensure_dir(full_path)
        with open(full_path, "wb") as f:
            f.write(file_content)
        return storage_path
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Erro no upload local: {str(e)}"
        )


def upload_processed_image(
    image: np.ndarray,
    timestamp: str,
    sha256: str,
    image_type: str,
    bucket: str = None
) -> str:
    """
    Salva uma imagem processada no disco local.
    """
    try:
        storage_path = f"{timestamp}/{sha256}/processed_{image_type}.png"
        full_path = os.path.join(STORAGE_DIR, storage_path)
        _ensure_dir(full_path)
        
        success = cv2.imwrite(full_path, image)
        if not success:
            raise ValueError("Não foi possivel salvar a imagem pelo OpenCV.")
        
        return storage_path
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Erro ao salvar imagem processada: {str(e)}"
        )


def move_file_between_buckets(
    source_path: str,
    dest_path: str,
    source_bucket: str = None,
    dest_bucket: str = None
) -> bool:
    """
    Move um arquivo localmente (simula mover do temp pro permanent se necessário).
    """
    # Como não há buckets, podemos apenas renomear ou copiar
    full_source = os.path.join(STORAGE_DIR, source_path)
    full_dest = os.path.join(STORAGE_DIR, dest_path)
    try:
        _ensure_dir(full_dest)
        shutil.move(full_source, full_dest)
        return True
    except Exception as e:
        print(f"Erro ao mover arquivo {source_path}: {str(e)}")
        return False


def delete_folder(timestamp: str, bucket: str = None) -> bool:
    """
    Deleta uma pasta local associada a um timestamp.
    """
    try:
        folder_path = os.path.join(STORAGE_DIR, timestamp)
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)
        return True
    except Exception as e:
        print(f"Erro ao deletar pasta local {timestamp}: {str(e)}")
        return False


def check_connection() -> bool:
    """
    Verifica se o diretório local de storage existe/pode ser lido.
    """
    try:
        os.makedirs(STORAGE_DIR, exist_ok=True)
        return os.path.exists(STORAGE_DIR)
    except Exception:
        return False