from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.cart_service import CartService

router = APIRouter(
    prefix="/cart",
    tags=["Shopping Cart"],
)


class AddCartItemRequest(BaseModel):
    variant_id: int
    quantity: int = Field(default=1, ge=1)
    user_id: int = Field(default=1)


class UpdateCartItemRequest(BaseModel):
    quantity: int = Field(..., ge=0)
    user_id: int = Field(default=1)


class CheckoutRequest(BaseModel):
    user_id: int = Field(default=1)
    shipping_address: dict[str, Any] | None = None


@router.get("/")
def get_cart(
    user_id: int = Query(1, description="Authenticated User ID"),
    db: Session = Depends(get_db),
):
    """Retrieve the current shopping cart for the specified user."""
    return CartService.get_cart(db=db, user_id=user_id)


@router.post("/items")
def add_to_cart(
    request: AddCartItemRequest,
    db: Session = Depends(get_db),
):
    """Add a product variant to the user's cart."""
    try:
        return CartService.add_item(
            db=db,
            user_id=request.user_id,
            product_variant_id=request.variant_id,
            quantity=request.quantity,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/items/{variant_id}")
def update_item_quantity(
    variant_id: int,
    request: UpdateCartItemRequest,
    db: Session = Depends(get_db),
):
    """Update item quantity or remove if set to 0."""
    try:
        return CartService.update_item_quantity(
            db=db,
            user_id=request.user_id,
            product_variant_id=variant_id,
            quantity=request.quantity,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/items/{variant_id}")
def remove_item(
    variant_id: int,
    user_id: int = Query(1, description="Authenticated User ID"),
    db: Session = Depends(get_db),
):
    """Remove a product variant completely from the user's cart."""
    try:
        return CartService.remove_item(
            db=db,
            user_id=user_id,
            product_variant_id=variant_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/")
def clear_cart(
    user_id: int = Query(1, description="Authenticated User ID"),
    db: Session = Depends(get_db),
):
    """Clear all items from the user's cart."""
    return CartService.clear_cart(db=db, user_id=user_id)


@router.post("/checkout")
def checkout(
    request: CheckoutRequest,
    db: Session = Depends(get_db),
):
    """Perform atomic checkout: decrements stock, creates order, and clears cart."""
    try:
        return CartService.checkout(
            db=db,
            user_id=request.user_id,
            shipping_address=request.shipping_address,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

