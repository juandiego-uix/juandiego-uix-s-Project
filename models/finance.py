from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


class FinanceModel:
    def __init__(self, client):
        self.client = client

    @staticmethod
    def _data(response):
        return response.data or []

    def dashboard(self, day: date, timezone_name: str):
        zone = ZoneInfo(timezone_name)
        start = datetime.combine(day, time.min, tzinfo=zone).isoformat()
        end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=zone).isoformat()
        cash_today = self._data(
            self.client.table("cash_movements")
            .select("direction,amount,kind,description,created_at")
            .gte("created_at", start)
            .lt("created_at", end)
            .order("created_at")
            .execute()
        )
        invoices = self._data(
            self.client.table("invoices")
            .select("id,number,total,cost_total,status,created_at,clients(name)")
            .gte("created_at", start)
            .lt("created_at", end)
            .order("created_at", desc=True)
            .execute()
        )
        invoice_ids = [invoice["id"] for invoice in invoices]
        invoice_items = (
            self._data(
                self.client.table("invoice_items")
                .select("invoice_id,product_name,quantity,unit_price,line_total")
                .in_("invoice_id", invoice_ids)
                .execute()
            )
            if invoice_ids else []
        )
        expenses = self._data(
            self.client.table("expenses")
            .select("amount,description,category,created_at")
            .gte("created_at", start)
            .lt("created_at", end)
            .order("created_at", desc=True)
            .execute()
        )
        clients = self._data(self.client.table("clients").select("id,name,phone").order("name").execute())
        products = self._data(
            self.client.table("products")
            .select("id,name,sku,unit_price,unit_cost,stock,active")
            .order("name")
            .execute()
        )
        debts = self._data(
            self.client.table("debts").select("id,description,creditor,original_amount,balance,due_date")
            .gt("balance", 0).order("created_at", desc=True).execute()
        )
        receivables = self._data(
            self.client.table("invoices")
            .select("id,number,total,balance,status,created_at,clients(name)")
            .gt("balance", 0)
            .order("created_at", desc=True)
            .execute()
        )
        totals_response = self.client.rpc("get_financial_totals", {
            "p_day": day.isoformat(),
            "p_timezone": timezone_name,
        }).execute()
        totals = totals_response.data
        settings = self._data(
            self.client.table("company_settings").select("currency_code").limit(1).execute()
        )
        return {
            "date": day.isoformat(),
            **totals,
            "cash_movements": cash_today,
            "invoices": invoices,
            "invoice_items": invoice_items,
            "expenses": expenses,
            "clients": clients,
            "products": products,
            "debts": debts,
            "receivables": receivables,
            "currency": settings[0]["currency_code"].strip() if settings else "USD",
        }

    def create_client(self, values):
        return self.client.table("clients").insert(values).execute().data[0]

    def create_product(self, values):
        return self.client.table("products").insert(values).execute().data[0]

    def create_expense(self, values):
        return self.client.rpc("record_expense", values).execute().data

    def create_contribution(self, values):
        return self.client.rpc("record_capital_contribution", values).execute().data

    def create_income(self, values):
        return self.client.rpc("record_operating_income", values).execute().data

    def set_opening_capital(self, values):
        return self.client.rpc("set_opening_capital", values).execute().data

    def create_debt(self, values):
        return self.client.rpc("record_debt", values).execute().data

    def repay_debt(self, values):
        return self.client.rpc("repay_debt", values).execute().data

    def create_invoice(self, values):
        return self.client.rpc("create_invoice", values).execute().data

    def record_payment(self, values):
        return self.client.rpc("record_invoice_payment", values).execute().data
