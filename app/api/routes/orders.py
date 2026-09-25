from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.order_service import OrderService

router = APIRouter(
    prefix="/orders",
    tags=["Orders & Shipments"],
)


class CancelOrderRequest(BaseModel):
    user_id: int = Field(default=1)
    reason: str = Field(default="Customer requested cancellation")


class ReturnOrderRequest(BaseModel):
    user_id: int = Field(default=1)
    reason: str = Field(default="Customer requested return")


@router.get("/")
def get_user_orders(
    user_id: int = Query(1, description="Authenticated User ID"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Retrieve recent orders for the specified user."""
    return OrderService.get_user_orders(db=db, user_id=user_id, limit=limit)


@router.get("/{order_identifier}")
def get_order_details(
    order_identifier: str,
    user_id: int = Query(1, description="Authenticated User ID"),
    db: Session = Depends(get_db),
):
    """Retrieve full details of an order strictly scoped to the user."""
    order = OrderService.get_order_details(
        db=db,
        user_id=user_id,
        order_identifier=order_identifier,
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.get("/{order_identifier}/tracking")
def get_shipment_tracking(
    order_identifier: str,
    user_id: int = Query(1, description="Authenticated User ID"),
    db: Session = Depends(get_db),
):
    """Retrieve tracking details and delivery milestones for an order."""
    tracking = OrderService.get_shipment_status(
        db=db,
        user_id=user_id,
        order_identifier=order_identifier,
    )
    if not tracking:
        raise HTTPException(status_code=404, detail="Shipment details not found")
    return tracking


@router.post("/{order_identifier}/cancel")
def cancel_order(
    order_identifier: str,
    request: CancelOrderRequest,
    db: Session = Depends(get_db),
):
    """Cancel an order before it has been shipped."""
    try:
        return OrderService.cancel_order(
            db=db,
            user_id=request.user_id,
            order_identifier=order_identifier,
            reason=request.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{order_identifier}/return")
def request_return(
    order_identifier: str,
    request: ReturnOrderRequest,
    db: Session = Depends(get_db),
):
    """Request a return and refund for an eligible delivered order within 7 days."""
    try:
        return OrderService.request_return(
            db=db,
            user_id=request.user_id,
            order_identifier=order_identifier,
            reason=request.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

