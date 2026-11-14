from flask import Blueprint, current_app, jsonify, request

from controllers.auth_controller import csrf_protect, login_required
from controllers.finance_controller import FinanceController, ValidationError
from database import get_user_client

finance_bp = Blueprint("finance", __name__, url_prefix="/api")


def controller():
    return FinanceController(get_user_client())


def payload():
    values = request.get_json(silent=True)
    if not isinstance(values, dict):
        raise ValidationError("El cuerpo de la solicitud debe ser un objeto JSON.")
    return values


@finance_bp.get("/dashboard")
@login_required
def dashboard():
    return jsonify(controller().dashboard(
        request.args.get("date"),
        current_app.config["BUSINESS_TIMEZONE"],
    ))


@finance_bp.post("/clients")
@login_required
@csrf_protect
def clients():
    return jsonify(controller().add_client(payload())), 201


@finance_bp.post("/products")
@login_required
@csrf_protect
def products():
    return jsonify(controller().add_product(payload())), 201


@finance_bp.post("/expenses")
@login_required
@csrf_protect
def expenses():
    return jsonify(controller().add_expense(payload())), 201


@finance_bp.post("/capital/contributions")
@login_required
@csrf_protect
def contributions():
    return jsonify(controller().add_contribution(payload())), 201


@finance_bp.post("/income")
@login_required
@csrf_protect
def income():
    return jsonify(controller().add_income(payload())), 201


@finance_bp.put("/capital/opening")
@login_required
@csrf_protect
def opening_capital():
    return jsonify(controller().set_opening_capital(payload()))


@finance_bp.post("/debts")
@login_required
@csrf_protect
def debts():
    return jsonify(controller().add_debt(payload())), 201


@finance_bp.post("/debts/<debt_id>/payments")
@login_required
@csrf_protect
def debt_payment(debt_id):
    return jsonify(controller().repay_debt(debt_id, payload()))


@finance_bp.post("/invoices")
@login_required
@csrf_protect
def invoices():
    return jsonify(controller().add_invoice(payload())), 201


@finance_bp.post("/invoices/<invoice_id>/payments")
@login_required
@csrf_protect
def invoice_payment(invoice_id):
    return jsonify(controller().add_payment(invoice_id, payload()))
