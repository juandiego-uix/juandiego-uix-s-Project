create extension if not exists pgcrypto;

create table if not exists public.user_roles (
    user_id uuid primary key references auth.users(id) on delete cascade,
    role text not null check (role in ('admin'))
);

create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.user_roles
        where user_id = (select auth.uid())
          and role = 'admin'
    );
$$;

revoke all on function public.is_admin() from public, anon;
grant execute on function public.is_admin() to authenticated;

create table if not exists public.company_settings (
    id boolean primary key default true check (id),
    opening_capital numeric(14,2) not null default 0 check (opening_capital >= 0),
    opening_capital_set boolean not null default false,
    currency_code char(3) not null default 'USD' check (currency_code ~ '^[A-Z]{3}$'),
    updated_at timestamptz not null default now()
);

insert into public.company_settings (id) values (true) on conflict (id) do nothing;

create table if not exists public.clients (
    id uuid primary key default gen_random_uuid(),
    name text not null check (length(trim(name)) between 1 and 120),
    phone text,
    email text,
    notes text,
    created_at timestamptz not null default now()
);

create table if not exists public.products (
    id uuid primary key default gen_random_uuid(),
    name text not null check (length(trim(name)) between 1 and 120),
    sku text unique,
    unit_price numeric(14,2) not null check (unit_price > 0),
    unit_cost numeric(14,2) not null check (unit_cost >= 0),
    stock integer not null default 0 check (stock >= 0),
    active boolean not null default true,
    created_at timestamptz not null default now()
);

create sequence if not exists public.invoice_number_seq;

create table if not exists public.invoices (
    id uuid primary key default gen_random_uuid(),
    number text not null unique,
    client_id uuid references public.clients(id) on delete restrict,
    subtotal numeric(14,2) not null check (subtotal >= 0),
    total numeric(14,2) not null check (total >= 0),
    cost_total numeric(14,2) not null check (cost_total >= 0),
    balance numeric(14,2) not null check (balance >= 0),
    status text not null check (status in ('paid', 'partial', 'pending')),
    notes text,
    created_at timestamptz not null default now()
);

create index if not exists invoices_created_at_idx on public.invoices (created_at desc);
create index if not exists invoices_client_id_idx on public.invoices (client_id);

create table if not exists public.invoice_items (
    id uuid primary key default gen_random_uuid(),
    invoice_id uuid not null references public.invoices(id) on delete cascade,
    product_id uuid not null references public.products(id) on delete restrict,
    product_name text not null,
    quantity integer not null check (quantity > 0),
    unit_price numeric(14,2) not null check (unit_price > 0),
    unit_cost numeric(14,2) not null check (unit_cost >= 0),
    line_total numeric(14,2) not null check (line_total >= 0),
    line_cost numeric(14,2) not null check (line_cost >= 0)
);

create table if not exists public.cash_movements (
    id uuid primary key default gen_random_uuid(),
    direction text not null check (direction in ('in', 'out')),
    kind text not null check (kind in (
        'invoice_payment', 'operating_income', 'expense', 'capital_contribution', 'opening_capital',
        'debt_proceeds', 'debt_payment'
    )),
    amount numeric(14,2) not null check (amount > 0),
    description text not null,
    reference_type text,
    reference_id uuid,
    created_at timestamptz not null default now()
);

create index if not exists cash_movements_created_at_idx on public.cash_movements (created_at);
create index if not exists cash_movements_kind_idx on public.cash_movements (kind);

create table if not exists public.invoice_payments (
    id uuid primary key default gen_random_uuid(),
    invoice_id uuid not null references public.invoices(id) on delete restrict,
    amount numeric(14,2) not null check (amount > 0),
    description text not null default 'Abono de cliente',
    cash_movement_id uuid not null references public.cash_movements(id) on delete restrict,
    created_at timestamptz not null default now()
);

create table if not exists public.expenses (
    id uuid primary key default gen_random_uuid(),
    description text not null,
    category text not null,
    amount numeric(14,2) not null check (amount > 0),
    cash_movement_id uuid not null references public.cash_movements(id) on delete restrict,
    created_at timestamptz not null default now()
);

create table if not exists public.debts (
    id uuid primary key default gen_random_uuid(),
    description text not null,
    creditor text not null,
    original_amount numeric(14,2) not null check (original_amount > 0),
    balance numeric(14,2) not null check (balance >= 0),
    due_date date,
    created_at timestamptz not null default now()
);

create table if not exists public.debt_payments (
    id uuid primary key default gen_random_uuid(),
    debt_id uuid not null references public.debts(id) on delete restrict,
    amount numeric(14,2) not null check (amount > 0),
    description text not null,
    cash_movement_id uuid not null references public.cash_movements(id) on delete restrict,
    created_at timestamptz not null default now()
);

alter table public.user_roles enable row level security;
alter table public.company_settings enable row level security;
alter table public.clients enable row level security;
alter table public.products enable row level security;
alter table public.invoices enable row level security;
alter table public.invoice_items enable row level security;
alter table public.cash_movements enable row level security;
alter table public.invoice_payments enable row level security;
alter table public.expenses enable row level security;
alter table public.debts enable row level security;
alter table public.debt_payments enable row level security;

drop policy if exists "admin reads own role" on public.user_roles;
create policy "admin reads own role" on public.user_roles
    for select to authenticated using (user_id = (select auth.uid()));

drop policy if exists "admin manages company settings" on public.company_settings;
create policy "admin manages company settings" on public.company_settings
    for all to authenticated using ((select public.is_admin()))
    with check ((select public.is_admin()));

do $$
declare
    table_name text;
begin
    foreach table_name in array array[
        'clients', 'products', 'invoices', 'invoice_items', 'cash_movements',
        'invoice_payments', 'expenses', 'debts', 'debt_payments'
    ]
    loop
        execute format('drop policy if exists "admin manages %1$s" on public.%1$I', table_name);
        execute format(
            'create policy "admin manages %1$s" on public.%1$I for all to authenticated using ((select public.is_admin())) with check ((select public.is_admin()))',
            table_name
        );
    end loop;
end
$$;

create or replace function public.record_expense(
    p_description text, p_category text, p_amount numeric
)
returns jsonb language plpgsql security definer set search_path = ''
as $$
declare movement_id uuid; expense_id uuid;
begin
    if not public.is_admin() then raise exception 'Acceso denegado'; end if;
    if p_amount <= 0 or p_amount <> round(p_amount, 2) then raise exception 'Monto inválido'; end if;
    insert into public.cash_movements(direction, kind, amount, description)
    values ('out', 'expense', p_amount, p_description) returning id into movement_id;
    insert into public.expenses(description, category, amount, cash_movement_id)
    values (p_description, p_category, p_amount, movement_id) returning id into expense_id;
    return jsonb_build_object('id', expense_id, 'cash_movement_id', movement_id);
end;
$$;

create or replace function public.record_capital_contribution(p_description text, p_amount numeric)
returns jsonb language plpgsql security definer set search_path = ''
as $$
declare movement_id uuid;
begin
    if not public.is_admin() then raise exception 'Acceso denegado'; end if;
    if p_amount <= 0 or p_amount <> round(p_amount, 2) then raise exception 'Monto inválido'; end if;
    insert into public.cash_movements(direction, kind, amount, description)
    values ('in', 'capital_contribution', p_amount, p_description) returning id into movement_id;
    return jsonb_build_object('cash_movement_id', movement_id);
end;
$$;

create or replace function public.record_operating_income(p_description text, p_amount numeric)
returns jsonb language plpgsql security definer set search_path = ''
as $$
declare movement_id uuid;
begin
    if not public.is_admin() then raise exception 'Acceso denegado'; end if;
    if p_amount <= 0 or p_amount <> round(p_amount, 2) then raise exception 'Monto inválido'; end if;
    insert into public.cash_movements(direction, kind, amount, description)
    values ('in', 'operating_income', p_amount, p_description) returning id into movement_id;
    return jsonb_build_object('cash_movement_id', movement_id);
end;
$$;

create or replace function public.set_opening_capital(p_amount numeric)
returns jsonb language plpgsql security definer set search_path = ''
as $$
begin
    if not public.is_admin() then raise exception 'Acceso denegado'; end if;
    if p_amount < 0 or p_amount <> round(p_amount, 2) then raise exception 'Monto inválido'; end if;
    update public.company_settings set opening_capital = p_amount, opening_capital_set = true,
        updated_at = now() where id = true and opening_capital_set = false;
    if not found then raise exception 'El capital inicial ya fue configurado'; end if;
    if p_amount > 0 then
        insert into public.cash_movements(direction, kind, amount, description)
        values ('in', 'opening_capital', p_amount, 'Capital inicial');
    end if;
    return jsonb_build_object('opening_capital', p_amount);
end;
$$;

create or replace function public.record_debt(
    p_description text, p_creditor text, p_amount numeric, p_due_date date default null
)
returns jsonb language plpgsql security definer set search_path = ''
as $$
declare movement_id uuid; debt_id uuid;
begin
    if not public.is_admin() then raise exception 'Acceso denegado'; end if;
    if p_amount <= 0 or p_amount <> round(p_amount, 2) then raise exception 'Monto inválido'; end if;
    insert into public.debts(description, creditor, original_amount, balance, due_date)
    values (p_description, p_creditor, p_amount, p_amount, p_due_date) returning id into debt_id;
    insert into public.cash_movements(direction, kind, amount, description, reference_type, reference_id)
    values ('in', 'debt_proceeds', p_amount, p_description, 'debt', debt_id) returning id into movement_id;
    return jsonb_build_object('id', debt_id, 'cash_movement_id', movement_id);
end;
$$;

create or replace function public.repay_debt(p_debt_id uuid, p_amount numeric, p_description text)
returns jsonb language plpgsql security definer set search_path = ''
as $$
declare debt_row public.debts%rowtype; movement_id uuid; payment_id uuid;
begin
    if not public.is_admin() then raise exception 'Acceso denegado'; end if;
    if p_amount <= 0 or p_amount <> round(p_amount, 2) then raise exception 'Monto inválido'; end if;
    select * into debt_row from public.debts where id = p_debt_id for update;
    if not found or p_amount > debt_row.balance then raise exception 'El abono supera el saldo pendiente'; end if;
    update public.debts set balance = balance - p_amount where id = p_debt_id;
    insert into public.cash_movements(direction, kind, amount, description, reference_type, reference_id)
    values ('out', 'debt_payment', p_amount, p_description, 'debt', p_debt_id) returning id into movement_id;
    insert into public.debt_payments(debt_id, amount, description, cash_movement_id)
    values (p_debt_id, p_amount, p_description, movement_id) returning id into payment_id;
    return jsonb_build_object('id', payment_id, 'remaining_balance', debt_row.balance - p_amount);
end;
$$;

create or replace function public.create_invoice(
    p_client_id uuid, p_items jsonb, p_notes text default null, p_payment numeric default 0
)
returns jsonb language plpgsql security definer set search_path = ''
as $$
declare
    item jsonb; product_row public.products%rowtype;
    qty integer; v_subtotal numeric(14,2) := 0; v_cost numeric(14,2) := 0;
    v_total numeric(14,2); v_balance numeric(14,2); v_invoice_id uuid;
    v_number text; v_movement_id uuid; v_payment_id uuid;
begin
    if not public.is_admin() then raise exception 'Acceso denegado'; end if;
    if p_items is null or jsonb_typeof(p_items) is distinct from 'array' then
        raise exception 'Detalle inválido';
    end if;
    if jsonb_array_length(p_items) < 1 or jsonb_array_length(p_items) > 100 then
        raise exception 'Detalle inválido';
    end if;
    if p_payment < 0 or p_payment <> round(p_payment, 2) then raise exception 'Abono inválido'; end if;
    if p_client_id is not null and not exists(select 1 from public.clients where id = p_client_id) then
       raise exception 'Cliente inválido';
    end if;

    for item in select value from jsonb_array_elements(p_items) order by value->>'product_id'
    loop
        qty := (item->>'quantity')::integer;
        if qty < 1 then raise exception 'Cantidad inválida'; end if;
        select * into product_row from public.products
        where id = (item->>'product_id')::uuid and active = true for update;
        if not found then raise exception 'Producto no encontrado o inactivo'; end if;
        if product_row.stock < qty then raise exception 'Inventario insuficiente para %', product_row.name; end if;
        v_subtotal := v_subtotal + product_row.unit_price * qty;
        v_cost := v_cost + product_row.unit_cost * qty;
    end loop;
    v_total := round(v_subtotal, 2);
    if p_payment > v_total then raise exception 'El abono excede el total de la factura'; end if;
    v_balance := v_total - p_payment;
    v_number := 'AF-' || to_char(now() at time zone 'UTC', 'YYYY') || '-' ||
                lpad(nextval('public.invoice_number_seq')::text, 7, '0');

    insert into public.invoices(number, client_id, subtotal, total, cost_total, balance, status, notes)
    values (v_number, p_client_id, v_total, v_total, round(v_cost, 2), v_balance,
            case when v_balance = 0 then 'paid' when p_payment > 0 then 'partial' else 'pending' end, p_notes)
    returning id into v_invoice_id;

    for item in select value from jsonb_array_elements(p_items) order by value->>'product_id'
    loop
        qty := (item->>'quantity')::integer;
        select * into product_row from public.products where id = (item->>'product_id')::uuid for update;
        insert into public.invoice_items(
            invoice_id, product_id, product_name, quantity, unit_price, unit_cost, line_total, line_cost
        ) values (
            v_invoice_id, product_row.id, product_row.name, qty, product_row.unit_price,
            product_row.unit_cost, product_row.unit_price * qty, product_row.unit_cost * qty
        );
        update public.products set stock = stock - qty where id = product_row.id;
    end loop;

    if p_payment > 0 then
        insert into public.cash_movements(direction, kind, amount, description, reference_type, reference_id)
        values ('in', 'invoice_payment', p_payment, 'Pago inicial ' || v_number, 'invoice', v_invoice_id)
        returning id into v_movement_id;
        insert into public.invoice_payments(invoice_id, amount, description, cash_movement_id)
        values (v_invoice_id, p_payment, 'Pago inicial', v_movement_id) returning id into v_payment_id;
    end if;
    return jsonb_build_object(
        'id', v_invoice_id, 'number', v_number, 'total', v_total, 'balance', v_balance,
        'status', case when v_balance = 0 then 'paid' when p_payment > 0 then 'partial' else 'pending' end,
        'payment_id', v_payment_id
    );
end;
$$;

create or replace function public.record_invoice_payment(
    p_invoice_id uuid, p_amount numeric, p_description text default 'Abono de cliente'
)
returns jsonb language plpgsql security definer set search_path = ''
as $$
declare invoice_row public.invoices%rowtype; movement_id uuid; payment_id uuid;
begin
    if not public.is_admin() then raise exception 'Acceso denegado'; end if;
    if p_amount <= 0 or p_amount <> round(p_amount, 2) then raise exception 'Monto inválido'; end if;
    select * into invoice_row from public.invoices where id = p_invoice_id for update;
    if not found or p_amount > invoice_row.balance then raise exception 'El abono supera el saldo pendiente'; end if;
    update public.invoices set balance = balance - p_amount,
        status = case when balance - p_amount = 0 then 'paid' else 'partial' end
        where id = p_invoice_id;
    insert into public.cash_movements(direction, kind, amount, description, reference_type, reference_id)
    values ('in', 'invoice_payment', p_amount, p_description || ' ' || invoice_row.number, 'invoice', p_invoice_id)
    returning id into movement_id;
    insert into public.invoice_payments(invoice_id, amount, description, cash_movement_id)
    values (p_invoice_id, p_amount, p_description, movement_id) returning id into payment_id;
    return jsonb_build_object(
        'id', payment_id, 'invoice_id', p_invoice_id,
        'amount', p_amount,
        'remaining_balance', invoice_row.balance - p_amount,
        'invoice_number', invoice_row.number
    );
end;
$$;

create or replace function public.get_financial_totals(p_day date, p_timezone text default 'UTC')
returns jsonb language plpgsql stable security invoker set search_path = ''
as $$
declare
    day_start timestamptz := p_day::timestamp at time zone p_timezone;
    day_end timestamptz := (p_day + 1)::timestamp at time zone p_timezone;
    opening_cash numeric(14,2); day_delta numeric(14,2);
    day_revenue numeric(14,2); day_cost numeric(14,2); day_expenses numeric(14,2);
    contributions numeric(14,2); retained_profit numeric(14,2); liability_total numeric(14,2);
    initial_capital numeric(14,2);
begin
    if not public.is_admin() then raise exception 'Acceso denegado'; end if;
    select coalesce(sum(case when direction = 'in' then amount else -amount end), 0)
    into opening_cash from public.cash_movements where created_at < day_start;
    select coalesce(sum(case when direction = 'in' then amount else -amount end), 0)
    into day_delta from public.cash_movements where created_at >= day_start and created_at < day_end;
    select coalesce(sum(total),0), coalesce(sum(cost_total),0)
    into day_revenue, day_cost from public.invoices where created_at >= day_start and created_at < day_end;
    select day_revenue + coalesce(sum(amount),0) into day_revenue
    from public.cash_movements
    where kind = 'operating_income' and created_at >= day_start and created_at < day_end;
    select coalesce(sum(amount),0) into day_expenses from public.expenses
    where created_at >= day_start and created_at < day_end;
    select coalesce(sum(amount),0) into contributions from public.cash_movements
    where kind = 'capital_contribution';
    select coalesce(sum(total - cost_total),0) into retained_profit from public.invoices;
    select retained_profit + coalesce(sum(amount),0) into retained_profit
    from public.cash_movements where kind = 'operating_income';
    select retained_profit - coalesce(sum(amount),0) into retained_profit from public.expenses;
    select coalesce(sum(balance),0) into liability_total from public.debts;
    select opening_capital into initial_capital from public.company_settings where id = true;
    return jsonb_build_object(
        'opening_cash', opening_cash,
        'closing_cash', opening_cash + day_delta,
        'revenue', day_revenue,
        'cost_of_goods', day_cost,
        'expenses_total', day_expenses,
        'daily_profit', day_revenue - day_cost - day_expenses,
        'net_worth', coalesce(initial_capital,0) + contributions + retained_profit - liability_total,
        'opening_capital', coalesce(initial_capital,0)
    );
end;
$$;

revoke all on function public.record_expense(text,text,numeric) from public, anon;
revoke all on function public.record_capital_contribution(text,numeric) from public, anon;
revoke all on function public.record_operating_income(text,numeric) from public, anon;
revoke all on function public.set_opening_capital(numeric) from public, anon;
revoke all on function public.record_debt(text,text,numeric,date) from public, anon;
revoke all on function public.repay_debt(uuid,numeric,text) from public, anon;
revoke all on function public.create_invoice(uuid,jsonb,text,numeric) from public, anon;
revoke all on function public.record_invoice_payment(uuid,numeric,text) from public, anon;
revoke all on function public.get_financial_totals(date,text) from public, anon;
grant execute on function public.record_expense(text,text,numeric) to authenticated;
grant execute on function public.record_capital_contribution(text,numeric) to authenticated;
grant execute on function public.record_operating_income(text,numeric) to authenticated;
grant execute on function public.set_opening_capital(numeric) to authenticated;
grant execute on function public.record_debt(text,text,numeric,date) to authenticated;
grant execute on function public.repay_debt(uuid,numeric,text) to authenticated;
grant execute on function public.create_invoice(uuid,jsonb,text,numeric) to authenticated;
grant execute on function public.record_invoice_payment(uuid,numeric,text) to authenticated;
grant execute on function public.get_financial_totals(date,text) to authenticated;

grant usage on schema public to authenticated;
grant select on public.user_roles to authenticated;
grant select on public.company_settings, public.clients, public.products,
    public.invoices, public.invoice_items, public.cash_movements, public.invoice_payments,
    public.expenses, public.debts, public.debt_payments to authenticated;
grant insert on public.clients, public.products to authenticated;
