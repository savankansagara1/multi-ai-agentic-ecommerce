import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi.testclient import TestClient

from app.db.database import SessionLocal
from app.db.models.order import Order, OrderItem, Payment, Shipment
from app.db.models.support import Return, Refund, ProductDocument, DocumentChunk, AuditLog
from app.db.models.product import ProductVariant
from app.services.cart_service import CartService
from app.services.order_service import OrderService
from app.services.support_service import SupportService
from app.agents.support_graph import build_support_graph
from app.agents.shopping_graph import build_shopping_graph
from app.agents.order_graph import build_order_graph
from app.agents.orchestrator import build_main_graph
from app.agents.router import detect_intents
from app.main import app


class TestSupportAndAPI(unittest.TestCase):

    def setUp(self):
        self.db = SessionLocal()
        self.client = TestClient(app)

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    # =================================================================
    # 1. KNOWLEDGE BASE RAG & ESCALATION SERVICE TESTS
    # =================================================================

    def test_01_support_knowledge_base_search(self):
        """1. RAG search retrieves grounded policy chunks from database."""
        results = SupportService.search_knowledge_base(self.db, "return window and refund timeline")
        self.assertGreater(len(results), 0)
        top = results[0]
        self.assertIn("content", top)
        self.assertIn("return", top["content"].lower())

    def test_02_support_troubleshooting_search(self):
        """2. RAG search retrieves device troubleshooting instructions."""
        results = SupportService.search_knowledge_base(self.db, "ThinkBook battery optimization")
        self.assertGreater(len(results), 0)
        found = any("battery" in r["content"].lower() for r in results)
        self.assertTrue(found)

    def test_03_support_escalate_to_human(self):
        """3. Escalation generates a unique ticket ID and creates an audit log."""
        ticket = SupportService.escalate_to_human(
            db=self.db,
            user_id=1,
            issue_description="Package arrived completely crushed and laptop screen is broken",
            reason="Damaged goods on arrival",
        )
        self.assertTrue(ticket["ticket_id"].startswith("TICKET-2026-"))
        self.assertEqual(ticket["status"], "escalated")

        # Verify audit log
        audit = self.db.query(AuditLog).filter(
            AuditLog.action == "ESCALATE_TO_HUMAN"
        ).order_by(AuditLog.id.desc()).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.new_value["ticket_id"], ticket["ticket_id"])

    def test_04_support_graph_grounded_response(self):
        """4. Support Graph responds to policy inquiries with grounded content."""
        graph = build_support_graph(self.db)
        res = graph.invoke({
            "user_id": 1,
            "message": "What is the return policy?",
        })
        self.assertIn("return", res["response"].lower())

    def test_05_support_graph_escalation_flow(self):
        """5. Support Graph automatically triggers escalation on explicit request."""
        graph = build_support_graph(self.db)
        res = graph.invoke({
            "user_id": 1,
            "message": "I want to speak with a human support agent about my order dispute",
        })
        self.assertIn("TICKET-2026-", res["response"])
        self.assertIn("Escalated", res["response"])

    # =================================================================
    # 2. CHECKOUT & ATOMIC INVENTORY DEDUCTION TESTS
    # =================================================================

    def test_06_cart_service_checkout_success(self):
        """6. CartService.checkout decrements stock, creates order & payment, and empties cart."""
        # Use user 2 to avoid altering user 1 baseline state
        CartService.clear_cart(self.db, user_id=2)
        variant = self.db.query(ProductVariant).filter(ProductVariant.sku == "TBP-8-512").first()
        stock_before = variant.stock_quantity

        # Add 1 unit
        CartService.add_item(self.db, user_id=2, product_variant_id=variant.id, quantity=1)

        # Checkout
        order_info = CartService.checkout(self.db, user_id=2)

        # Assertions
        self.assertTrue(order_info["order_number"].startswith("ORD-2026-"))
        self.assertEqual(order_info["status"], "placed")
        self.assertTrue(order_info["tracking_number"].startswith("TRK"))

        # Verify stock decremented
        self.db.refresh(variant)
        self.assertEqual(variant.stock_quantity, stock_before - 1)

        # Verify cart emptied
        cart_after = CartService.get_cart(self.db, user_id=2)
        self.assertEqual(cart_after["item_count"], 0)

        # Verify order in DB
        db_order = self.db.query(Order).filter(Order.order_number == order_info["order_number"]).first()
        self.assertIsNotNone(db_order)
        self.assertEqual(len(db_order.items), 1)
        self.assertEqual(len(db_order.payments), 1)
        self.assertEqual(len(db_order.shipments), 1)

    def test_07_cart_checkout_empty_cart_fails(self):
        """7. Checkout fails gracefully when cart is empty."""
        CartService.clear_cart(self.db, user_id=2)
        with self.assertRaises(ValueError) as ctx:
            CartService.checkout(self.db, user_id=2)
        self.assertIn("empty", str(ctx.exception).lower())

    def test_08_agent_checkout_two_turn_confirmation(self):
        """8. Shopping Graph requires explicit confirmation before placing order."""
        graph = build_shopping_graph(self.db)
        config = {"configurable": {"thread_id": "test-checkout-thread"}}

        # Ensure user 2 has an item in cart
        CartService.clear_cart(self.db, user_id=2)
        variant = self.db.query(ProductVariant).first()
        CartService.add_item(self.db, user_id=2, product_variant_id=variant.id, quantity=1)

        # Turn 1: Initiate checkout
        turn1 = graph.invoke({"user_id": 2, "message": "Place order for my cart"}, config=config)
        self.assertTrue(turn1.get("awaiting_confirmation"))
        self.assertEqual(turn1.get("pending_action", {}).get("tool"), "checkout")
        self.assertIn("proceed", turn1["response"].lower())

        # Cart should NOT be cleared yet
        cart_mid = CartService.get_cart(self.db, user_id=2)
        self.assertEqual(cart_mid["item_count"], 1)

        # Turn 2: Positive confirmation
        turn2 = graph.invoke({"user_id": 2, "message": "yes, place the order"}, config=config)
        self.assertFalse(turn2.get("awaiting_confirmation"))
        self.assertIn("placed successfully", turn2["response"].lower())

        # Cart should now be empty
        cart_end = CartService.get_cart(self.db, user_id=2)
        self.assertEqual(cart_end["item_count"], 0)

    # =================================================================
    # 3. ORDER RETURN & REFUND TESTS
    # =================================================================

    def test_09_request_return_delivered_order_success(self):
        """9. Requesting return on delivered order within 7 days creates Return and Refund."""
        # Find delivered order (ORD-2026-1001)
        order = self.db.query(Order).filter(Order.order_number == "ORD-2026-1001").first()
        self.assertIsNotNone(order)

        # Clean existing returns if re-running test
        for r in list(order.returns):
            for item in list(r.items):
                self.db.delete(item)
            refunds = self.db.query(Refund).filter(Refund.return_id == r.id).all()
            for ref in refunds:
                self.db.delete(ref)
            self.db.delete(r)
        self.db.commit()

        result = OrderService.request_return(
            db=self.db,
            user_id=1,
            order_identifier="ORD-2026-1001",
            reason="Item had dead pixels on screen",
        )
        self.assertEqual(result["status"], "requested")
        self.assertEqual(result["order_number"], "ORD-2026-1001")
        self.assertGreater(result["refund_amount"], 0)

        # Verify Return record in DB
        ret = self.db.query(Return).filter(Return.id == result["return_id"]).first()
        self.assertIsNotNone(ret)
        self.assertEqual(ret.status, "requested")

        # Verify Refund record
        ref = self.db.query(Refund).filter(Refund.return_id == ret.id).first()
        self.assertIsNotNone(ref)
        self.assertEqual(ref.status, "pending")

    def test_10_request_return_non_delivered_order_fails(self):
        """10. Return request rejected if order status is processing or placed."""
        with self.assertRaises(ValueError) as ctx:
            OrderService.request_return(
                db=self.db,
                user_id=1,
                order_identifier="ORD-2026-1002",  # Status is processing
                reason="Changed mind",
            )
        self.assertIn("delivered", str(ctx.exception).lower())

    def test_11_request_return_expired_window_fails(self):
        """11. Return request rejected if delivered more than 7 days ago."""
        # Create a mock delivered order from 10 days ago
        now = datetime.now(timezone.utc)
        old_order = Order(
            user_id=1,
            order_number="ORD-2026-EXPIRED",
            status="delivered",
            subtotal=Decimal("1000.00"),
            discount_amount=Decimal("0.00"),
            shipping_amount=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            total_amount=Decimal("1000.00"),
            shipping_address_snapshot={"city": "Bangalore"},
            created_at=now - timedelta(days=12),
        )
        self.db.add(old_order)
        self.db.flush()

        old_shipment = Shipment(
            order_id=old_order.id,
            tracking_number="TRK-OLD-123",
            carrier="Delhivery",
            status="delivered",
            delivered_at=now - timedelta(days=10),
            created_at=now - timedelta(days=12),
        )
        self.db.add(old_shipment)
        self.db.commit()

        with self.assertRaises(ValueError) as ctx:
            OrderService.request_return(
                db=self.db,
                user_id=1,
                order_identifier=old_order.order_number,
                reason="Too late",
            )
        self.assertIn("expired", str(ctx.exception).lower())

    def test_12_agent_return_two_turn_confirmation(self):
        """12. Order Agent confirms with user before submitting return request."""
        graph = build_order_graph(self.db)
        config = {"configurable": {"thread_id": "test-return-thread"}}

        # Clean returns on ORD-2026-1001 for test isolation
        order = self.db.query(Order).filter(Order.order_number == "ORD-2026-1001").first()
        for r in list(order.returns):
            for item in list(r.items):
                self.db.delete(item)
            refunds = self.db.query(Refund).filter(Refund.return_id == r.id).all()
            for ref in refunds:
                self.db.delete(ref)
            self.db.delete(r)
        self.db.commit()

        # Turn 1: Request return
        turn1 = graph.invoke({
            "user_id": 1,
            "message": "I want to return order ORD-2026-1001 because the display is defective",
        }, config=config)

        self.assertTrue(turn1.get("awaiting_confirmation"))
        self.assertEqual(turn1.get("pending_action", {}).get("tool"), "request_return")
        self.assertIn("yes", turn1["response"].lower())

        # Turn 2: Positive confirmation
        turn2 = graph.invoke({
            "user_id": 1,
            "message": "yes, confirm return",
        }, config=config)

        self.assertFalse(turn2.get("awaiting_confirmation"))
        self.assertIn("submitted successfully", turn2["response"].lower())

    # =================================================================
    # 4. MULTI-INTENT ORCHESTRATION TESTS
    # =================================================================

    def test_13_detect_compound_intents(self):
        """13. Router correctly detects multiple intents in compound query."""
        intents = detect_intents("Show me my cart and what is your return policy?")
        self.assertIn("shopping", intents)
        self.assertIn("support", intents)
        self.assertGreaterEqual(len(intents), 2)

    def test_14_main_graph_multi_intent_execution(self):
        """14. Main graph orchestrates multiple domains and presents unified response."""
        graph = build_main_graph(self.db, with_checkpointer=False)
        result = graph.invoke({
            "user_id": 1,
            "message": "Show me my cart and what is your return policy?",
        })
        response = result.get("response", "")
        # Check both domain sections present in response
        self.assertIn("Shopping Cart", response)
        self.assertIn("Customer Support", response)

    # =================================================================
    # 5. FASTAPI REST API TESTS
    # =================================================================

    def test_15_fastapi_products_endpoint(self):
        """15. GET /api/products/ returns full product list."""
        res = self.client.get("/api/products/")
        self.assertEqual(res.status_code, 200)
        products = res.json()
        self.assertGreaterEqual(len(products), 2)

    def test_16_fastapi_cart_lifecycle(self):
        """16. Cart REST endpoints add, update, and read cart."""
        # 1. View cart
        res = self.client.get("/api/cart/?user_id=1")
        self.assertEqual(res.status_code, 200)
        self.assertIn("items", res.json())

        # 2. Add item to user 2's cart
        res = self.client.post("/api/cart/items", json={
            "variant_id": 1,
            "quantity": 2,
            "user_id": 2,
        })
        self.assertEqual(res.status_code, 200)

        # 3. Update quantity
        res = self.client.put("/api/cart/items/1", json={
            "quantity": 1,
            "user_id": 2,
        })
        self.assertEqual(res.status_code, 200)

    def test_17_fastapi_orders_endpoints(self):
        """17. Orders REST endpoints list orders and track shipments."""
        res = self.client.get("/api/orders/?user_id=1")
        self.assertEqual(res.status_code, 200)
        orders = res.json()
        self.assertGreaterEqual(len(orders), 1)

        # Tracking endpoint
        ord_num = orders[0]["order_number"]
        res_track = self.client.get(f"/api/orders/{ord_num}/tracking?user_id=1")
        self.assertEqual(res_track.status_code, 200)
        self.assertIn("carrier", res_track.json())

    def test_18_fastapi_support_faqs_and_escalate(self):
        """18. Support REST endpoints serve FAQs and create escalation tickets."""
        # FAQs
        res_faqs = self.client.get("/api/support/faqs")
        self.assertEqual(res_faqs.status_code, 200)
        self.assertGreater(len(res_faqs.json()), 0)

        # Escalate
        res_esc = self.client.post("/api/support/escalate", json={
            "user_id": 1,
            "issue_description": "Delayed delivery and unreachable courier",
            "reason": "Logistics issue",
        })
        self.assertEqual(res_esc.status_code, 200)
        self.assertTrue(res_esc.json()["ticket_id"].startswith("TICKET-2026-"))

    def test_19_fastapi_chat_conversational_endpoint(self):
        """19. POST /api/chat/ invokes LangGraph and returns structured response."""
        res = self.client.post("/api/chat/", json={
            "message": "What is the return policy?",
            "user_id": 1,
            "thread_id": "test_api_conv_thread",
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("response", data)
        self.assertIn("return", data["response"].lower())

    def test_20_fastapi_home_ui_served(self):
        """20. GET / serves the Single Page Web Application UI."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("<!DOCTYPE html>", res.text)
        self.assertIn("Multi-AI Agentic E-Commerce System", res.text)


if __name__ == "__main__":
    unittest.main()

