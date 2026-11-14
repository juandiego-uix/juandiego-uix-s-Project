from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from models.finance import FinanceModel


class ValidationError(ValueError):
    pass


def _required_text(data, key, label, max_length=160):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > max_length:
        raise ValidationError(f"{label} es obligatorio (máximo {max_length} caracteres).")
    return value.strip()


def _amount(data, key, label, allow_zero=False):
    try:
        value = Decimal(str(data.get(key, "")))
    except (InvalidOperation, TypeError):
        raise ValidationError(f"{label} debe ser un valor monetario válido.")
    if (
        not value.is_finite()
        or value > Decimal("999999999999.99")
        or value < 0
        or (not allow_zero and value == 0)
        or value.as_tuple().exponent < -2
    ):
        minimum = "igual o mayor que cero" if allow_zero else "mayor que cero"
        raise ValidationError(f"{label} debe ser {minimum} y tener máximo 2 decimales.")
    return str(value.quantize(Decimal("0.01")))


def _optional_text(data, key, max_length):
    value = data.get(key, "")
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(f"El campo {key} no es válido.")
    value = value.strip()
    if len(value) > max_length:
        raise ValidationError(f"El campo {key} no puede superar {max_length} caracteres.")
    return value or None


def _uuid(value, label, optional=False):
    if optional and value in (None, ""):
        return None
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError(f"{label} no es válido.")


def _integer(data, key, label, minimum=0):
    raw = data.get(key)
    if isinstance(raw, bool) or not (
        isinstance(raw, int) or (isinstance(raw, str) and raw.isdecimal())
    ):
        raise ValidationError(f"{label} debe ser un número entero.")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} debe ser un número entero.")
    if value < minimum or value > 2147483647:
        raise ValidationError(f"{label} debe estar entre {minimum} y 2,147,483,647.")
    return value


class FinanceController:
    def __init__(self, client):
        self.model = FinanceModel(client)

    def dashboard(self, day_value, timezone_name):
        try:
            zone = ZoneInfo(timezone_name)
            day = date.fromisoformat(day_value) if day_value else datetime.now(zone).date()
        except (ValueError, ZoneInfoNotFoundError):
            raise ValidationError("La fecha no es válida.")
        return self.model.dashboard(day, timezone_name)

    def add_client(self, data):
        return self.model.create_client({
            "name": _required_text(data, "name", "El nombre", 120),
            "phone": _optional_text(data, "phone", 40),
            "email": _optional_text(data, "email", 254),
            "notes": _optional_text(data, "notes", 500),
        })

    def add_product(self, data):
        sku = _optional_text(data, "sku", 60)
        return self.model.create_product({
            "name": _required_text(data, "name", "El nombre", 120),
            "sku": sku,
            "unit_price": _amount(data, "unit_price", "El precio"),
            "unit_cost": _amount(data, "unit_cost", "El costo", allow_zero=True),
            "stock": _integer(data, "stock", "El inventario"),
        })

    def add_expense(self, data):
        return self.model.create_expense({
            "p_description": _required_text(data, "description", "La descripción", 200),
            "p_category": _required_text(data, "category", "La categoría", 80),
            "p_amount": _amount(data, "amount", "El monto"),
        })

    def add_contribution(self, data):
        return self.model.create_contribution({
            "p_description": _required_text(data, "description", "La descripción", 200),
            "p_amount": _amount(data, "amount", "El aporte"),
        })

    def add_income(self, data):
        return self.model.create_income({
            "p_description": _required_text(data, "description", "La descripción", 200),
            "p_amount": _amount(data, "amount", "El monto"),
        })

    def set_opening_capital(self, data):
        return self.model.set_opening_capital({
            "p_amount": _amount(data, "amount", "El capital inicial", allow_zero=True),
        })

    def add_debt(self, data):
        return self.model.create_debt({
            "p_description": _required_text(data, "description", "La descripción", 200),
            "p_creditor": _required_text(data, "creditor", "El acreedor", 120),
            "p_amount": _amount(data, "amount", "El monto"),
            "p_due_date": self._due_date(data.get("due_date")),
        })

    def add_invoice(self, data):
        client_id = _uuid(data.get("client_id"), "El cliente", optional=True)
        items = data.get("items")
        if not isinstance(items, list) or not items or len(items) > 100:
            raise ValidationError("La factura debe incluir entre 1 y 100 productos.")
        quantities = {}
        for item in items:
            if not isinstance(item, dict):
                raise ValidationError("El detalle de la factura no es válido.")
            product_id = _uuid(item.get("product_id"), "El producto")
            quantities[product_id] = quantities.get(product_id, 0) + _integer(
                item, "quantity", "La cantidad", minimum=1
            )
            if quantities[product_id] > 2147483647:
                raise ValidationError("La cantidad total del producto es demasiado alta.")
        normalized = [
            {"product_id": product_id, "quantity": quantity}
            for product_id, quantity in sorted(quantities.items())
        ]
        return self.model.create_invoice({
            "p_client_id": client_id or None,
            "p_items": normalized,
            "p_notes": _optional_text(data, "notes", 500),
            "p_payment": _amount(data, "initial_payment", "El abono inicial", allow_zero=True),
        })

    def add_payment(self, invoice_id, data):
        return self.model.record_payment({
            "p_invoice_id": _uuid(invoice_id, "La factura"),
            "p_amount": _amount(data, "amount", "El abono"),
            "p_description": _optional_text(data, "description", 200) or "Abono de cliente",
        })

    @staticmethod
    def _due_date(value):
        if not value:
            return None
        try:
            return date.fromisoformat(value).isoformat()
        except (ValueError, TypeError):
            raise ValidationError("La fecha de vencimiento no es válida.")

    def repay_debt(self, debt_id, data):
        return self.model.repay_debt({
            "p_debt_id": _uuid(debt_id, "La deuda"),
            "p_amount": _amount(data, "amount", "El abono"),
            "p_description": _optional_text(data, "description", 200) or "Abono a deuda",
        })
