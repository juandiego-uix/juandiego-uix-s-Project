import unittest

from controllers.finance_controller import FinanceController, ValidationError


class ModelStub:
    def create_invoice(self, values):
        return values

    def create_client(self, values):
        return values


class FinanceControllerTests(unittest.TestCase):
    def setUp(self):
        self.controller = FinanceController(None)
        self.controller.model = ModelStub()

    def test_invoice_merges_repeated_product_lines(self):
        product_id = "12345678-1234-5678-1234-567812345678"
        result = self.controller.add_invoice({
            "client_id": None,
            "items": [
                {"product_id": product_id, "quantity": 2},
                {"product_id": product_id, "quantity": 3},
            ],
            "initial_payment": "0",
        })

        self.assertEqual(result["p_items"], [{"product_id": product_id, "quantity": 5}])
        self.assertEqual(result["p_payment"], "0.00")

    def test_invoice_rejects_fractional_quantity_and_money(self):
        product_id = "12345678-1234-5678-1234-567812345678"
        with self.assertRaises(ValidationError):
            self.controller.add_invoice({
                "items": [{"product_id": product_id, "quantity": 1.5}],
                "initial_payment": "0",
            })
        with self.assertRaises(ValidationError):
            self.controller.add_invoice({
                "items": [{"product_id": product_id, "quantity": 1}],
                "initial_payment": "0.001",
            })

    def test_invoice_rejects_invalid_identifier(self):
        with self.assertRaises(ValidationError):
            self.controller.add_invoice({
                "items": [{"product_id": "not-a-uuid", "quantity": 1}],
                "initial_payment": "0",
            })

    def test_client_rejects_optional_text_over_limit(self):
        with self.assertRaises(ValidationError):
            self.controller.add_client({
                "name": "Cliente",
                "phone": "1" * 41,
            })


if __name__ == "__main__":
    unittest.main()
