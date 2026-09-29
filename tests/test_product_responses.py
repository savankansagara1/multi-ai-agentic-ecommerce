import unittest
from unittest.mock import patch

from app.agents.product_graph import build_product_graph
from app.services.product_service import ProductService


class FakeResponse:
    def __init__(self, content):
        self.content = content


class FakeLLM:
    def __init__(self, content):
        self.content = content
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return FakeResponse(self.content)


class TestProductResponses(unittest.TestCase):
    def setUp(self):
        self.products = [
            {
                "product_id": 1, "product_name": "Galaxy Pro", "brand": "Samsung",
                "variant_id": 11, "variant_name": "128GB", "sku": "GP-128",
                "price": 54999.0, "stock_quantity": 48,
                "product_specifications": {"display": "AMOLED"},
                "variant_specifications": {"storage": "128GB"},
            },
            {
                "product_id": 2, "product_name": "ThinkBook Pro", "brand": "Lenovo",
                "variant_id": 22, "variant_name": "8GB RAM / 512GB SSD", "sku": "TBP-8-512",
                "price": 74999.0, "stock_quantity": 38,
                "product_specifications": {"type": "laptop"},
                "variant_specifications": {"ram": "8GB", "storage": "512GB"},
            },
        ]

    def test_comparison_is_written_by_llm_and_keeps_catalog_rows(self):
        generated = "The Galaxy is a phone and the ThinkBook is a laptop. What will you use it for most?"
        model = FakeLLM(generated)
        with (
            patch.object(ProductService, "is_catalog_browse_request", return_value=False),
            patch.object(ProductService, "search_catalog", return_value=self.products),
            patch("app.agents.product_graph.llm", model),
        ):
            result = build_product_graph(db=None).invoke({
                "messages": [{"role": "user", "content": "Compare Galaxy Pro and ThinkBook Pro"}]
            })
        answer = result["messages"][-1].content
        self.assertTrue(answer.startswith(generated))
        self.assertIn("Galaxy Pro — 128GB", answer)
        self.assertIn("ThinkBook Pro — 8GB RAM / 512GB SSD", answer)
        self.assertIn("authoritative", model.prompts[0][1].content)

    def test_no_match_response_is_written_by_llm(self):
        generated = "I couldn’t find that model in the catalog. Was there another name or budget you had in mind?"
        model = FakeLLM(generated)
        with (
            patch.object(ProductService, "is_catalog_browse_request", return_value=False),
            patch.object(ProductService, "search_catalog", return_value=[]),
            patch("app.agents.product_graph.llm", model),
        ):
            result = build_product_graph(db=None).invoke({
                "messages": [{"role": "user", "content": "Show me an unknown model"}]
            })
        self.assertEqual(result["messages"][-1].content, generated)
        self.assertEqual(len(model.prompts), 1)

    def test_catalog_list_keeps_every_database_record(self):
        model = FakeLLM("Here is the full range of products currently in the catalog.")
        with (
            patch.object(ProductService, "is_catalog_browse_request", return_value=True),
            patch.object(ProductService, "list_catalog", return_value=self.products),
            patch("app.agents.product_graph.llm", model),
        ):
            result = build_product_graph(db=None).invoke({
                "messages": [{"role": "user", "content": "List all products"}]
            })
        answer = result["messages"][-1].content
        self.assertIn("Galaxy Pro — 128GB", answer)
        self.assertIn("ThinkBook Pro — 8GB RAM / 512GB SSD", answer)
        self.assertIn("full range", answer)


if __name__ == "__main__":
    unittest.main()
