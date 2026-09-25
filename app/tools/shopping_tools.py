from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.services.cart_service import CartService
from app.services.product_service import ProductService


def create_shopping_tools(db: Session):

    @tool
    def view_cart(user_id: int):
        """View the current shopping cart for a user.

        Use this when the user wants to see their cart,
        cart items, quantities, or cart total.
        """
        return CartService.get_cart(
            db=db,
            user_id=user_id,
        )

    @tool
    def find_product_variants(
        query: str,
        limit: int = 5,
    ):
        """Find products and their active variants.

        Use this when the user wants to add a product
        to their cart and the product variant ID is unknown.
        """
        return ProductService.find_product_variants(
            db=db,
            query=query,
            limit=limit,
        )

    @tool
    def add_to_cart(
        user_id: int,
        product_variant_id: int,
        quantity: int,
    ):
        """Add a product variant to the user's cart.

        Use this only after the user has confirmed
        the requested cart addition.
        """
        return CartService.add_item(
            db=db,
            user_id=user_id,
            product_variant_id=product_variant_id,
            quantity=quantity,
        )

    @tool
    def update_cart_quantity(
        user_id: int,
        product_variant_id: int,
        quantity: int,
    ):
        """Update the quantity of an item already in the user's cart.

        Use this only after user confirmation when adjusting
        the number of items in their cart.
        """
        return CartService.update_item_quantity(
            db=db,
            user_id=user_id,
            product_variant_id=product_variant_id,
            quantity=quantity,
        )

    @tool
    def remove_from_cart(
        user_id: int,
        product_variant_id: int,
    ):
        """Remove a product variant completely from the user's cart.

        Use this only after user confirmation when the user wants
        to delete or remove an item from their cart.
        """
        return CartService.remove_item(
            db=db,
            user_id=user_id,
            product_variant_id=product_variant_id,
        )

    @tool
    def clear_cart(
        user_id: int,
    ):
        """Clear all items from the user's cart.

        Use this only after user confirmation when clearing the entire cart.
        """
        return CartService.clear_cart(
            db=db,
            user_id=user_id,
        )

    @tool
    def checkout(
        user_id: int,
    ):
        """Checkout and place an order for all items in the user's cart.

        Use this only after the user has confirmed placing the order.
        """
        return CartService.checkout(
            db=db,
            user_id=user_id,
        )

    return {
        "view_cart": view_cart,
        "find_product_variants": find_product_variants,
        "add_to_cart": add_to_cart,
        "update_cart_quantity": update_cart_quantity,
        "remove_from_cart": remove_from_cart,
        "clear_cart": clear_cart,
        "checkout": checkout,
    }