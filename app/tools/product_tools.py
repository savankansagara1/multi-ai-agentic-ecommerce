from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.services.product_service import ProductService


def create_product_tools(db: Session):

    @tool
    def search_products(
        query: str,
        limit: int = 10,
    ):
        """
        Search products in the e-commerce database.

        Use this when the user wants to find products
        by name or keyword.
        """

        return ProductService.search_products(
            db=db,
            query=query,
            limit=limit,
        )

    return {
        "search_products": search_products,
    }