from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.services.order_service import OrderService


def create_order_tools(db: Session):

    @tool
    def get_user_orders(
        user_id: int,
        limit: int = 5,
    ):
        """Retrieve the recent orders for the authenticated user.

        Use this when the user asks to see their past orders,
        order history, or recent purchases.
        """
        return OrderService.get_user_orders(
            db=db,
            user_id=user_id,
            limit=limit,
        )

    @tool
    def get_order_details(
        user_id: int,
        order_identifier: str,
    ):
        """Retrieve detailed information about a specific order for the user.

        Includes items, quantities, pricing breakdown, payment method,
        shipping address, and delivery tracking.
        Access is strictly scoped to the authenticated user.
        """
        return OrderService.get_order_details(
            db=db,
            user_id=user_id,
            order_identifier=order_identifier,
        )

    @tool
    def get_order_status(
        user_id: int,
        order_identifier: str,
    ):
        """Check the status of an existing order for the user.

        Returns order status (e.g. processing, shipped, delivered, cancelled)
        and shipment overview.
        """
        return OrderService.get_order_status(
            db=db,
            user_id=user_id,
            order_identifier=order_identifier,
        )

    @tool
    def get_shipment_status(
        user_id: int,
        order_identifier: str,
    ):
        """Track shipment and delivery status for an order.

        Returns carrier name, tracking number, shipment status,
        and estimated/actual delivery timestamps.
        """
        return OrderService.get_shipment_status(
            db=db,
            user_id=user_id,
            order_identifier=order_identifier,
        )

    @tool
    def cancel_order(
        user_id: int,
        order_identifier: str,
        reason: str = "Customer requested cancellation",
    ):
        """Cancel an eligible order for the user.

        Use this ONLY after the user has explicitly confirmed cancellation.
        Orders that are already shipped or delivered cannot be cancelled.
        """
        return OrderService.cancel_order(
            db=db,
            user_id=user_id,
            order_identifier=order_identifier,
            reason=reason,
        )

    @tool
    def request_return(
        user_id: int,
        order_identifier: str,
        reason: str = "Customer requested return",
    ):
        """Request a return and refund for an eligible delivered order.

        Use this ONLY after the user has explicitly confirmed the return request.
        Orders must be delivered and within the 7-day return window.
        """
        return OrderService.request_return(
            db=db,
            user_id=user_id,
            order_identifier=order_identifier,
            reason=reason,
        )

    return {
        "get_user_orders": get_user_orders,
        "get_order_details": get_order_details,
        "get_order_status": get_order_status,
        "get_shipment_status": get_shipment_status,
        "cancel_order": cancel_order,
        "request_return": request_return,
    }

