"""
Dependências compartilhadas da aplicação.
"""
import os
import cv2
import numpy as np
from app.core.config import settings



# === Border Mask (para processamento de hastes) ===

BORDER_MASK: np.ndarray | None = None

if os.path.exists(settings.BORDER_MASK_PATH):
    BORDER_MASK = cv2.imread(settings.BORDER_MASK_PATH)
    if BORDER_MASK is not None:
        print(f"✅ Máscara de borda carregada: {settings.BORDER_MASK_PATH}")
    else:
        print(f"⚠️ Erro ao carregar máscara: {settings.BORDER_MASK_PATH}")
else:
    print(f"⚠️ Máscara não encontrada: {settings.BORDER_MASK_PATH}")
    print(f"   O processamento continuará sem remoção de borda.")




def get_border_mask() -> np.ndarray | None:
    """Retorna a máscara de borda carregada."""
    return BORDER_MASK