from decimal import Decimal

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models.product import Category, Product, ProductVariant


def seed_products():
    db = SessionLocal()

    try:
        existing = db.scalar(select(Category).limit(1))

        if existing:
            print("Seed data already exists.")
            return

        electronics = Category(
            name="Electronics",
            slug="electronics",
            description="Electronic devices and accessories",
        )

        db.add(electronics)
        db.flush()

        laptop = Product(
            category_id=electronics.id,
            name="ThinkBook Pro",
            description="Professional productivity laptop",
            brand="Lenovo",
            rating=4.5,
            specifications={
                "processor": "Intel Core i7",
                "display": "15.6 inch",
            },
        )

        smartphone = Product(
            category_id=electronics.id,
            name="Galaxy Pro",
            description="High-performance Android smartphone",
            brand="Samsung",
            rating=4.4,
            specifications={
                "display": "6.7 inch",
                "camera": "50MP",
            },
        )

        db.add_all([laptop, smartphone])
        db.flush()

        db.add_all(
            [
                ProductVariant(
                    product_id=laptop.id,
                    sku="TBP-8-512",
                    name="8GB RAM / 512GB SSD",
                    price=Decimal("74999.00"),
                    discount=Decimal("5000.00"),
                    stock_quantity=10,
                    specifications={
                        "ram": "8GB",
                        "storage": "512GB",
                    },
                    is_active=True,
                ),
                ProductVariant(
                    product_id=laptop.id,
                    sku="TBP-16-1TB",
                    name="16GB RAM / 1TB SSD",
                    price=Decimal("89999.00"),
                    discount=Decimal("7000.00"),
                    stock_quantity=5,
                    specifications={
                        "ram": "16GB",
                        "storage": "1TB",
                    },
                    is_active=True,
                ),
                ProductVariant(
                    product_id=smartphone.id,
                    sku="SGP-128",
                    name="128GB",
                    price=Decimal("54999.00"),
                    discount=Decimal("3000.00"),
                    stock_quantity=20,
                    specifications={
                        "storage": "128GB",
                    },
                    is_active=True,
                ),
                ProductVariant(
                    product_id=smartphone.id,
                    sku="SGP-256",
                    name="256GB",
                    price=Decimal("59999.00"),
                    discount=Decimal("4000.00"),
                    stock_quantity=12,
                    specifications={
                        "storage": "256GB",
                    },
                    is_active=True,
                ),
            ]
        )

        db.commit()

        print("Seed data created successfully.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


from datetime import datetime, timedelta, timezone

from app.db.models.user import User
from app.db.models.order import Order, OrderItem, Payment, Shipment, ShipmentItem


def seed_orders():
    db = SessionLocal()

    try:
        existing_order = db.scalar(select(Order).limit(1))
        if existing_order:
            print("Order seed data already exists.")
            return

        # Ensure demo user exists
        user1 = db.scalar(select(User).where(User.id == 1))
        if not user1:
            user1 = User(
                username="demo_user",
                email="demo@example.com",
                hashed_password="demo-only",
            )
            db.add(user1)
            db.flush()

        # Ensure secondary user exists for cross-user isolation tests
        user2 = db.scalar(select(User).where(User.email == "user2@example.com"))
        if not user2:
            user2 = User(
                username="other_user",
                email="user2@example.com",
                hashed_password="demo-only",
            )
            db.add(user2)
            db.flush()

        # Retrieve product variants for order items
        laptop_variant = db.scalar(
            select(ProductVariant).where(ProductVariant.sku == "TBP-8-512")
        )
        phone_variant1 = db.scalar(
            select(ProductVariant).where(ProductVariant.sku == "SGP-128")
        )
        phone_variant2 = db.scalar(
            select(ProductVariant).where(ProductVariant.sku == "SGP-256")
        )

        if not (laptop_variant and phone_variant1 and phone_variant2):
            print("Product variants missing. Seed products first.")
            return

        now = datetime.now(timezone.utc)

        # -------------------------------------------------------------
        # Order 1 (User 1): Delivered order with shipment and payment
        # -------------------------------------------------------------
        order1 = Order(
            user_id=user1.id,
            order_number="ORD-2026-1001",
            status="delivered",
            subtotal=Decimal("74999.00"),
            discount_amount=Decimal("0.00"),
            shipping_amount=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            total_amount=Decimal("74999.00"),
            shipping_address_snapshot={
                "recipient_name": "Demo User",
                "city": "Bangalore",
                "state": "Karnataka",
                "postal_code": "560001",
                "country": "India",
            },
            created_at=now - timedelta(days=5),
        )
        db.add(order1)
        db.flush()

        item1 = OrderItem(
            order_id=order1.id,
            product_variant_id=laptop_variant.id,
            quantity=1,
            unit_price=Decimal("74999.00"),
            product_name_snapshot="ThinkBook Pro (8GB RAM / 512GB SSD)",
        )
        db.add(item1)
        db.flush()

        pay1 = Payment(
            order_id=order1.id,
            amount=Decimal("74999.00"),
            status="completed",
            payment_method="UPI",
            transaction_reference="UPI-TXN-1001",
        )
        db.add(pay1)

        ship1 = Shipment(
            order_id=order1.id,
            tracking_number="BD987654321IN",
            carrier="BlueDart",
            status="delivered",
            shipped_at=now - timedelta(days=4),
            delivered_at=now - timedelta(days=1),
        )
        db.add(ship1)
        db.flush()

        ship_item1 = ShipmentItem(
            shipment_id=ship1.id,
            order_item_id=item1.id,
            quantity=1,
        )
        db.add(ship_item1)

        # -------------------------------------------------------------
        # Order 2 (User 1): Processing order (in transit, cancellable test)
        # -------------------------------------------------------------
        order2 = Order(
            user_id=user1.id,
            order_number="ORD-2026-1002",
            status="processing",
            subtotal=Decimal("54999.00"),
            discount_amount=Decimal("0.00"),
            shipping_amount=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            total_amount=Decimal("54999.00"),
            shipping_address_snapshot={
                "recipient_name": "Demo User",
                "city": "Bangalore",
                "state": "Karnataka",
                "postal_code": "560001",
                "country": "India",
            },
            created_at=now - timedelta(days=1),
        )
        db.add(order2)
        db.flush()

        item2 = OrderItem(
            order_id=order2.id,
            product_variant_id=phone_variant1.id,
            quantity=1,
            unit_price=Decimal("54999.00"),
            product_name_snapshot="Galaxy Pro (128GB)",
        )
        db.add(item2)
        db.flush()

        pay2 = Payment(
            order_id=order2.id,
            amount=Decimal("54999.00"),
            status="completed",
            payment_method="Credit Card",
            transaction_reference="CC-TXN-1002",
        )
        db.add(pay2)

        ship2 = Shipment(
            order_id=order2.id,
            tracking_number="DL123456789IN",
            carrier="Delhivery",
            status="in_transit",
            shipped_at=now - timedelta(hours=12),
            estimated_delivery_at=now + timedelta(days=2),
        )
        db.add(ship2)
        db.flush()

        ship_item2 = ShipmentItem(
            shipment_id=ship2.id,
            order_item_id=item2.id,
            quantity=1,
        )
        db.add(ship_item2)

        # -------------------------------------------------------------
        # Order 3 (User 2): Order belonging to User 2 for security tests
        # -------------------------------------------------------------
        order3 = Order(
            user_id=user2.id,
            order_number="ORD-2026-2001",
            status="placed",
            subtotal=Decimal("59999.00"),
            discount_amount=Decimal("0.00"),
            shipping_amount=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            total_amount=Decimal("59999.00"),
            shipping_address_snapshot={
                "recipient_name": "Other User",
                "city": "Mumbai",
                "state": "Maharashtra",
                "postal_code": "400001",
                "country": "India",
            },
            created_at=now - timedelta(hours=2),
        )
        db.add(order3)
        db.flush()

        item3 = OrderItem(
            order_id=order3.id,
            product_variant_id=phone_variant2.id,
            quantity=1,
            unit_price=Decimal("59999.00"),
            product_name_snapshot="Galaxy Pro (256GB)",
        )
        db.add(item3)

        db.commit()
        print("Order seed data created successfully.")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


import hashlib
from app.db.models.support import ProductDocument, DocumentChunk


def seed_support_documents():
    db = SessionLocal()

    try:
        existing_doc = db.scalar(select(ProductDocument).limit(1))
        if existing_doc:
            print("Support documents seed data already exists.")
            return

        laptop = db.scalar(select(Product).where(Product.name == "ThinkBook Pro"))
        smartphone = db.scalar(select(Product).where(Product.name == "Galaxy Pro"))

        if not (laptop and smartphone):
            print("Products missing. Seed products first.")
            return

        docs_data = [
            {
                "product_id": laptop.id,
                "file_name": "thinkbook_pro_manual.md",
                "document_type": "manual",
                "version": "1.0",
                "file_path": "/docs/thinkbook_pro_manual.md",
                "chunks": [
                    {
                        "chunk_index": 0,
                        "content": "ThinkBook Pro Battery & Power Optimization: To optimize battery life, enable Battery Saver mode in system settings. If the laptop does not charge, ensure you are using the original 65W USB-C charger. For thermal throttling or fan noise, ensure vents are unobstructed and update BIOS to version 1.12.",
                        "chunk_metadata": {"topic": "battery_and_power", "product": "ThinkBook Pro"},
                    },
                    {
                        "chunk_index": 1,
                        "content": "ThinkBook Pro Display & Port Specifications: Features a 15.6-inch Full HD anti-glare IPS display. Includes 2x USB-C ports with DisplayPort Alt Mode and Power Delivery, 2x USB-A 3.2 ports, and 1x HDMI 2.0 port supporting external 4K monitors.",
                        "chunk_metadata": {"topic": "display_and_ports", "product": "ThinkBook Pro"},
                    },
                    {
                        "chunk_index": 2,
                        "content": "ThinkBook Pro Warranty & Repair Coverage: Covered by a 1-year comprehensive manufacturer warranty covering motherboard, processor, RAM, and display defects. Does not cover liquid damage or accidental physical drops. Free doorstep pickup and repair across India.",
                        "chunk_metadata": {"topic": "warranty", "product": "ThinkBook Pro"},
                    },
                ],
            },
            {
                "product_id": smartphone.id,
                "file_name": "galaxy_pro_manual.md",
                "document_type": "manual",
                "version": "1.0",
                "file_path": "/docs/galaxy_pro_manual.md",
                "chunks": [
                    {
                        "chunk_index": 0,
                        "content": "Galaxy Pro Screen & Touch Troubleshooting: If the 6.7-inch AMOLED touchscreen becomes unresponsive, perform a soft reset by holding Power + Volume Down for 10 seconds. Ensure screen protector does not interfere with the in-display ultrasonic fingerprint sensor.",
                        "chunk_metadata": {"topic": "screen_touch", "product": "Galaxy Pro"},
                    },
                    {
                        "chunk_index": 1,
                        "content": "Galaxy Pro Camera & Battery Diagnostics: Features a 50MP primary sensor with OIS. If camera app crashes, clear camera cache via Settings > Apps > Camera > Storage > Clear Cache. Fast charging requires a 45W PPS charger.",
                        "chunk_metadata": {"topic": "camera_charging", "product": "Galaxy Pro"},
                    },
                    {
                        "chunk_index": 2,
                        "content": "Galaxy Pro Warranty & Accidental Protection: 1-year brand warranty on hardware and 6 months on supplied inbox accessories. Screen replacement is discounted within the first 6 months of purchase.",
                        "chunk_metadata": {"topic": "warranty", "product": "Galaxy Pro"},
                    },
                ],
            },
            {
                "product_id": laptop.id,
                "file_name": "returns_and_refunds_policy.md",
                "document_type": "policy",
                "version": "2.0",
                "file_path": "/policies/returns_and_refunds.md",
                "chunks": [
                    {
                        "chunk_index": 0,
                        "content": "Return & Replacement Window: Customers can request a return or replacement within 7 calendar days of delivery for eligible electronic items. The product must be in its original packaging with all tags, serial numbers, manuals, and accessories intact. Opened items must be in undamaged condition.",
                        "chunk_metadata": {"topic": "return_window", "category": "policy"},
                    },
                    {
                        "chunk_index": 1,
                        "content": "Refund Process & Timelines: Once a return is approved and the item is inspected, refunds are credited back to the original payment method (UPI, Net Banking, Credit/Debit card) within 5 to 7 business days. For cash on delivery orders, refunds are issued via NEFT bank transfer.",
                        "chunk_metadata": {"topic": "refund_timeline", "category": "policy"},
                    },
                    {
                        "chunk_index": 2,
                        "content": "Order Cancellation Policy: Orders can be cancelled free of charge at any time before the order has been shipped or marked out for delivery. Once shipped or delivered, orders cannot be cancelled directly; customers must instead request a return after delivery.",
                        "chunk_metadata": {"topic": "cancellation_policy", "category": "policy"},
                    },
                ],
            },
            {
                "product_id": smartphone.id,
                "file_name": "shipping_and_escalation_policy.md",
                "document_type": "policy",
                "version": "2.0",
                "file_path": "/policies/shipping_and_escalation.md",
                "chunks": [
                    {
                        "chunk_index": 0,
                        "content": "Shipping Fees & Delivery Timelines: Standard delivery is free for all orders above ₹499. Orders are processed within 24 hours and delivered within 2 to 4 business days via our courier partners (BlueDart, Delhivery, Shadowfax). Tracking numbers are provided via email and SMS.",
                        "chunk_metadata": {"topic": "shipping_delivery", "category": "policy"},
                    },
                    {
                        "chunk_index": 1,
                        "content": "Damaged, Wrong, or Missing Items: If an item arrives damaged, defective, or different from what was ordered, please report it within 48 hours of delivery. Include photos of the packaging and damage. We will arrange immediate reverse pickup and replacement or full refund.",
                        "chunk_metadata": {"topic": "damaged_missing_goods", "category": "policy"},
                    },
                    {
                        "chunk_index": 2,
                        "content": "Human Support Escalation: If an issue cannot be resolved through automated assistance, or involves damaged goods on arrival, payment disputes, or custom exceptions, our AI will escalate the case to a human support specialist. A ticket reference (e.g., TICKET-2026-XXXX) will be generated, and a representative will follow up within 24 business hours.",
                        "chunk_metadata": {"topic": "support_escalation", "category": "policy"},
                    },
                ],
            },
        ]

        for d in docs_data:
            doc = ProductDocument(
                product_id=d["product_id"],
                file_name=d["file_name"],
                document_type=d["document_type"],
                version=d["version"],
                file_path=d["file_path"],
            )
            db.add(doc)
            db.flush()

            for c in d["chunks"]:
                content_hash = hashlib.sha256(c["content"].encode()).hexdigest()
                chunk = DocumentChunk(
                    document_id=doc.id,
                    chunk_index=c["chunk_index"],
                    content=c["content"],
                    chunk_metadata=c["chunk_metadata"],
                    content_hash=content_hash,
                )
                db.add(chunk)

        db.commit()
        print("Support documents seed data created successfully.")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_products()
    seed_orders()
    seed_support_documents()