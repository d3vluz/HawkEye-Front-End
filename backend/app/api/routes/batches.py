"""
Rotas de gerenciamento de lotes.
"""
from fastapi import APIRouter

from app.schemas import (
    CreateBatchRequest,
    CreateBatchResponse,
    RejectBatchRequest,
)
from app.services import create_batch, reject_batch

router = APIRouter(prefix="/api/batches", tags=["Batches"])


@router.post("/create", response_model=CreateBatchResponse)
async def create_batch_endpoint(request: CreateBatchRequest):
    """
    Cria um novo lote com as capturas processadas.
    
    - Move arquivos do bucket temporário para o permanente
    - Cria registros no banco de dados (batch, captures, compartments, defects)
    - Calcula métricas de qualidade
    - Limpa arquivos temporários
    
    **Campos obrigatórios:**
    - **name**: Nome do lote
    - **captures**: Lista de capturas processadas
    """
    result = await create_batch(request)
    return CreateBatchResponse(**result)


@router.post("/reject")
async def reject_batch_endpoint(request: RejectBatchRequest):
    """
    Rejeita um lote, deletando todos os arquivos temporários.
    
    - **timestamp**: Timestamp do lote a rejeitar
    """
    return await reject_batch(request.timestamp)

@router.get("/")
async def get_all_batches():
    """Retorna a lista de todos os lotes."""
    from app.core.db import db
    
    batches = await db.batch.find_many(
        order={"createdAt": "desc"}
    )
    
    return {
        "batches": [
            {
                "id": b.id,
                "name": b.name,
                "description": b.description,
                "total_captures": b.totalCaptures,
                "total_defects": 0, # Simplify or calculate if needed
                "quality_score": (b.validCaptures / b.totalCaptures * 100) if b.totalCaptures > 0 else 0,
                "created_at": b.createdAt.isoformat()
            }
            for b in batches
        ]
    }

@router.get("/{batch_id}")
async def get_batch_by_id(batch_id: str):
    """Retorna detalhes de um lote específico."""
    from app.core.db import db
    
    batch = await db.batch.find_unique(
        where={"id": batch_id},
        include={"captures": {"include": {"compartments": True}}}
    )
    
    if not batch:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Lote não encontrado")
        
    return {
        "batch": {
            "id": batch.id,
            "name": batch.name,
            "description": batch.description,
            "created_at": batch.createdAt.isoformat(),
            "total_captures": batch.totalCaptures,
            "valid_captures": batch.validCaptures,
            "invalid_captures": batch.invalidCaptures,
            "total_defects": sum(c.defectsCount for c in batch.captures),
            "quality_score": (batch.validCaptures / batch.totalCaptures * 100) if batch.totalCaptures > 0 else 0
        },
        "captures": [
            {
                "id": c.id,
                "filename": c.filename,
                "is_valid": c.isValid,
                "original_uri": c.originalUri,
                "processed_uri": c.processedUri,
                "processed_areas_uri": c.processedAreasUri,
                "processed_pins_uri": c.processedPinsUri,
                "processed_shaft_uri": c.processedShaftUri,
                "defects_count": c.defectsCount,
                "hasMissingPins": c.hasMissingPins,
                "hasExtraPins": c.hasExtraPins,
                "hasDamagedPins": c.hasDamagedPins,
                "hasWrongColorPins": c.hasWrongColorPins,
                "hasStructureDamage": c.hasStructureDamage,
                "hasShaftDefects": c.hasShaftDefects,
            }
            for c in batch.captures
        ]
    }

@router.delete("/{batch_id}")
async def delete_batch_by_id(batch_id: str):
    """Deleta um lote permanentemente."""
    from app.core.db import db
    await db.batch.delete(where={"id": batch_id})
    return {"success": True}