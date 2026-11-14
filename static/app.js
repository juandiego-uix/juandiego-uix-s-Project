(() => {
  "use strict";
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || "";
  const dateInput = document.getElementById("report-date");
  if (!dateInput) return;
  const businessTimezone = dateInput.dataset.timezone || "UTC";
  const state = { data: null, invoiceItems: [] };
  if (!dateInput.value) dateInput.value = new Date().toISOString().slice(0, 10);
  const $ = (id) => document.getElementById(id);
  const safe = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[char]));
  const money = (value) => new Intl.NumberFormat("es-CO", {
    style: "currency", currency: state.data?.currency || "USD",
    minimumFractionDigits: 2, maximumFractionDigits: 2
  }).format(Number(value || 0));
  const showNotice = (message, isError = false) => {
    const box = $("notice");
    box.textContent = message;
    box.className = `mb-5 rounded-xl px-4 py-3 text-sm ${isError ? "border border-red-200 bg-red-50 text-red-800" : "border border-emerald-200 bg-emerald-50 text-emerald-800"}`;
    window.setTimeout(() => box.classList.add("hidden"), 5000);
  };
  async function api(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf, ...(options.headers || {}) }
    });
    const body = await response.json().catch(() => ({}));
    if (response.status === 401) window.location.assign("/");
    if (!response.ok) throw new Error(body.error || "No fue posible completar la operación.");
    return body;
  }
  const emptyRow = (cols, message) => `<tr><td colspan="${cols}" class="px-5 py-7 text-center text-slate-400">${message}</td></tr>`;

  async function refresh() {
    try {
      state.data = await api(`/api/dashboard?date=${encodeURIComponent(dateInput.value)}`, { headers: {} });
      render();
    } catch (error) {
      showNotice(error.message, true);
    }
  }

  function render() {
    const d = state.data;
    ["opening_cash", "closing_cash", "revenue", "cost_of_goods", "expenses_total", "daily_profit", "net_worth"]
      .forEach((key) => { $(key.replaceAll("_", "-")).textContent = money(d[key]); });
    $("invoices-table").innerHTML = d.invoices.length ? d.invoices.map((row) => {
      const client = row.clients?.name || "Venta sin cliente";
      return `<tr class="border-t border-slate-100"><td class="px-5 py-3"><strong>${safe(row.number)}</strong><span class="block text-xs text-slate-500">${safe(client)}</span></td><td class="px-3 py-3">${money(row.total)}</td><td class="px-3 py-3">${money(row.balance)}</td><td class="px-5 py-3"><button class="text-xs font-semibold text-emerald-800" data-receipt="${safe(row.id)}">Comprobante</button></td></tr>`;
    }).join("") : emptyRow(4, "No hay facturas para esta fecha.");
    $("receivables-table").innerHTML = d.receivables.length ? d.receivables.map((row) =>
      `<tr class="border-t border-slate-100"><td class="px-5 py-3"><strong>${safe(row.number)}</strong><span class="block text-xs text-slate-500">${safe(row.clients?.name || "Venta sin cliente")}</span></td><td class="px-3 py-3 font-medium">${money(row.balance)}</td><td class="px-5 py-3"><button class="text-xs font-semibold text-emerald-800" data-payment="${safe(row.id)}" data-balance="${safe(row.balance)}">Registrar abono</button></td></tr>`
    ).join("") : emptyRow(3, "La cartera está al día.");
    $("products-table").innerHTML = d.products.length ? d.products.map((row) =>
      `<tr class="border-t border-slate-100"><td class="px-5 py-3">${safe(row.name)}${row.sku ? `<span class="block text-xs text-slate-400">${safe(row.sku)}</span>` : ""}</td><td class="px-3 py-3">${safe(row.stock)}</td><td class="px-3 py-3">${money(row.unit_price)}</td><td class="px-5 py-3">${money(row.unit_cost)}</td></tr>`
    ).join("") : emptyRow(4, "Agrega productos para habilitar facturación.");
    $("debts-table").innerHTML = d.debts.length ? d.debts.map((row) =>
      `<tr class="border-t border-amber-100"><td class="px-5 py-3">${safe(row.creditor)}<span class="block text-xs text-slate-500">${safe(row.description)}</span></td><td class="px-3 py-3"><span class="inline-flex rounded-full bg-amber-100 px-2.5 py-1 font-semibold text-amber-950">${money(row.balance)}</span></td><td class="px-5 py-3"><button class="text-xs font-semibold text-amber-800 hover:text-amber-950" data-debt-payment="${safe(row.id)}" data-balance="${safe(row.balance)}">Abonar</button></td></tr>`
    ).join("") : emptyRow(3, "No hay deudas activas.");
    $("cash-table").innerHTML = d.cash_movements.length ? d.cash_movements.map((row) => {
      const amount = `${row.direction === "in" ? "+" : "−"}${money(row.amount)}`;
      const time = new Date(row.created_at).toLocaleTimeString("es-CO", {
        hour: "2-digit",
        minute: "2-digit",
        timeZone: businessTimezone
      });
      return `<tr class="border-t border-slate-100"><td class="px-5 py-3">${time}</td><td class="px-3 py-3">${row.direction === "in" ? "Entrada" : "Salida"}</td><td class="px-3 py-3">${safe(row.description)}</td><td class="px-5 py-3 font-medium">${amount}</td></tr>`;
    }).join("") : emptyRow(4, "Sin movimientos registrados.");
    $("invoice-client").innerHTML = `<option value="">Venta sin cliente</option>` + d.clients.map((c) => `<option value="${safe(c.id)}">${safe(c.name)}</option>`).join("");
    $("invoice-product").innerHTML = d.products.filter((p) => p.active && p.stock > 0).map((p) =>
      `<option value="${safe(p.id)}">${safe(p.name)} · ${money(p.unit_price)} · stock ${safe(p.stock)}</option>`
    ).join("");
  }

  function openModal(id) {
    const modal = $(id);
    modal?.classList.remove("hidden");
    modal?.classList.add("flex");
  }
  function closeModal(modal) {
    modal.classList.add("hidden");
    modal.classList.remove("flex");
  }
  document.querySelectorAll("[data-open]").forEach((button) => button.addEventListener("click", () => openModal(button.dataset.open)));
  document.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", () => closeModal(button.closest(".modal"))));
  document.querySelectorAll(".modal").forEach((modal) => modal.addEventListener("click", (event) => {
    if (event.target === modal) closeModal(modal);
  }));
  dateInput.addEventListener("change", refresh);
  $("logout").addEventListener("click", () => $("logout-form").requestSubmit());

  function connectForm(formId, path, transform = (form) => Object.fromEntries(new FormData(form))) {
    $(formId).addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      try {
        await api(path, { method: "POST", body: JSON.stringify(transform(form)) });
        form.reset();
        closeModal(form.closest(".modal"));
        showNotice("Registro guardado correctamente.");
        await refresh();
      } catch (error) {
        showNotice(error.message, true);
      }
    });
  }
  connectForm("expense-form", "/api/expenses");
  connectForm("income-form", "/api/income");
  connectForm("client-form", "/api/clients");
  connectForm("product-form", "/api/products", (form) => {
    const values = Object.fromEntries(new FormData(form));
    values.stock = Number(values.stock);
    return values;
  });
  connectForm("capital-form", "/api/capital/contributions");
  connectForm("debt-form", "/api/debts");
  $("opening-capital-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await api("/api/capital/opening", {
        method: "PUT",
        body: JSON.stringify({ amount: new FormData(event.currentTarget).get("amount") })
      });
      event.currentTarget.reset();
      closeModal($("opening-capital-modal"));
      showNotice("Capital inicial configurado. No se puede cambiar desde el panel.");
      await refresh();
    } catch (error) { showNotice(error.message, true); }
  });

  function renderInvoiceItems() {
    $("invoice-items").innerHTML = state.invoiceItems.map((item, index) =>
      `<tr class="border-t"><td class="py-2">${safe(item.name)}</td><td>${item.quantity}</td><td>${money(item.unit_price * item.quantity)}</td><td><button type="button" class="text-red-600" data-remove-item="${index}" aria-label="Quitar">Quitar</button></td></tr>`
    ).join("");
    const total = state.invoiceItems.reduce((sum, item) => sum + item.unit_price * item.quantity, 0);
    $("invoice-total").textContent = money(total);
  }
  $("add-invoice-item").addEventListener("click", () => {
    const product = state.data.products.find((item) => item.id === $("invoice-product").value);
    const quantity = Number($("invoice-quantity").value);
    if (!product || !Number.isInteger(quantity) || quantity < 1) return showNotice("Seleccione un producto y una cantidad válida.", true);
    const existing = state.invoiceItems.find((item) => item.product_id === product.id);
    const nextQuantity = (existing?.quantity || 0) + quantity;
    if (nextQuantity > product.stock) return showNotice("La cantidad supera las existencias disponibles.", true);
    if (existing) existing.quantity = nextQuantity;
    else state.invoiceItems.push({ product_id: product.id, name: product.name, unit_price: Number(product.unit_price), quantity });
    renderInvoiceItems();
  });
  $("invoice-items").addEventListener("click", (event) => {
    const index = event.target.dataset.removeItem;
    if (index === undefined) return;
    state.invoiceItems.splice(Number(index), 1);
    renderInvoiceItems();
  });
  $("invoice-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.invoiceItems.length) return showNotice("Agrega al menos un producto a la factura.", true);
    const body = {
      client_id: $("invoice-client").value || null,
      items: state.invoiceItems.map(({ product_id, quantity }) => ({ product_id, quantity })),
      initial_payment: $("invoice-initial-payment").value || "0",
      notes: $("invoice-notes").value
    };
    try {
      const invoice = await api("/api/invoices", { method: "POST", body: JSON.stringify(body) });
      state.invoiceItems = [];
      renderInvoiceItems();
      event.currentTarget.reset();
      closeModal($("invoice-modal"));
      showNotice(`Factura ${invoice.number} creada. Total: ${money(invoice.total)}.`);
      await refresh();
    } catch (error) { showNotice(error.message, true); }
  });

  document.body.addEventListener("click", async (event) => {
    const target = event.target;
    if (target.dataset.payment) {
      const amount = window.prompt(`Saldo pendiente ${money(target.dataset.balance)}. Monto del abono:`);
      if (amount === null) return;
      try {
        const receipt = await api(`/api/invoices/${encodeURIComponent(target.dataset.payment)}/payments`, {
          method: "POST", body: JSON.stringify({ amount })
        });
        receipt.amount = amount;
        showNotice(`Abono registrado. Saldo restante: ${money(receipt.remaining_balance)}.`);
        createReceipt(receipt);
        await refresh();
      } catch (error) { showNotice(error.message, true); }
    }
    if (target.dataset.debtPayment) {
      const amount = window.prompt(`Saldo de deuda ${money(target.dataset.balance)}. Monto del abono:`);
      if (amount === null) return;
      try {
        await api(`/api/debts/${encodeURIComponent(target.dataset.debtPayment)}/payments`, {
          method: "POST", body: JSON.stringify({ amount })
        });
        showNotice("Abono a la deuda registrado.");
        await refresh();
      } catch (error) { showNotice(error.message, true); }
    }
    if (target.dataset.receipt) {
      const invoice = state.data.invoices.find((item) => item.id === target.dataset.receipt);
      if (invoice) createInvoiceReceipt(invoice);
    }
  });

  function pdf(title, headers, rows, filename) {
    if (!window.jspdf?.jsPDF) return showNotice("No fue posible cargar el módulo PDF. Verifica tu conexión.", true);
    const doc = new window.jspdf.jsPDF();
    if (typeof doc.autoTable !== "function") return showNotice("No fue posible cargar el módulo de tablas PDF.", true);
    doc.setFontSize(16);
    doc.text("ARANKO FOOD", 14, 17);
    doc.setFontSize(12);
    doc.text(title, 14, 25);
    doc.setFontSize(9);
    doc.text(`Fecha: ${state.data.date}`, 14, 31);
    doc.autoTable({ startY: 37, head: [headers], body: rows, styles: { fontSize: 8 }, headStyles: { fillColor: [23, 107, 80] } });
    doc.save(filename);
  }
  function createReceipt(payment) {
    pdf("Comprobante de pago", ["Concepto", "Detalle"], [
      ["Factura", payment.invoice_number || payment.number || payment.id],
      ["Pago recibido", money(payment.amount)],
      ["Saldo pendiente", money(payment.remaining_balance ?? payment.balance)]
    ], `comprobante-${payment.invoice_number || payment.id}.pdf`);
  }
  function createInvoiceReceipt(invoice) {
    const items = state.data.invoice_items.filter((item) => item.invoice_id === invoice.id);
    pdf(`Factura ${invoice.number}`, ["Producto", "Cantidad", "Precio unitario", "Total"], [
      ...items.map((item) => [item.product_name, item.quantity, money(item.unit_price), money(item.line_total)]),
      ["TOTAL", "", "", money(invoice.total)],
      ["SALDO PENDIENTE", "", "", money(invoice.balance)]
    ], `factura-${invoice.number}.pdf`);
  }
  $("pdf-cash").addEventListener("click", () => pdf("Corte de caja diario",
    ["Concepto", "Monto"], [
      ["Saldo inicial", money(state.data.opening_cash)],
      ["Ingresos facturados", money(state.data.revenue)],
      ["Costo de productos vendidos", money(state.data.cost_of_goods)],
      ["Gastos del día", money(state.data.expenses_total)],
      ["Saldo final de caja", money(state.data.closing_cash)],
      ...state.data.cash_movements.map((m) => [m.description, `${m.direction === "in" ? "+" : "-"}${money(m.amount)}`])
    ], `corte-caja-${state.data.date}.pdf`));
  $("pdf-sales").addEventListener("click", () => pdf("Detalle de facturas",
    ["Factura", "Cliente", "Producto", "Cantidad", "Precio", "Total"], state.data.invoice_items.map((item) => {
      const invoice = state.data.invoices.find((row) => row.id === item.invoice_id);
      return [
        invoice?.number || "", invoice?.clients?.name || "Venta sin cliente",
        item.product_name, item.quantity, money(item.unit_price), money(item.line_total)
      ];
    }), `facturas-${state.data.date}.pdf`));
  $("pdf-receivables").addEventListener("click", () => pdf("Estado de cartera",
    ["Factura", "Cliente", "Total factura", "Saldo pendiente"], state.data.receivables.map((i) => [
      i.number, i.clients?.name || "Venta sin cliente", money(i.total), money(i.balance)
    ]), `cartera-${state.data.date}.pdf`));
  $("pdf-debts").addEventListener("click", () => pdf("Deudas activas",
    ["Acreedor", "Descripción", "Saldo", "Vencimiento"], state.data.debts.map((d) => [
      d.creditor, d.description, money(d.balance), d.due_date || "Sin fecha"
    ]), `deudas-${state.data.date}.pdf`));

  let installPrompt;
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    installPrompt = event;
    $("install-app").classList.remove("hidden");
  });
  $("install-app").addEventListener("click", async () => {
    if (!installPrompt) return;
    await installPrompt.prompt();
    installPrompt = null;
    $("install-app").classList.add("hidden");
  });
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/service-worker.js").catch(() => showNotice("No se pudo preparar el modo instalable.", true));
  }
  refresh();
})();
