from app.db.database import SessionLocal
from app.tools.shopping_tools import create_shopping_tools


if __name__ == "__main__":
    db = SessionLocal()

    try:
        tools = create_shopping_tools(db)

        view_cart = tools["view_cart"]

        result = view_cart.invoke({
            "user_id": 1,
        })

        print("\nCART:")
        print(result)

    finally:
        db.close()


    add_to_cart = tools["add_to_cart"]

    result = add_to_cart.invoke({
        "user_id": 1,
        "product_variant_id": 1,
        "quantity": 1,
    })

    print("\nADD TO CART:")
    print(result)


    find_product_variants = tools["find_product_variants"]

    result = find_product_variants.invoke({
        "query": "Galaxy",
        "limit": 5,
    })

    print("\nPRODUCT VARIANTS:")
    for item in result:
        print(item)
    