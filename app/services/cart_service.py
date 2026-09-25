from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.shopping import Cart, CartItem
from app.db.models.product import ProductVariant
from app.db.models.support import AuditLog


class CartService:

    @staticmethod
    def get_or_create_cart(
        db: Session,
        user_id: int,
    ) -> Cart:
        """Retrieve existing active cart or initialize a new one for the user."""
        cart = db.scalar(
            select(Cart)
            .where(Cart.user_id == user_id)
            .order_by(Cart.id)
        )

        if cart:
            return cart

        cart = Cart(user_id=user_id)
        db.add(cart)
        db.flush()

        return cart

    @staticmethod
    def get_cart(
        db: Session,
        user_id: int,
    ) -> dict:
        """Return a structured, serializable representation of user's shopping cart."""
        cart = CartService.get_or_create_cart(
            db=db,
            user_id=user_id,
        )

        items = []

        for item in cart.items:
            variant = item.product_variant
            product = variant.product if variant else None

            product_name = product.name if product else "Unknown Product"
            variant_name = variant.name if variant else ""
            unit_price = float(variant.price) if variant else 0.0
            line_total = round(item.quantity * unit_price, 2)

            items.append({
                "cart_item_id": item.id,
                "product_variant_id": item.product_variant_id,
                "product_name": product_name,
                "variant_name": variant_name,
                "sku": variant.sku if variant else "",
                "quantity": item.quantity,
                "unit_price": unit_price,
                "line_total": line_total,
                "stock_available": variant.stock_quantity if variant else 0,
            })

        total = round(sum(item["line_total"] for item in items), 2)

        return {
            "cart_id": cart.id,
            "user_id": user_id,
            "items": items,
            "total": total,
            "item_count": sum(item["quantity"] for item in items),
        }

    @staticmethod
    def add_item(
        db: Session,
        user_id: int,
        product_variant_id: int,
        quantity: int,
    ) -> dict:
        """Add a product variant to the cart after validating inputs and stock."""
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero")

        variant = db.scalar(
            select(ProductVariant)
            .where(
                ProductVariant.id == product_variant_id,
                ProductVariant.is_active.is_(True),
            )
        )

        if variant is None:
            raise ValueError("Product variant not found or inactive")

        if variant.stock_quantity < quantity:
            raise ValueError(
                f"Insufficient stock. Only {variant.stock_quantity} unit(s) are available."
            )

        cart = CartService.get_or_create_cart(
            db=db,
            user_id=user_id,
        )

        item = db.scalar(
            select(CartItem)
            .where(
                CartItem.cart_id == cart.id,
                CartItem.product_variant_id == product_variant_id,
            )
        )

        old_qty = 0
        if item:
            old_qty = item.quantity
            new_quantity = item.quantity + quantity

            if variant.stock_quantity < new_quantity:
                raise ValueError(
                    f"Insufficient stock. You already have {item.quantity} in cart and only {variant.stock_quantity} total exist."
                )

            item.quantity = new_quantity
        else:
            item = CartItem(
                cart_id=cart.id,
                product_variant_id=product_variant_id,
                quantity=quantity,
            )
            db.add(item)

        # Audit log for transactional traceability
        audit = AuditLog(
            user_id=user_id,
            action="ADD_TO_CART",
            entity_type="cart_item",
            old_value={"quantity": old_qty} if old_qty else None,
            new_value={"quantity": item.quantity, "variant_id": product_variant_id},
        )
        db.add(audit)

        db.commit()
        db.refresh(item)

        return {
            "cart_item_id": item.id,
            "product_variant_id": item.product_variant_id,
            "product_name": variant.product.name if variant.product else "",
            "variant_name": variant.name,
            "quantity": item.quantity,
            "unit_price": float(variant.price),
        }

    @staticmethod
    def update_item_quantity(
        db: Session,
        user_id: int,
        product_variant_id: int,
        quantity: int,
    ) -> dict:
        """Update the quantity of an existing cart item."""
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero")

        cart = CartService.get_or_create_cart(
            db=db,
            user_id=user_id,
        )

        item = db.scalar(
            select(CartItem)
            .where(
                CartItem.cart_id == cart.id,
                CartItem.product_variant_id == product_variant_id,
            )
        )

        if not item:
            raise ValueError("Item not found in your cart")

        variant = item.product_variant
        if not variant or not variant.is_active:
            raise ValueError("Product variant is no longer available")

        if variant.stock_quantity < quantity:
            raise ValueError(
                f"Insufficient stock. Only {variant.stock_quantity} unit(s) are available."
            )

        old_quantity = item.quantity
        item.quantity = quantity

        # Audit log
        audit = AuditLog(
            user_id=user_id,
            action="UPDATE_CART_QUANTITY",
            entity_type="cart_item",
            entity_id=item.id,
            old_value={"quantity": old_quantity},
            new_value={"quantity": quantity},
        )
        db.add(audit)

        db.commit()
        db.refresh(item)

        return {
            "cart_item_id": item.id,
            "product_variant_id": item.product_variant_id,
            "product_name": variant.product.name if variant.product else "",
            "variant_name": variant.name,
            "old_quantity": old_quantity,
            "new_quantity": item.quantity,
            "unit_price": float(variant.price),
        }

    @staticmethod
    def remove_item(
        db: Session,
        user_id: int,
        product_variant_id: int,
    ) -> dict:
        """Remove an item from the user's cart."""
        cart = CartService.get_or_create_cart(
            db=db,
            user_id=user_id,
        )

        item = db.scalar(
            select(CartItem)
            .where(
                CartItem.cart_id == cart.id,
                CartItem.product_variant_id == product_variant_id,
            )
        )

        if not item:
            raise ValueError("Item not found in your cart")

        variant = item.product_variant
        product_name = variant.product.name if variant and variant.product else "Item"
        variant_name = variant.name if variant else ""
        item_id = item.id
        removed_quantity = item.quantity

        db.delete(item)

        # Audit log
        audit = AuditLog(
            user_id=user_id,
            action="REMOVE_FROM_CART",
            entity_type="cart_item",
            entity_id=item_id,
            old_value={"variant_id": product_variant_id, "quantity": removed_quantity},
            new_value=None,
        )
        db.add(audit)

        db.commit()

        return {
            "cart_item_id": item_id,
            "product_variant_id": product_variant_id,
            "product_name": product_name,
            "variant_name": variant_name,
            "removed_quantity": removed_quantity,
            "message": f"Removed {product_name} ({variant_name}) from your cart.",
        }

    @staticmethod
    def clear_cart(
        db: Session,
        user_id: int,
    ) -> dict:
        """Remove all items from the user's cart."""
        cart = CartService.get_or_create_cart(
            db=db,
            user_id=user_id,
        )

        count = len(cart.items)
        for item in list(cart.items):
            db.delete(item)

        db.commit()

        return {
            "cart_id": cart.id,
            "items_removed": count,
            "message": "Cart cleared successfully.",
        }

    @staticmethod
    def checkout(
        db: Session,
        user_id: int,
        shipping_address: dict | None = None,
    ) -> dict:
        """Execute atomic checkout: validates cart, checks & decrements stock,
        creates Order, OrderItem, Payment, Shipment, clears the cart, and logs audit."""
        import uuid
        import random
        from datetime import datetime, timezone, timedelta
        from decimal import Decimal
        from app.db.models.order import Order, OrderItem, Payment, Shipment, ShipmentItem

        cart = CartService.get_or_create_cart(db=db, user_id=user_id)
        if not cart.items:
            raise ValueError("Your cart is empty. Add products to cart before checkout.")

        # Default shipping address if none provided
        if not shipping_address:
            shipping_address = {
                "recipient_name": "Valued Customer",
                "address_line1": "123 Tech Park Blvd",
                "city": "Bangalore",
                "state": "Karnataka",
                "postal_code": "560001",
                "country": "India",
            }

        # Validate stock availability for all items before any mutation
        total_subtotal = Decimal("0.00")
        items_to_process = []

        for item in cart.items:
            variant = item.product_variant
            if not variant or not variant.is_active:
                raise ValueError(f"Product variant for item {item.id} is no longer active.")
            if variant.stock_quantity < item.quantity:
                raise ValueError(
                    f"Insufficient stock for {variant.name}. Requested: {item.quantity}, available: {variant.stock_quantity}."
                )
            
            unit_price = Decimal(str(variant.price))
            line_price = unit_price * Decimal(item.quantity)
            total_subtotal += line_price

            items_to_process.append({
                "item": item,
                "variant": variant,
                "unit_price": unit_price,
                "quantity": item.quantity,
                "name_snapshot": f"{variant.product.name} ({variant.name})" if variant.product else variant.name,
            })

        # Calculate taxes and shipping
        discount_amount = Decimal("0.00")
        shipping_amount = Decimal("0.00")  # Free shipping
        tax_amount = (total_subtotal * Decimal("0.18")).quantize(Decimal("0.01"))  # 18% GST standard
        total_amount = total_subtotal + shipping_amount + tax_amount

        order_number = f"ORD-2026-{random.randint(10000, 99999)}"
        now = datetime.now(timezone.utc)

        # Create Order
        order = Order(
            user_id=user_id,
            order_number=order_number,
            status="placed",
            subtotal=total_subtotal,
            discount_amount=discount_amount,
            shipping_amount=shipping_amount,
            tax_amount=tax_amount,
            total_amount=total_amount,
            shipping_address_snapshot=shipping_address,
            created_at=now,
        )
        db.add(order)
        db.flush()

        # Create OrderItems, decrement stock, and prepare for shipment
        created_order_items = []
        for info in items_to_process:
            order_item = OrderItem(
                order_id=order.id,
                product_variant_id=info["variant"].id,
                quantity=info["quantity"],
                unit_price=info["unit_price"],
                product_name_snapshot=info["name_snapshot"],
            )
            db.add(order_item)
            db.flush()
            created_order_items.append(order_item)

            # Decrement variant stock atomically
            info["variant"].stock_quantity -= info["quantity"]

            # Remove item from cart
            db.delete(info["item"])

        # Create Payment
        payment = Payment(
            order_id=order.id,
            amount=total_amount,
            status="completed",
            payment_method="UPI",
            transaction_reference=f"UPI-{uuid.uuid4().hex[:10].upper()}",
            created_at=now,
        )
        db.add(payment)

        # Create Shipment
        shipment = Shipment(
            order_id=order.id,
            tracking_number=f"TRK{uuid.uuid4().hex[:8].upper()}IN",
            carrier="Delhivery",
            status="manifested",
            shipped_at=now,
            estimated_delivery_at=now + timedelta(days=3),
            created_at=now,
        )
        db.add(shipment)
        db.flush()

        for oi in created_order_items:
            db.add(ShipmentItem(
                shipment_id=shipment.id,
                order_item_id=oi.id,
                quantity=oi.quantity,
            ))

        # Audit log
        audit = AuditLog(
            user_id=user_id,
            action="CHECKOUT",
            entity_type="order",
            entity_id=order.id,
            old_value={"cart_id": cart.id},
            new_value={
                "order_number": order.order_number,
                "total_amount": float(total_amount),
                "items_count": len(items_to_process),
            },
        )
        db.add(audit)

        db.commit()
        db.refresh(order)

        return {
            "order_id": order.id,
            "order_number": order.order_number,
            "status": order.status,
            "subtotal": float(order.subtotal),
            "tax_amount": float(order.tax_amount),
            "total_amount": float(order.total_amount),
            "items_count": len(items_to_process),
            "tracking_number": shipment.tracking_number,
            "estimated_delivery": shipment.estimated_delivery_at.strftime("%Y-%m-%d %H:%M:%S"),
            "message": f"Order {order.order_number} placed successfully! Total: ₹{order.total_amount:,.2f}. Tracking ID: {shipment.tracking_number}.",
        }