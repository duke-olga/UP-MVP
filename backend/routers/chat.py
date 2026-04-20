from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.modules.llm_explainer.chat_service import chat_with_plan


router = APIRouter(prefix="/api/v1")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ChatRequest(BaseModel):
    message: str


class ChatAnswer(BaseModel):
    answer: str


class ChatResponse(BaseModel):
    data: ChatAnswer


@router.post("/plans/{plan_id}/chat", response_model=ChatResponse)
def chat(plan_id: int, body: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    if not body.message.strip():
        raise HTTPException(status_code=422, detail="Сообщение не может быть пустым")
    answer = chat_with_plan(plan_id=plan_id, user_message=body.message.strip(), db=db)
    return ChatResponse(data=ChatAnswer(answer=answer))
