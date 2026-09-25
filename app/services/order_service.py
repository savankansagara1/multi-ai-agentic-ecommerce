import re
from typing import Any
from sqlalchemy import select, or_
from sqlalchemy.orm import Session, selectinload

from app.db.models.order import Order, OrderItem, Payment, Shipment
from app.db.models.support import AuditLog
from app.db.models.support import AuditLog, Return, ReturnItem, Refund


class OrderService:

    @staticmethod
    def _find_user_order(
        db: Session,
        user_id: int,
        order_identifier: str | int,
    ) -> Order | None:
        """Helper to find an order strictly scoped to the authenticated user.
        
        Security rule: Access must always be scoped by user_id. Even if an order
        with the requested ID exists in the database, if it belongs to another user,
        this returns None so we never leak existence or data of other users' orders.
        """
        clean_identifier = str(order_identifier).strip()
        # Clean common prefixes like '#', 'order #', etc.
        clean_identifier = re.sub(r"^(order\s*#?|#)", "", clean_identifier, flags=re.IGNORECASE).strip()

        conditions = [Order.order_number.ilike(f"%{clean_identifier}%")]
        if clean_identifier.isdigit():
            conditions.append(Order.id == int(clean_identifier))

        stmt = (
            select(Order)
            .options(
                selectinload(Order.items),
                selectinload(Order.shipments),
                selectinload(Order.payments),
                selectinload(Order.returns),
            )
            .where(
                Order.user_id == user_id,
                or_(*conditions),
            )
        )

        return db.scalar(stmt)

    @staticmethod
    def get_user_orders(
        db: Session,
        user_id: int,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Retrieve recent orders for the specified user."""
        stmt = (
            select(Order)
            .options(
                selectinload(Order.items),
                selectinload(Order.shipments),
            )
            .where(Order.user_id == user_id)
            .order_by(Order.created_at.desc())
            .limit(limit)
        )

        orders = db.scalars(stmt).all()
        results = []

        for order in orders:
            items_summary = ", ".join(
                f"{item.product_name_snapshot} (x{item.quantity})"
                for item in order.items
            )
            latest_shipment = order.shipments[-1] if order.shipments else None

            results.append({
                "order_id": order.id,
                "order_number": order.order_number,
                "status": order.status,
                "total_amount": float(order.total_amount),
                "item_count": sum(i.quantity for i in order.items),
                "items_summary": items_summary,
                "shipment_status": latest_shipment.status if latest_shipment else "not_shipped",
                "created_at": order.created_at.strftime("%Y-%m-%d %H:%M:%S") if order.created_at else "",
            })

        return results

    @staticmethod
    def get_order_details(
        db: Session,
        user_id: int,
        order_identifier: str | int,
    ) -> dict[str, Any] | None:
        """Retrieve full details of an order, strictly scoped to user_id."""
        order = OrderService._find_user_order(db, user_id, order_identifier)
        if not order:
            return None

        items = [
            {
                "item_id": item.id,
                "product_name": item.product_name_snapshot,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price),
                "total_price": float(item.unit_price * item.quantity),
            }
            for item in order.items
        ]

        payments = [
            {
                "payment_id": p.id,
                "amount": float(p.amount),
                "status": p.status,
                "payment_method": p.payment_method,
                "transaction_reference": p.transaction_reference,
            }
            for p in order.payments
        ]

        shipments = [
            {
                "shipment_id": s.id,
                "carrier": s.carrier,
                "tracking_number": s.tracking_number,
                "status": s.status,
                "shipped_at": s.shipped_at.strftime("%Y-%m-%d %H:%M:%S") if s.shipped_at else None,
                "estimated_delivery_at": s.estimated_delivery_at.strftime("%Y-%m-%d %H:%M:%S") if s.estimated_delivery_at else None,
                "delivered_at": s.delivered_at.strftime("%Y-%m-%d %H:%M:%S") if s.delivered_at else None,
            }
            for s in order.shipments
        ]

        return {
            "order_id": order.id,
            "order_number": order.order_number,
            "status": order.status,
            "subtotal": float(order.subtotal),
            "discount_amount": float(order.discount_amount),
            "shipping_amount": float(order.shipping_amount),
            "tax_amount": float(order.tax_amount),
            "total_amount": float(order.total_amount),
            "shipping_address": order.shipping_address_snapshot,
            "created_at": order.created_at.strftime("%Y-%m-%d %H:%M:%S") if order.created_at else "",
            "items": items,
            "payments": payments,
            "shipments": shipments,
        }

    @staticmethod
    def get_order_status(
        db: Session,
        user_id: int,
        order_identifier: str | int,
    ) -> dict[str, Any] | None:
        """Retrieve status of an order, strictly scoped to user_id."""
        order = OrderService._find_user_order(db, user_id, order_identifier)
        if not order:
            return None

        latest_shipment = order.shipments[-1] if order.shipments else None

        return {
            "order_number": order.order_number,
            "status": order.status,
            "total_amount": float(order.total_amount),
            "item_count": sum(i.quantity for i in order.items),
            "shipment_status": latest_shipment.status if latest_shipment else "no_shipment_yet",
            "carrier": latest_shipment.carrier if latest_shipment else None,
            "tracking_number": latest_shipment.tracking_number if latest_shipment else None,
            "created_at": order.created_at.strftime("%Y-%m-%d %H:%M:%S") if order.created_at else "",
        }

    @staticmethod
    def get_shipment_status(
        db: Session,
        user_id: int,
        order_identifier: str | int,
    ) -> dict[str, Any] | None:
        """Retrieve tracking and delivery status for an order."""
        order = OrderService._find_user_order(db, user_id, order_identifier)
        if not order:
            return None

        if not order.shipments:
            return {
                "order_number": order.order_number,
                "status": "pending_shipment",
                "message": f"Order {order.order_number} has not been dispatched yet.",
            }

        shipment = order.shipments[-1]
        return {
            "order_number": order.order_number,
            "carrier": shipment.carrier,
            "tracking_number": shipment.tracking_number,
            "status": shipment.status,
            "shipped_at": shipment.shipped_at.strftime("%Y-%m-%d %H:%M:%S") if shipment.shipped_at else None,
            "estimated_delivery_at": shipment.estimated_delivery_at.strftime("%Y-%m-%d %H:%M:%S") if shipment.estimated_delivery_at else None,
            "delivered_at": shipment.delivered_at.strftime("%Y-%m-%d %H:%M:%S") if shipment.delivered_at else None,
        }

    @staticmethod
    def cancel_order(
        db: Session,
        user_id: int,
        order_identifier: str | int,
        reason: str = "Customer requested cancellation",
    ) -> dict[str, Any]:
        """Cancel an order with business rule validation and audit logging."""
        order = OrderService._find_user_order(db, user_id, order_identifier)
        if not order:
            raise ValueError(
                "Order not found or does not belong to your account."
            )

        if order.status in ["cancelled", "canceled"]:
            raise ValueError(f"Order {order.order_number} is already cancelled.")

        if order.status in ["shipped", "delivered"]:
            raise ValueError(
                f"Order {order.order_number} cannot be cancelled because it is already {order.status}. "
                "You may request a return once it is delivered."
            )

        # Allow cancellation for pending, placed, processing
        old_status = order.status
        order.status = "cancelled"

        # Record audit log for compliance and trace
        audit = AuditLog(
            user_id=user_id,
            action="CANCEL_ORDER",
            entity_type="order",
            entity_id=order.id,
            old_value={"status": old_status},
            new_value={"status": "cancelled", "reason": reason},
        )
        db.add(audit)

        db.commit()
        db.refresh(order)

        return {
            "order_id": order.id,
            "order_number": order.order_number,
            "status": "cancelled",
            "message": f"Order {order.order_number} has been cancelled successfully.",
        }

    @staticmethod
    def request_return(
        db: Session,
        user_id: int,
        order_identifier: str | int,
        reason: str = "Customer requested return",
    ) -> dict[str, Any]:
        """Request a return and refund for a delivered order within the 7-day window."""
        import uuid
        from datetime import datetime, timezone, timedelta

        order = OrderService._find_user_order(db, user_id, order_identifier)
        if not order:
            raise ValueError("Order not found or does not belong to your account.")

        if order.status != "delivered":
            raise ValueError(
                f"Order {order.order_number} cannot be returned because its status is '{order.status}'. "
                "Returns are only permitted for delivered orders."
            )

        # Check return window: 7 days from delivery (or order creation if delivery timestamp not recorded)
        latest_shipment = order.shipments[-1] if order.shipments else None
        delivery_time = (latest_shipment.delivered_at if latest_shipment and latest_shipment.delivered_at else order.created_at)
        if delivery_time.tzinfo is None:
            delivery_time = delivery_time.replace(tzinfo=timezone.utc)
        
        now = datetime.now(timezone.utc)
        if now - delivery_time > timedelta(days=7):
            raise ValueError(
                f"The return window for order {order.order_number} has expired. "
                "Returns must be requested within 7 calendar days of delivery."
            )

        # Check if already returned or requested
        for existing_return in order.returns:
            if existing_return.status in ["requested", "approved", "completed"]:
                raise ValueError(
                    f"A return request has already been submitted for order {order.order_number} (Status: {existing_return.status})."
                )

        # Create Return record
        ret = Return(
            order_id=order.id,
            user_id=user_id,
            status="requested",
            reason=reason,
        )
        db.add(ret)
        db.flush()

        # Add return items
        for item in order.items:
            ret_item = ReturnItem(
                return_id=ret.id,
                order_item_id=item.id,
                quantity=item.quantity,
                reason=reason,
                resolution="refund",
            )
            db.add(ret_item)

        # Create Refund record
        refund = Refund(
            return_id=ret.id,
            amount=order.total_amount,
            status="pending",
            transaction_reference=f"REF-{uuid.uuid4().hex[:8].upper()}",
        )
        db.add(refund)

        # Audit log
        audit = AuditLog(
            user_id=user_id,
            action="REQUEST_RETURN",
            entity_type="return",
            entity_id=ret.id,
            old_value=None,
            new_value={
                "order_number": order.order_number,
                "reason": reason,
                "refund_amount": float(order.total_amount),
            },
        )
        db.add(audit)

        db.commit()
        db.refresh(ret)

        return {
            "return_id": ret.id,
            "order_number": order.order_number,
            "status": "requested",
            "refund_amount": float(order.total_amount),
            "reason": reason,
            "message": f"Return request for order {order.order_number} has been submitted successfully. A refund of ₹{order.total_amount:,.2f} will be processed within 5-7 business days upon inspection.",
        }

