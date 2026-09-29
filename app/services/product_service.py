import re
from difflib import get_close_matches
from decimal import Decimal

from sqlalchemy import select, or_
from sqlalchemy.orm import Session, selectinload

from app.db.models.product import Product, ProductVariant


class ProductService:
    _query_word_corrections = {
        "product", "products", "item", "items", "catalog", "laptop", "laptops",
        "notebook", "notebooks", "phone", "phones", "smartphone", "smartphones",
        "mobile", "mobiles", "tablet", "tablets", "camera", "cameras",
        "headphone", "headphones", "earbuds",
    }
    _query_stop_words = {
        "show", "find", "search", "give", "me", "some", "any", "please",
        "product", "products", "item", "items", "available", "best", "good",
        "for", "with", "and", "the", "a", "an", "under", "below", "less",
        "than", "up", "to", "upto", "maximum", "max", "price", "budget",
        "rupees", "rs", "inr", "laptop", "laptops", "notebook", "notebooks",
        "phone", "phones", "smartphone", "smartphones", "mobile", "mobiles",
        "tablet", "tablets", "camera", "cameras", "headphone", "headphones",
        "earbuds", "how", "many", "unit", "units", "are", "is", "of", "there",
        "in", "stock", "inventory", "quantity", "count", "left", "remain",
        "remaining", "tell", "does", "do", "have", "has", "currently", "right",
        "now", "i", "want", "wanna", "buy", "purchase", "looking", "look",
        "options", "option", "what", "which", "my", "your", "recommend",
        "recommendations", "need", "like", "can", "could", "would", "suggest",
        "compare", "comparison", "versus", "vs",
        "you", "we", "our", "it", "this", "that", "get", "list", "of",
    }

    @classmethod
    def _normalized_query_tokens(cls, query: str) -> list[str]:
        tokens = re.findall(r"[a-zA-Z0-9]+", query.lower())
        normalized = []
        for token in tokens:
            if token in cls._query_word_corrections:
                normalized.append(token)
                continue
            correction = get_close_matches(
                token,
                cls._query_word_corrections,
                n=1,
                cutoff=0.78,
            )
            normalized.append(correction[0] if correction else token)
        return normalized

    @classmethod
    def is_catalog_browse_request(cls, query: str) -> bool:
        tokens = cls._normalized_query_tokens(query)
        product_words = {"product", "products", "item", "items", "catalog"}
        if not product_words.intersection(tokens):
            return False
        requested_types = {
            "laptop", "laptops", "notebook", "notebooks", "phone", "phones",
            "smartphone", "smartphones", "mobile", "mobiles", "tablet", "tablets",
            "camera", "cameras", "headphone", "headphones", "earbuds",
        }
        has_type_filter = bool(requested_types.intersection(tokens))
        has_price_filter = bool(re.search(
            r"\b(?:under|below|less than|up to|upto|max(?:imum)?)\s*"
            r"(?:₹|rs\.?\s*)?[\d,]+(?:\.\d+)?\s*(?:k|thousand)?\b",
            query,
            re.IGNORECASE,
        ))
        has_availability_filter = bool(re.search(
            r"\b(?:in stock|available|availability|stock|inventory)\b",
            query,
            re.IGNORECASE,
        ))
        meaningful_terms = [
            token for token in tokens
            if token not in cls._query_stop_words and not token.isdigit()
        ]
        return not (has_type_filter or has_price_filter or has_availability_filter or meaningful_terms)

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
        include_out_of_stock: bool = False,
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

        tokens = ProductService._normalized_query_tokens(query)
        budget_number = (
            re.sub(r"\D", "", budget_match.group(1))
            if budget_match else None
        )
        terms = [
            term for term in tokens
            if term not in ProductService._query_stop_words
            and (not term.isdigit() or term != budget_number)
        ]
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
        # Keep the normalized identifying terms computed above. A duplicate
        # filter here previously referenced an undefined `ignored` variable.

        # Load actual catalog rows with their variant data; never synthesize products.
        statement = (
            select(Product)
            .join(ProductVariant, ProductVariant.product_id == Product.id)
            .options(selectinload(Product.variants))
            .where(ProductVariant.is_active.is_(True))
            .distinct()
        )
        products = db.scalars(statement).unique().all()
        results = []
        for product in products:
            product_text = " ".join([
                product.name or "", product.brand or "", product.description or "",
                str(product.specifications or {}),
            ]).lower()
            # Respect product kinds such as laptop/phone as real catalog constraints.
            if type_matches and not any(kind in product_text for kind in type_matches):
                continue

            for variant in product.variants:
                if not variant.is_active:
                    continue
                if not include_out_of_stock and variant.stock_quantity <= 0:
                    continue
                variant_text = " ".join([
                    product_text, variant.name or "", variant.sku or "",
                    str(variant.specifications or {}),
                ]).lower()
                # Specific identifying words must match the product or its variant.
                if terms:
                    searchable_tokens = set(re.findall(r"[a-z0-9]+", variant_text))
                    # Match misspelled model names (e.g. "Galxy") against words
                    # that actually occur in catalog records, without relaxing
                    # every term into a broad catalog search.
                    unmatched = [
                        term for term in terms
                        if term not in variant_text
                        and not any(
                            get_close_matches(term, [word], n=1, cutoff=0.78)
                            for word in searchable_tokens
                        )
                    ]
                    if unmatched:
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
