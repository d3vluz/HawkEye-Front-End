"""
Rotas para métricas do dashboard.
"""
from fastapi import APIRouter
from app.core.db import db

router = APIRouter(prefix="/api/metrics", tags=["Metrics"])

@router.get("/dashboard")
async def get_dashboard_metrics():
    """
    Retorna as métricas e estatísticas gerais (ex-Supabase getDashboardMetrics).
    """
    batches = await db.batch.find_many(
        include={"captures": True},
        order={"createdAt": "desc"}
    )
    
    total_lotes = len(batches)
    total_imagens = sum(b.totalCaptures for b in batches)
    
    if total_lotes == 0:
        return {
            "totalBatches": 0,
            "totalImages": 0,
            "validImages": 0,
            "totalDefects": 0,
            "successRate": 0,
            "qualityScore": 0,
            "recentBatches": [],
            "defectsRanking": [],
            "dailyStats": [],
            "topDefects": [],
            "defectTrends": [],
            "errorDistribution": [],
            "validityDistribution": []
        }
        
    total_valid = sum(b.validCaptures for b in batches)
    success_rate = (total_valid / total_imagens * 100) if total_imagens > 0 else 0
    total_defects = 0
    
    # Ranking types usually calculated per defect type, but since we simplified schema:
    # We will compute basic stats from captures directly.
    defect_counts = {
        "Pino Ausente": 0,
        "Pino Extra": 0,
        "Pino Danificado": 0,
        "Cor Incorreta": 0,
        "Dano Estrutural": 0,
        "Defeito na Haste": 0
    }
    
    for b in batches:
        for c in b.captures:
            total_defects += c.defectsCount
            if c.hasMissingPins: defect_counts["Pino Ausente"] += 1
            if c.hasExtraPins: defect_counts["Pino Extra"] += 1
            if c.hasDamagedPins: defect_counts["Pino Danificado"] += 1
            if c.hasWrongColorPins: defect_counts["Cor Incorreta"] += 1
            if c.hasStructureDamage: defect_counts["Dano Estrutural"] += 1
            if c.hasShaftDefects: defect_counts["Defeito na Haste"] += 1

    ranking = [{"rank": i+1, "code": k.replace(' ', '_').upper(), "label": k, "count": v, "severity": 2, "percentage": (v / total_defects * 100) if total_defects > 0 else 0} for i, (k, v) in enumerate(defect_counts.items()) if v > 0]
    ranking.sort(key=lambda x: x["count"], reverse=True)

    formatted_batches = [
        {
            "id": b.id,
            "name": b.name,
            "totalCaptures": b.totalCaptures,
            "validCaptures": b.validCaptures,
            "qualityScore": (b.validCaptures / b.totalCaptures * 100) if b.totalCaptures > 0 else 0,
            "defectCount": sum((c.defectsCount for c in getattr(b, "captures", [])))
        }
        for b in batches[:10]
    ]

    return {
        "totalBatches": total_lotes,
        "totalImages": total_imagens,
        "validImages": total_valid,
        "totalDefects": total_defects,
        "successRate": success_rate,
        "qualityScore": success_rate,
        "recentBatches": formatted_batches,
        "defectsRanking": ranking,
        "dailyStats": [], # To be implemented
        "topDefects": ranking[:3],
        "defectTrends": [], # To be implemented
        "errorDistribution": [{"name": k, "value": v} for k, v in defect_counts.items() if v > 0],
        "validityDistribution": [
            {"name": "Válidas", "value": total_valid, "color": "#10b981"},
            {"name": "Com Defeito", "value": total_imagens - total_valid, "color": "#ef4444"}
        ]
    }
