import unittest
from app.db.database import SessionLocal
from app.services.cart_service import CartService
from app.services.order_service import OrderService
from app.agents.shopping_graph import build_shopping_graph
from app.agents.order_graph import build_order_graph
from app.agents.orchestrator import build_main_graph


class TestShoppingAndOrders(unittest.TestCase):

    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    # =================================================================
    # SHOPPING TESTS (1 - 15)
    # =================================================================

    def test_01_view_empty_cart(self):
        """1. View empty cart for a fresh user."""
        CartService.clear_cart(self.db, user_id=2)
        graph = build_shopping_graph(self.db)
        config = {"configurable": {"thread_id": "test-empty-cart"}}

        result = graph.invoke({"user_id": 2, "message": "Show me my cart"}, config=config)
        self.assertIn("empty", result["response"].lower())

    def test_02_view_populated_cart(self):
        """2. View populated cart for existing demo user."""
        graph = build_shopping_graph(self.db)
        config = {"configurable": {"thread_id": "test-pop-cart"}}

        result = graph.invoke({"user_id": 1, "message": "Show me my cart"}, config=config)
        self.assertIn("cart", result["response"].lower())
        self.assertIn("₹", result["response"])

    def test_03_add_valid_product_pending_confirmation(self):
        """3. Add valid product creates pending action without immediate DB mutation."""
        graph = build_shopping_graph(self.db)
        config = {"configurable": {"thread_id": "test-add-valid"}}

        cart_before = CartService.get_cart(self.db, user_id=1)
        initial_count = cart_before["item_count"]

        result = graph.invoke({"user_id": 1, "message": "Add ThinkBook Pro 8GB to my cart"}, config=config)

        # Verify pending confirmation created
        self.assertTrue(result.get("awaiting_confirmation"))
        self.assertIsNotNone(result.get("pending_action"))
        self.assertEqual(result["pending_action"]["tool"], "add_to_cart")

        # Verify DB has NOT changed yet
        cart_after = CartService.get_cart(self.db, user_id=1)
        self.assertEqual(cart_after["item_count"], initial_count)

    def test_04_add_with_quantity_greater_than_1(self):
        """4. Add with quantity > 1 parses quantity correctly."""
        graph = build_shopping_graph(self.db)
        config = {"configurable": {"thread_id": "test-add-qty-2"}}

        result = graph.invoke({"user_id": 1, "message": "Add 2 ThinkBook Pro 8GB to my cart"}, config=config)
        self.assertTrue(result.get("awaiting_confirmation"))
        self.assertEqual(result["pending_action"]["args"]["quantity"], 2)

    def test_05_product_not_found(self):
        """5. Product not found returns graceful message and no pending action."""
        graph = build_shopping_graph(self.db)
        config = {"configurable": {"thread_id": "test-not-found"}}

        result = graph.invoke({"user_id": 1, "message": "Add SuperHyperGadget999 to my cart"}, config=config)
        self.assertIn("couldn't find", result["response"].lower())
        self.assertIsNone(result.get("pending_action"))

    def test_06_multiple_product_matches_ambiguity(self):
        """6. Multiple product matches prompt disambiguation instead of guessing."""
        graph = build_shopping_graph(self.db)
        config = {"configurable": {"thread_id": "test-ambiguity"}}

        result = graph.invoke({"user_id": 1, "message": "Add ThinkBook Pro to my cart"}, config=config)
        self.assertIn("multiple", result["response"].lower())
        self.assertIsNotNone(result.get("active_options"))
        self.assertGreaterEqual(len(result["active_options"]), 2)
        self.assertIsNone(result.get("pending_action"))  # Does NOT silently guess first

    def test_07_insufficient_stock(self):
        """7. Insufficient stock is safely handled."""
        graph = build_shopping_graph(self.db)
        config = {"configurable": {"thread_id": "test-stock"}}

        result = graph.invoke({"user_id": 1, "message": "Add 9999 ThinkBook Pro 8GB to my cart"}, config=config)
        self.assertIn("stock", result["response"].lower())
        self.assertIsNone(result.get("pending_action"))

    def test_08_invalid_quantity(self):
        """8. Invalid quantity <= 0 is rejected safely."""
        graph = build_shopping_graph(self.db)
        config = {"configurable": {"thread_id": "test-invalid-qty"}}

        result = graph.invoke({"user_id": 1, "message": "Add 0 ThinkBook Pro to my cart"}, config=config)
        self.assertIn("greater than zero", result["response"].lower())
        self.assertIsNone(result.get("pending_action"))

    def test_09_10_pending_action_and_yes_confirmation(self):
        """9 & 10. Pending action created, 'yes' executes action and updates DB."""
        graph = build_shopping_graph(self.db)
        config = {"configurable": {"thread_id": "test-confirm-yes"}}

        # Turn 1: Request addition
        res1 = graph.invoke({"user_id": 1, "message": "Add 1 Galaxy Pro 128GB to my cart"}, config=config)
        self.assertTrue(res1.get("awaiting_confirmation"))

        cart_mid = CartService.get_cart(self.db, user_id=1)
        count_before = cart_mid["item_count"]

        # Turn 2: Confirm
        res2 = graph.invoke({"user_id": 1, "message": "yes"}, config=config)
        self.assertFalse(res2.get("awaiting_confirmation"))
        self.assertIsNone(res2.get("pending_action"))
        self.assertIn("added", res2["response"].lower())

        # Verify DB actually mutated
        cart_after = CartService.get_cart(self.db, user_id=1)
        self.assertEqual(cart_after["item_count"], count_before + 1)

    def test_11_no_cancels_action(self):
        """11. 'no' cancels pending action without changing database."""
        graph = build_shopping_graph(self.db)
        config = {"configurable": {"thread_id": "test-confirm-no"}}

        cart_before = CartService.get_cart(self.db, user_id=1)
        initial_count = cart_before["item_count"]

        # Turn 1: Request
        res1 = graph.invoke({"user_id": 1, "message": "Add 1 Galaxy Pro 128GB to my cart"}, config=config)
        self.assertTrue(res1.get("awaiting_confirmation"))

        # Turn 2: Cancel
        res2 = graph.invoke({"user_id": 1, "message": "no"}, config=config)
        self.assertIn("cancelled", res2["response"].lower())
        self.assertFalse(res2.get("awaiting_confirmation"))
        self.assertIsNone(res2.get("pending_action"))

        # Verify DB unchanged
        cart_after = CartService.get_cart(self.db, user_id=1)
        self.assertEqual(cart_after["item_count"], initial_count)

    def test_12_ambiguous_confirmation_asks_again(self):
        """12. Ambiguous response does not execute and asks for confirmation again."""
        graph = build_shopping_graph(self.db)
        config = {"configurable": {"thread_id": "test-confirm-ambiguous"}}

        # Turn 1: Request
        res1 = graph.invoke({"user_id": 1, "message": "Add 1 Galaxy Pro 128GB to my cart"}, config=config)
        self.assertTrue(res1.get("awaiting_confirmation"))

        # Turn 2: Ambiguous answer
        res2 = graph.invoke({"user_id": 1, "message": "Maybe tomorrow or what do you think?"}, config=config)
        self.assertIn("confirm", res2["response"].lower())
        # Still pending!
        self.assertTrue(res2.get("awaiting_confirmation"))
        self.assertIsNotNone(res2.get("pending_action"))

    def test_13_pending_action_survives_next_turn_with_thread_id(self):
        """13. Pending action survives across turns via thread_id checkpointer."""
        graph = build_shopping_graph(self.db)
        thread_id = "test-thread-persistence-99"
        config = {"configurable": {"thread_id": thread_id}}

        res1 = graph.invoke({"user_id": 1, "message": "Add 1 ThinkBook Pro 8GB to my cart"}, config=config)
        self.assertTrue(res1["awaiting_confirmation"])

        # Call on the same thread without explicit state override
        res2 = graph.invoke({"user_id": 1, "message": "yes"}, config=config)
        self.assertIn("added", res2["response"].lower())

    def test_14_update_cart_quantity(self):
        """14. Update cart quantity with confirmation flow."""
        graph = build_shopping_graph(self.db)
        config = {"configurable": {"thread_id": "test-update-qty"}}

        # Turn 1: Request update
        res1 = graph.invoke({"user_id": 1, "message": "Update quantity of ThinkBook to 2 in my cart"}, config=config)
        self.assertTrue(res1.get("awaiting_confirmation"))
        self.assertEqual(res1["pending_action"]["tool"], "update_cart_quantity")

        # Turn 2: Confirm
        res2 = graph.invoke({"user_id": 1, "message": "yes"}, config=config)
        self.assertIn("updated", res2["response"].lower())

    def test_15_remove_cart_item(self):
        """15. Remove cart item with confirmation flow."""
        graph = build_shopping_graph(self.db)
        config = {"configurable": {"thread_id": "test-remove-item"}}

        # Turn 1: Request removal
        res1 = graph.invoke({"user_id": 1, "message": "Remove Galaxy from my cart"}, config=config)
        self.assertTrue(res1.get("awaiting_confirmation"))
        self.assertEqual(res1["pending_action"]["tool"], "remove_from_cart")

        # Turn 2: Confirm
        res2 = graph.invoke({"user_id": 1, "message": "yes"}, config=config)
        self.assertIn("removed", res2["response"].lower())

    # =================================================================
    # ORDER TESTS (16 - 22)
    # =================================================================

    def test_16_retrieve_user_orders(self):
        """16. Retrieve user's orders accurately."""
        graph = build_order_graph(self.db)
        config = {"configurable": {"thread_id": "test-order-list"}}

        res = graph.invoke({"user_id": 1, "message": "Show my orders"}, config=config)
        self.assertTrue("ORD-2026-1001" in res["response"] or "ORD-2026-1002" in res["response"])

    def test_17_retrieve_order_details(self):
        """17. Retrieve specific order details."""
        graph = build_order_graph(self.db)
        config = {"configurable": {"thread_id": "test-order-details"}}

        res = graph.invoke({"user_id": 1, "message": "Show details of order ORD-2026-1001"}, config=config)
        self.assertIn("ORD-2026-1001", res["response"])
        self.assertIn("₹", res["response"])

    def test_18_retrieve_order_status(self):
        """18. Retrieve order status."""
        graph = build_order_graph(self.db)
        config = {"configurable": {"thread_id": "test-order-status"}}

        res = graph.invoke({"user_id": 1, "message": "What is the status of order ORD-2026-1001?"}, config=config)
        self.assertIn("DELIVERED", res["response"].upper())

    def test_19_retrieve_shipment_status(self):
        """19. Retrieve shipment status with carrier and tracking."""
        graph = build_order_graph(self.db)
        config = {"configurable": {"thread_id": "test-order-shipment"}}

        res = graph.invoke({"user_id": 1, "message": "Track order ORD-2026-1001"}, config=config)
        self.assertIn("BlueDart", res["response"])
        self.assertIn("BD987654321IN", res["response"])

    def test_20_invalid_order_id(self):
        """20. Invalid order ID returns clean error."""
        graph = build_order_graph(self.db)
        config = {"configurable": {"thread_id": "test-invalid-order"}}

        res = graph.invoke({"user_id": 1, "message": "Track order ORD-999999"}, config=config)
        self.assertIn("couldn't find", res["response"].lower())

    def test_21_cross_user_order_isolation_security(self):
        """21. Security check: User 1 cannot access User 2's order."""
        graph = build_order_graph(self.db)
        config = {"configurable": {"thread_id": "test-security-isolation"}}

        # ORD-2026-2001 belongs to User 2!
        res = graph.invoke({"user_id": 1, "message": "Show order ORD-2026-2001"}, config=config)
        self.assertIn("couldn't find", res["response"].lower())

    def test_22_graceful_handling_missing_shipment(self):
        """22. Graceful handling when order has no shipment dispatched yet."""
        # ORD-2026-2001 (User 2) has no shipments yet
        res = OrderService.get_shipment_status(self.db, user_id=2, order_identifier="ORD-2026-2001")
        self.assertIsNotNone(res)
        self.assertEqual(res["status"], "pending_shipment")

    # =================================================================
    # END-TO-END FLOWS (MAIN ROUTER INTEGRATION)
    # =================================================================

    def test_e2e_flow_1_view_cart(self):
        """FLOW 1: User asks 'Show me my cart' -> grounded response via main graph."""
        graph = build_main_graph(self.db)
        config = {"configurable": {"thread_id": "e2e-flow-1"}}

        res = graph.invoke({"user_id": 1, "message": "Show me my cart"}, config=config)
        self.assertEqual(res["intent"], "shopping")
        self.assertIn("cart", res["response"].lower())

    def test_e2e_flow_2_add_to_cart_confirm(self):
        """FLOW 2: Add product -> confirmation -> yes -> DB updated via main graph."""
        graph = build_main_graph(self.db)
        config = {"configurable": {"thread_id": "e2e-flow-2"}}

        # Turn 1
        res1 = graph.invoke({"user_id": 1, "message": "Add 1 ThinkBook Pro 8GB to my cart"}, config=config)
        self.assertTrue(res1.get("awaiting_confirmation"))

        # Turn 2
        res2 = graph.invoke({"user_id": 1, "message": "yes"}, config=config)
        self.assertIn("added", res2["response"].lower())
        self.assertFalse(res2.get("awaiting_confirmation"))

    def test_e2e_flow_3_add_nonexistent_product(self):
        """FLOW 3: Add product that doesn't exist -> no DB mutation."""
        graph = build_main_graph(self.db)
        config = {"configurable": {"thread_id": "e2e-flow-3"}}

        res = graph.invoke({"user_id": 1, "message": "Add QuantumFluxPhone to my cart"}, config=config)
        self.assertIn("couldn't find", res["response"].lower())
        self.assertIsNone(res.get("pending_action"))

    def test_e2e_flow_4_show_previous_orders(self):
        """FLOW 4: Show my previous orders -> grounded order history."""
        graph = build_main_graph(self.db)
        config = {"configurable": {"thread_id": "e2e-flow-4"}}

        res = graph.invoke({"user_id": 1, "message": "Show my previous orders"}, config=config)
        self.assertEqual(res["intent"], "order")
        self.assertIn("ORD-2026-", res["response"])

    def test_e2e_flow_5_where_is_order(self):
        """FLOW 5: Where is order ORD-2026-1001 -> ownership checked & tracking returned."""
        graph = build_main_graph(self.db)
        config = {"configurable": {"thread_id": "e2e-flow-5"}}

        res = graph.invoke({"user_id": 1, "message": "Where is order ORD-2026-1001?"}, config=config)
        self.assertEqual(res["intent"], "order")
        self.assertTrue("BlueDart" in res["response"] or "Delivered" in res["response"])

    def test_e2e_product_catalog_still_works(self):
        """Verify that Product Agent workflow is NOT broken by Day 3 changes."""
        graph = build_main_graph(self.db)
        config = {"configurable": {"thread_id": "e2e-product-intact"}}

        res = graph.invoke({"user_id": 1, "message": "Show me products containing Galaxy"}, config=config)
        self.assertEqual(res["intent"], "product")
        self.assertIn("galaxy", str(res["response"]).lower())

    def test_e2e_support_policy_route(self):
        """Verify support workflow routes correctly."""
        graph = build_main_graph(self.db)
        config = {"configurable": {"thread_id": "e2e-support-route"}}

        res = graph.invoke({"user_id": 1, "message": "What is your return policy?"}, config=config)
        self.assertEqual(res["intent"], "support")
        self.assertIn("return", res["response"].lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)

