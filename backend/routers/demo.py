from fastapi import APIRouter, Query
import math
import random

router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/metrics")
def get_demo_metrics(total_epochs: int = Query(default=10, ge=1, le=200)):
    metrics = []
    best = 0.0
    for e in range(1, total_epochs + 1):
        t = e / total_epochs
        decay = math.exp(-3.5 * t)
        train_loss = 2.5 * decay + random.uniform(0.02, 0.12)
        val_miou = min(0.95, 0.85 * (1 - decay) + random.uniform(-0.01, 0.02))
        best = max(best, val_miou)
        metrics.append({
            "epoch": e,
            "total_epochs": total_epochs,
            "train_loss": round(train_loss, 4),
            "val_miou": round(val_miou, 4),
            "best_miou": round(best, 4),
        })
    return metrics
