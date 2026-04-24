"""Authenticated /history routes for a user's past evaluations."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from backend.auth.deps import get_current_user_required
from backend.db.base import get_db
from backend.db.models import Evaluation, User
from backend.schemas.evaluation import EvaluationListItem, EvaluationOut

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=list[EvaluationListItem])
def list_history(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required),
) -> list[Evaluation]:
    """Return the logged-in user's evaluations, newest first."""
    return (
        db.query(Evaluation)
        .filter(Evaluation.user_id == user.id)
        .order_by(Evaluation.created_at.desc())
        .limit(100)
        .all()
    )


@router.get("/{evaluation_id}", response_model=EvaluationOut)
def get_history_item(
    evaluation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required),
) -> Evaluation:
    """Return one full evaluation report owned by the logged-in user."""
    row = db.get(Evaluation, evaluation_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return row


@router.delete("/{evaluation_id}")
def delete_history_item(
    evaluation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required),
) -> Response:
    """Permanently delete one evaluation owned by the logged-in user."""
    row = db.get(Evaluation, evaluation_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    db.delete(row)
    db.commit()
    return Response(status_code=204)
