from app.db.database import SessionLocal
from app.tools.shopping_tools import create_shopping_tools


def main():
    db = SessionLocal()
    try:
        tools = create_shopping_tools(db)
        print("CART:")
        print(tools["view_cart"].invoke({"user_id": 1}))
        print("\nPRODUCT VARIANTS:")
        for item in tools["find_product_variants"].invoke({"query": "Galaxy", "limit": 5}):
            print(item)
    finally:
        db.close()


if __name__ == "__main__":
    main()
