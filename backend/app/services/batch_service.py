"""
Serviço de gerenciamento de lotes (batches).

Lê imagens do cache em memória e faz upload direto para o bucket permanente,
eliminando o bucket temporário completamente.
"""
import cv2
import uuid
from typing import Dict, Any, List, Tuple
from fastapi import HTTPException

from app.core.config import settings
from app.core.db import db
from app.core.image_cache import get_image_cache, CachedImage
from app.repositories import get_public_url, upload_processed_image
from app.schemas import CreateBatchRequest, CaptureData


def _encode_image_to_bytes(image) -> bytes:
    """Codifica numpy array para bytes PNG."""
    success, buffer = cv2.imencode('.png', image)
    if not success:
        raise ValueError("Falha ao codificar imagem para PNG")
    return buffer.tobytes()
def _upload_image_to_permanent(image_bytes: bytes, storage_path: str) -> str:
    """Faz upload de uma imagem diretamente para o storage permanente."""
    from app.repositories.storage import upload_image
    
    upload_image(
        file_content=image_bytes,
        storage_path=storage_path,
        content_type="image/png"
    )
    return storage_path


def _upload_cached_image_to_permanent(
    cached_img: CachedImage,
    timestamp: str
) -> Dict[str, str]:
    """
    Faz upload de todas as imagens de uma captura do cache para o bucket permanente.
    
    Returns:
        Dicionário com os caminhos de cada imagem
    """
    sha256 = cached_img.sha256
    paths = {}
    
    # Upload da imagem original
    original_path = f"{timestamp}/{sha256}/original_{cached_img.filename}"
    original_bytes = _encode_image_to_bytes(cached_img.original)
    _upload_image_to_permanent(original_bytes, original_path)
    paths["original"] = original_path
    print(f"   ✅ Upload: original_{cached_img.filename}")
    
    # Upload das imagens processadas
    processed_types = [
        ("areas", cached_img.processed_areas),
        ("pins", cached_img.processed_pins),
        ("boxes", cached_img.processed_boxes),
        ("shafts", cached_img.processed_shafts),
    ]
    
    for img_type, img_data in processed_types:
        if img_data is not None:
            path = f"{timestamp}/{sha256}/processed_{img_type}.png"
            img_bytes = _encode_image_to_bytes(img_data)
            _upload_image_to_permanent(img_bytes, path)
            paths[img_type] = path
            print(f"   ✅ Upload: processed_{img_type}.png")
    
    return paths


async def _create_batch_record(
    name: str,
    description: str,
    total_captures: int,
    valid_captures: int,
    invalid_captures: int,
    total_defects: int,
    quality_score: float
) -> str:
    """
    Cria o registro do lote no banco de dados.
    
    Returns:
        ID do lote criado
    """
    batch_result = await db.batch.create(
        data={
            "name": name,
            "description": description,
            "totalCaptures": total_captures,
            "validCaptures": valid_captures,
            "invalidCaptures": invalid_captures,
        }
    )
    
    return batch_result.id


async def _create_capture_record(
    batch_id: str,
    capture: CaptureData,
    uploaded_paths: Dict[str, str]
) -> str:
    """
    Cria o registro de uma captura no banco de dados.
    
    Returns:
        ID da captura criada
    """
    capture_data = {
        "batchId": batch_id,
        "filename": capture.filename,
        "sha256": capture.sha256,
        "originalUri": get_public_url(uploaded_paths.get("original", "")),
        "processedUri": get_public_url(uploaded_paths.get("boxes", "")),
        "processedAreasUri": get_public_url(uploaded_paths.get("areas", "")),
        "processedPinsUri": get_public_url(uploaded_paths.get("pins", "")),
        "processedShaftUri": get_public_url(uploaded_paths.get("shafts", "")),
        "isValid": capture.is_valid,
        "areasDetected": capture.areas_detected,
        "pinsDetected": capture.pins_detected,
        "defectsCount": capture.defects_count,
        "hasMissingPins": capture.has_missing_pins,
        "hasExtraPins": capture.has_extra_pins,
        "hasDamagedPins": capture.has_damaged_pins,
        "hasWrongColorPins": capture.has_wrong_color_pins,
        "hasStructureDamage": capture.has_structure_damage,
        "hasShaftDefects": capture.has_shaft_defects
    }
    
    capture_result = await db.capture.create(data=capture_data)
    
    return capture_result.id


async def _create_compartments(
    capture_id: str,
    capture: CaptureData
) -> Dict[tuple, str]:
    """
    Cria os registros de compartimentos no banco de dados.
    
    Returns:
        Mapeamento de (grid_row, grid_col) -> compartment_id
    """
    if not capture.compartments:
        return {}
    
    print(f"      📦 Criando {len(capture.compartments)} compartimentos...")
    
    compartments_data = [
        {
            "id": str(uuid.uuid4()),
            "captureId": capture_id,
            "gridRow": comp.grid_row,
            "gridCol": comp.grid_col,
            "bboxX": comp.bbox_x,
            "bboxY": comp.bbox_y,
            "bboxWidth": comp.bbox_width,
            "bboxHeight": comp.bbox_height,
            "pinsCount": comp.pins_count,
            "isValid": comp.is_valid,
            "hasDefect": comp.has_defect
        }
        for comp in capture.compartments
    ]
    
    comp_result = await db.compartment.create_many(data=compartments_data)
    
    compartments_map = {}
    for comp in compartments_data:
        key = (comp["gridRow"], comp["gridCol"])
        compartments_map[key] = comp["id"]
        
    return compartments_map


    # Prisma removed Defect model mapping from earlier versions
    # We simplified the schema to boolean columns in Capture/Compartments 
    # based on the new Prisma Schema where there are no Defect tables.
    pass


async def create_batch(request: CreateBatchRequest) -> Dict[str, Any]:
    """
    Cria um novo lote a partir das imagens no cache.
    
    - Lê imagens do cache em memória
    - Faz upload direto para o bucket permanente
    - Cria registros no banco de dados
    - Limpa o cache após conclusão
    
    Args:
        request: Dados do lote a criar
    
    Returns:
        Dicionário com success, message, batch_id, métricas
    """
    cache = get_image_cache()
    
    try:
        print(f"\n{'='*80}\n📦 Criando lote: {request.name}\n{'='*80}")
        
        if not request.captures:
            raise HTTPException(
                status_code=400,
                detail="Lote deve conter ao menos uma captura"
            )
        
        # Extrair timestamp do primeiro arquivo
        original_uri = request.captures[0].original_uri
        print(f"DEBUG original_uri: {original_uri}")
        timestamp = original_uri.split('/api/files/')[-1].split('/')[0]
        print(f"DEBUG extracted_timestamp: {timestamp}")
        
        batch = cache.get_batch(timestamp)
        if not batch:
            raise HTTPException(
                status_code=404,
                detail=f"Lote não encontrado no cache: {timestamp}"
            )
        
        print(f"\n📤 Fazendo upload para storage permanente...")
        uploaded_paths_map: Dict[str, Dict[str, str]] = {}
        
        for capture in request.captures:
            cached_img = cache.get_image(timestamp, capture.sha256)
            if not cached_img:
                raise HTTPException(
                    status_code=404,
                    detail=f"Imagem não encontrada no cache: {capture.sha256}"
                )
            
            print(f"\n   📷 {capture.filename}")
            paths = _upload_cached_image_to_permanent(cached_img, timestamp)
            uploaded_paths_map[capture.sha256] = paths
        
        # Calcular métricas
        total_captures = len(request.captures)
        valid_captures = sum(1 for c in request.captures if c.is_valid)
        invalid_captures = total_captures - valid_captures
        total_defects = sum(c.defects_count for c in request.captures)
        quality_score = (valid_captures / total_captures * 100) if total_captures > 0 else 0
        
        print(f"\n📊 Métricas: Total:{total_captures} | Válidas:{valid_captures} | Inválidas:{invalid_captures} | Defeitos:{total_defects} | Score:{quality_score:.2f}%")
        
        # Criar registro do lote
        print(f"\n💾 Criando lote no banco...")
        batch_id = await _create_batch_record(
            name=request.name,
            description=request.description,
            total_captures=total_captures,
            valid_captures=valid_captures,
            invalid_captures=invalid_captures,
            total_defects=total_defects,
            quality_score=quality_score
        )
        
        for capture in request.captures:
            uploaded_paths = uploaded_paths_map[capture.sha256]
            capture_id = await _create_capture_record(batch_id, capture, uploaded_paths)
            print(f"   ✅ Capture: {capture.filename} ({capture_id})")
            
            compartments_map = await _create_compartments(capture_id, capture)
        
        print(f"\n🧹 Limpando cache...")
        cache.clear_batch(timestamp)
        print(f"   ✅ Cache do lote {timestamp} liberado")
        
        print(f"\n{'='*80}\n✅ LOTE CRIADO COM SUCESSO!\n{'='*80}\n")
        
        return {
            "success": True,
            "message": f"Lote '{request.name}' criado com sucesso",
            "batch_id": batch_id,
            "total_captures": total_captures,
            "valid_captures": valid_captures,
            "invalid_captures": invalid_captures
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"\n❌ Erro: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao criar lote: {str(e)}"
        )


async def reject_batch(timestamp: str) -> Dict[str, Any]:
    """
    Rejeita um lote, deletando todos os arquivos temporários.
    
    Args:
        timestamp: Timestamp do lote a rejeitar
    
    Returns:
        Dicionário com success, message, timestamp
    """
    cache = get_image_cache()
    
    try:
        print(f"\n{'='*80}\n❌ Rejeitando lote: {timestamp}\n{'='*80}")
        
        batch = cache.get_batch(timestamp)
        if not batch:
            print(f"   ⚠️ Lote não encontrado no cache (pode já ter sido limpo)")
        else:
            memory_mb = batch.memory_estimate_mb
            print(f"\n🧹 Limpando cache ({memory_mb:.2f} MB)...")
            cache.clear_batch(timestamp)
            print(f"   ✅ Cache do lote {timestamp} liberado")
        
        print(f"\n{'='*80}\n✅ LOTE REJEITADO!\n{'='*80}\n")
        
        return {
            "success": True,
            "message": f"Lote {timestamp} rejeitado",
            "timestamp": timestamp
        }
    
    except Exception as e:
        print(f"\n❌ Erro: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao rejeitar: {str(e)}"
        )