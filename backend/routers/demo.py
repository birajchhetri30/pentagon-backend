from fastapi import APIRouter, Query
from typing import Optional
import math
import random
import uuid
from datetime import datetime, timedelta

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


@router.get("/proposal")
def get_demo_proposal(
    current_lr: str = Query(default="1e-4"),
    current_dropout: str = Query(default="0.2"),
    current_batch_size: str = Query(default="8"),
    source_epoch: int = Query(default=15),
):
    lr_map = {"1e-2": "1e-3", "1e-3": "1e-4", "1e-4": "1e-5", "1e-5": "1e-6", "1e-6": "1e-6"}
    bs_map = {"2": "4", "4": "4", "8": "4", "16": "8", "32": "16", "64": "32"}
    severity = random.choice(["moderate", "severe"])
    trend = random.choice(["DEGRADING", "STAGNATING"])
    now = datetime.utcnow()

    return {
        "proposal_id": str(uuid.uuid4()),
        "status": "pending",
        "proposed_params": {
            "learning_rate": lr_map.get(current_lr, "1e-5"),
            "weight_decay": "1e-3",
            "batch_size": bs_map.get(current_batch_size, "4"),
            "momentum": "0.95",
            "aux_loss_weight": "0.4",
        },
        "rationale": f"Overfitting detected at epoch {source_epoch}. Validation mIoU has {'degraded over the last 5 epochs' if trend == 'DEGRADING' else 'stagnated for 4 consecutive epochs'}. "
                     f"Recommending lower learning rate and reduced batch size to improve generalization.",
        "overfitting_severity": severity,
        "trend": trend,
        "confidence": "high" if severity == "severe" else "medium",
        "source_epoch": source_epoch,
        "applies_via": "checkpoint_restart",
        "expires_at": (now + timedelta(hours=24)).isoformat() + "Z",
        "created_at": now.isoformat() + "Z",
    }


@router.get("/orchestrator-log")
def get_demo_orchestrator_log(total_epochs: int = Query(default=10)):
    logs = []
    for e in range(1, total_epochs + 1):
        if e <= total_epochs * 0.3:
            decision = "continue"
            agents = ["training_monitor"]
            rationale = f"Epoch {e}: Loss decreasing normally. No intervention needed."
        elif e <= total_epochs * 0.5:
            decision = "continue"
            agents = ["training_monitor", "overfitting_detector"]
            rationale = f"Epoch {e}: Minor gap between train/val loss. Monitoring closely."
        elif e == int(total_epochs * 0.6):
            decision = "hitl_pause"
            agents = ["training_monitor", "overfitting_detector", "optimizer"]
            rationale = f"Epoch {e}: Severe overfitting detected. Pausing for human review."
        else:
            decision = "continue"
            agents = ["training_monitor"]
            rationale = f"Epoch {e}: Training resumed with adjusted parameters. Converging."

        logs.append({
            "id": str(uuid.uuid4()),
            "epoch": e,
            "decision": decision,
            "agents_called": agents,
            "rationale": rationale,
            "duration_ms": random.randint(200, 5000),
            "created_at": (datetime.utcnow() - timedelta(minutes=total_epochs - e)).isoformat() + "Z",
        })
    return list(reversed(logs))


@router.get("/training-report")
def get_demo_training_report(total_epochs: int = Query(default=10)):
    best_epoch = int(total_epochs * 0.8)
    return {
        "id": str(uuid.uuid4()),
        "run_number": 1,
        "total_epochs": total_epochs,
        "best_epoch": best_epoch,
        "best_val_loss": round(random.uniform(0.25, 0.35), 4),
        "best_val_accuracy": round(random.uniform(0.86, 0.92), 4),
        "final_val_loss": round(random.uniform(0.30, 0.40), 4),
        "final_val_accuracy": round(random.uniform(0.84, 0.90), 4),
        "loss_improvement": round(random.uniform(0.55, 0.75), 4),
        "accuracy_improvement": round(random.uniform(0.30, 0.45), 4),
        "training_outcome": "completed",
        "stop_reason": None,
        "summary": f"Training converged after {total_epochs} epochs. Best validation accuracy achieved at epoch {best_epoch}. "
                   f"Model shows strong generalization with minimal overfitting after hyperparameter adjustment.",
        "alerts_sent": [
            {"severity": "warning", "message": f"val_accuracy dipped at epoch {int(total_epochs * 0.5)}"},
            {"severity": "info", "message": "Hyperparameters adjusted via HITL at epoch " + str(int(total_epochs * 0.6))},
        ],
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
