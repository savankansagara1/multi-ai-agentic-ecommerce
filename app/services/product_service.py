import re
from decimal import Decimal

from sqlalchemy import select, or_
from sqlalchemy.orm import Session, selectinload

from app.db.models.product import Product, ProductVariant


class ProductService:
    @staticmethod
    def get_product(db: Session, product_id: int) -> Product | None:
        statement = (
            select(Product)
            .options(selectinload(Product.variants))
            .where(Product.id == product_id)
        )
        return db.scalar(statement)

    @staticmethod
    def search_products(
        db: Session,
        query: str | None = None,
        limit: int = 10,
    ) -> list[Product]:
        statement = select(Product).options(selectinload(Product.variants)).limit(limit)
        if query:
            statement = statement.where(Product.name.ilike(f"%{query}%"))
        return list(db.scalars(statement).all())

    @staticmethod
    def list_catalog(db: Session) -> list[dict]:
        """List every active product variant, including those currently out of stock."""
        statement = (
            select(Product)
            .join(ProductVariant, ProductVariant.product_id == Product.id)
            .options(selectinload(Product.variants))
            .where(ProductVariant.is_active.is_(True))
            .distinct()
            .order_by(Product.name)
        )
        products = db.scalars(statement).unique().all()
        results = []
        for product in products:
            for variant in product.variants:
                if not variant.is_active:
                    continue
                results.append({
                    "product_id": product.id,
                    "product_name": product.name,
                    "brand": product.brand,
                    "variant_name": variant.name,
                    "sku": variant.sku,
                    "price": float(variant.price),
                    "stock_quantity": variant.stock_quantity,
                })
        return results

    @staticmethod
    def search_catalog(
        db: Session,
        query: str,
        limit: int = 10,
    ) -> list[dict]:
        """Return only matching, active, in-stock catalog variants.

        Price limits are parsed and applied here against the stored selling price;
        the language model does not decide which records qualify.
        """
        query = query.strip()
        if not query:
            return []

        budget_match = re.search(
            r"\b(?:under|below|less than|up to|upto|max(?:imum)?)\s*"
            r"(?:₹|rs\.?\s*)?([\d,]+(?:\.\d+)?)\s*(k|thousand)?\b",
            query,
            re.IGNORECASE,
        )
        max_price = None
        if budget_match:
            amount = Decimal(budget_match.group(1).replace(",", ""))
            if budget_match.group(2):
                amount *= 1000
            max_price = amount

        ignored = {
            "show", "find", "search", "give", "me", "some", "any", "please",
            "product", "products", "available", "best", "good", "for", "with",
            "and", "the", "a", "an", "under", "below", "less", "than", "up",
            "to", "upto", "maximum", "max", "price", "budget", "rupees", "rs",
            "inr", "laptop", "laptops", "notebook", "notebooks", "phone", "phones",
            "smartphone", "smartphones", "mobile", "mobiles", "tablet", "tablets",
            "camera", "cameras", "headphone", "headphones", "earbuds", "with",
        }
        tokens = [term.lower() for term in re.findall(r"[a-zA-Z0-9]+", query)]
        requested_types = {
            "laptop": {"laptop", "notebook"},
            "notebook": {"laptop", "notebook"},
            "phone": {"phone", "smartphone", "mobile"},
            "smartphone": {"phone", "smartphone", "mobile"},
            "mobile": {"phone", "smartphone", "mobile"},
            "tablet": {"tablet"},
            "camera": {"camera"},
            "headphone": {"headphone", "earbud"},
            "earbuds": {"headphone", "earbud"},
        }
        type_matches = set()
        for token in tokens:
            singular = token[:-1] if token.endswith("s") else token
            type_matches.update(requested_types.get(singular, set()))
        terms = [
            term for term in tokens
            if term not in ignored and not term.isdigit()
        ]

        # Load actual catalog rows with their variant data; never synthesize products.
        statement = (
            select(Product)
            .join(ProductVariant, ProductVariant.product_id == Product.id)
            .options(selectinload(Product.variants))
            .where(ProductVariant.is_active.is_(True), ProductVariant.stock_quantity > 0)
            .distinct()
        )
        products = db.scalars(statement).unique().all()
        results = []
        for product in products:
            description = " ".join([
                product.name or "", product.brand or "", product.description or "",
                str(product.specifications or {}),
            ]).lower()
            matching_terms = [term for term in terms if term in description]
            # Respect product kinds such as laptop/phone as real catalog constraints.
            if type_matches and not any(kind in description for kind in type_matches):
                continue
            # A query with specific identifying words must match all of them.
            if terms and len(matching_terms) != len(terms):
                continue

            for variant in product.variants:
                if not variant.is_active or variant.stock_quantity <= 0:
                    continue
                if max_price is not None and Decimal(variant.price) > max_price:
                    continue
                results.append({
                    "product_id": product.id,
                    "product_name": product.name,
                    "brand": product.brand,
                    "description": product.description,
                    "product_specifications": product.specifications or {},
                    "variant_id": variant.id,
                    "variant_name": variant.name,
                    "sku": variant.sku,
                    "price": float(variant.price),
                    "discount": float(variant.discount),
                    "stock_quantity": variant.stock_quantity,
                    "variant_specifications": variant.specifications or {},
                })

        results.sort(key=lambda item: (item["price"], item["product_name"], item["variant_name"]))
        return results[:max(1, min(limit, 50))]

    @staticmethod
    def find_product_variants(
        db: Session,
        query: str,
        limit: int = 5,
    ) -> list[dict]:
        words = [w.strip() for w in query.split() if len(w.strip()) > 1]
        if not words:
            return []
        product_conds = [Product.name.ilike(f"%{w}%") for w in words]
        products = db.scalars(
            select(Product).options(selectinload(Product.variants)).where(or_(*product_conds))
        ).all()
        scored_variants = []
        for product in products:
            product_word_matches = sum(1 for w in words if w.lower() in product.name.lower())
            if product_word_matches == 0:
                continue
            for variant in product.variants:
                if not variant.is_active:
                    continue
                full_variant_text = f"{product.name} {variant.name} {variant.sku}".lower()
                score = sum(1 for w in words if w.lower() in full_variant_text)
                scored_variants.append((score, {
                    "product_id": product.id,
                    "product_name": product.name,
                    "variant_id": variant.id,
                    "variant_name": variant.name,
                    "sku": variant.sku,
                    "price": float(variant.price),
                    "stock_quantity": variant.stock_quantity,
                }))
        if not scored_variants:
            return []
        max_score = max(item[0] for item in scored_variants)
        best_variants = [item[1] for item in scored_variants if item[0] == max_score]
        return best_variants[:limit]
