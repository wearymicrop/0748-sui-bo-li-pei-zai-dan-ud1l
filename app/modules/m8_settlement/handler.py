from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api import preview as run_pipeline
from app.catalog import source_data
from app.modules.m8_settlement.register import confirm, register, rerun
from app.modules.m8_settlement.service import settle

router = APIRouter(prefix="/api/settlements", tags=["批次结算"])


class RegisterBody(BaseModel):
    source: str = ""


class ConfirmBody(BaseModel):
    operator: str = ""


@router.get("/preview/{source}")
def preview(request: Request, source: str):
    data = source_data(request.app.state.ledger, source)
    return settle(run_pipeline(request, source), data)


@router.post("")
def create(request: Request, body: RegisterBody):
    record, outcome = register(request.app.state.ledger, body.source)
    return {"outcome": outcome, **record}


@router.get("/{batch}")
def detail(request: Request, batch: str):
    return request.app.state.ledger.settlement(batch)


@router.post("/{batch}/confirm")
def approve(request: Request, batch: str, body: ConfirmBody):
    record, outcome = confirm(request.app.state.ledger, batch, body.operator)
    return {"outcome": outcome, **record}


@router.post("/{batch}/rerun")
def repeat(request: Request, batch: str):
    return rerun(request.app.state.ledger, batch)
