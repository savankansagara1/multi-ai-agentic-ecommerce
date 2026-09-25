from enum import Enum
from pydantic import BaseModel, Field


class Intent(str, Enum):
    PRODUCT = "product"
    SHOPPING = "shopping"
    ORDER = "order"
    SUPPORT = "support"
    UNKNOWN = "unknown"


class IntentClassification(BaseModel):
    intent: Intent = Field(
        description="The primary intent of the user's e-commerce request."
    )


class AddToCartRequest(BaseModel):
    product_query: str = Field(
        description="The product name only, without quantities or action verbs."
    )
    quantity: int = Field(
        default=1,
        ge=1,
        description="The number of items to add."
    )


class UpdateCartRequest(BaseModel):
    product_query: str = Field(
        description="The product name or identifier to update in the cart."
    )
    quantity: int = Field(
        ge=1,
        description="The new target quantity for the cart item."
    )


class RemoveCartRequest(BaseModel):
    product_query: str = Field(
        description="The product name or identifier to remove from the cart."
    )


class OrderQueryRequest(BaseModel):
    order_identifier: str | None = Field(
        default=None,
        description="The order number (e.g. ORD-2026-1001) or order ID, if mentioned in the query."
    )


class CancelOrderRequest(BaseModel):
    order_identifier: str = Field(
        description="The order number or ID to cancel."
    )
    reason: str = Field(
        default="Customer requested cancellation",
        description="The reason for order cancellation."
    )