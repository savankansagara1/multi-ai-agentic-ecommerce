from sqlalchemy import select, or_
from sqlalchemy.orm import Session, selectinload

from app.db.models.product import Product, ProductVariant


class ProductService:

    @staticmethod
    def get_product(
        db: Session,
        product_id: int,
    ) -> Product | None:
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
    def find_product_variants(
        db: Session,
        query: str,
        limit: int = 5,
    ) -> list[dict]:
        """Find active product variants matching the user's natural language query.
        
        Handles both broad product queries (e.g. 'ThinkBook Pro' -> returns multiple variants)
        and specific variant-targeted queries (e.g. 'ThinkBook Pro 8GB' -> returns the specific 8GB variant).
        """
        words = [w.strip() for w in query.split() if len(w.strip()) > 1]
        if not words:
            return []

        # Find products matching any of the significant query words
        product_conds = [Product.name.ilike(f"%{w}%") for w in words]
        products = db.scalars(
            select(Product)
            .options(selectinload(Product.variants))
            .where(or_(*product_conds))
        ).all()

        if not products:
            return []

        scored_variants = []
        for product in products:
            # Check how many query words match the product name itself
            product_word_matches = sum(
                1 for w in words if w.lower() in product.name.lower()
            )
            if product_word_matches == 0:
                continue

            for variant in product.variants:
                if not variant.is_active:
                    continue

                full_variant_text = f"{product.name} {variant.name} {variant.sku}".lower()
                # Score based on how many query words appear in the full variant description
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

        # Filter to the highest-scoring variants (e.g. if '8GB' was specified, prefer 8GB over 16GB)
        max_score = max(item[0] for item in scored_variants)
        best_variants = [item[1] for item in scored_variants if item[0] == max_score]

        return best_variants[:limit]
