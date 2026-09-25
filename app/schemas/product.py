from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ProductVariantResponse(BaseModel):
    id: int
    sku: str
    name: str
    price: Decimal
    discount: Decimal
    stock_quantity: int
    specifications: dict | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class ProductResponse(BaseModel):
    id: int
    category_id: int
    name: str
    description: str | None
    brand: str | None
    rating: float | None
    specifications: dict | None
    variants: list[ProductVariantResponse] = []

    model_config = ConfigDict(from_attributes=True)