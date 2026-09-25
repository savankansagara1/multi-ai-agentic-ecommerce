from app.db.database import SessionLocal
from app.tools.product_tools import create_product_tools


if __name__ == "__main__":
    db = SessionLocal()

    try:
        tools = create_product_tools(db)

        search_products = tools["search_products"]

        result = search_products.invoke(
            {
                "query": "Galaxy",
                "limit": 5,
            }
        )

        print("\nSEARCH RESULT:")

        for product in result:
            print(
                product.id,
                product.name,
                product.brand,
            )

    finally:
        db.close()