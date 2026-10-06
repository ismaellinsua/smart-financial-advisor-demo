"""The database's tables and the changes applied to databases created by older versions.

`{pk}` and `{real}` are filled in by each engine (SQLite or PostgreSQL). Add columns at the end of MIGRATIONS and
one-off changes at the end of VERSIONED_MIGRATIONS; never edit or renumber one that has been applied.
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
    id {pk},
    sku TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'General',
    price {real} NOT NULL CHECK (price >= 0),
    cost {real} NOT NULL DEFAULT 0 CHECK (cost >= 0),
    stock INTEGER NOT NULL DEFAULT 0,
    min_stock INTEGER NOT NULL DEFAULT 0,
    track_stock INTEGER NOT NULL DEFAULT 1,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS customers (
    id {pk},
    name TEXT NOT NULL,
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    tax_id TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    address TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS sales (
    id {pk},
    number TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    customer_id INTEGER REFERENCES customers(id),
    payment_method TEXT NOT NULL,
    discount_pct {real} NOT NULL DEFAULT 0,
    tax_rate {real} NOT NULL DEFAULT 0,
    subtotal {real} NOT NULL,
    discount {real} NOT NULL,
    tax {real} NOT NULL,
    total {real} NOT NULL,
    status TEXT NOT NULL DEFAULT 'completada' CONSTRAINT ck_sales_status CHECK (status IN ('completada', 'anulada'))
);
CREATE TABLE IF NOT EXISTS sale_items (
    id {pk},
    sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    name TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price {real} NOT NULL,
    unit_cost {real} NOT NULL
);
CREATE TABLE IF NOT EXISTS invoices (
    id {pk},
    number TEXT UNIQUE NOT NULL,
    sale_id INTEGER UNIQUE NOT NULL REFERENCES sales(id),
    issued_at TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    customer_tax_id TEXT NOT NULL DEFAULT '',
    customer_address TEXT NOT NULL DEFAULT '',
    customer_email TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS appointments (
    id {pk},
    starts_at TEXT NOT NULL,
    duration_min INTEGER NOT NULL CHECK (duration_min > 0),
    customer_id INTEGER REFERENCES customers(id),
    customer_name TEXT NOT NULL DEFAULT '',
    product_id INTEGER REFERENCES products(id),
    notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pendiente' CONSTRAINT ck_appointments_status
        CHECK (status IN ('pendiente', 'completada', 'cancelada', 'no_presentado')),
    sale_id INTEGER REFERENCES sales(id),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cash_closings (
    id {pk},
    day TEXT NOT NULL,
    opening_float {real} NOT NULL DEFAULT 0,
    cash_sales {real} NOT NULL DEFAULT 0,
    expected_cash {real} NOT NULL,
    counted_cash {real} NOT NULL,
    difference {real} NOT NULL,
    total_sales {real} NOT NULL,
    sales_count INTEGER NOT NULL,
    breakdown TEXT NOT NULL DEFAULT '{{}}',
    notes TEXT NOT NULL DEFAULT '',
    closed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sale_payments (
    id {pk},
    sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    method TEXT NOT NULL,
    amount {real} NOT NULL,
    tendered {real} NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS promotions (
    id {pk},
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    value {real} NOT NULL DEFAULT 0,
    buy INTEGER NOT NULL DEFAULT 0,
    pay INTEGER NOT NULL DEFAULT 0,
    scope TEXT NOT NULL DEFAULT 'todo',
    target TEXT NOT NULL DEFAULT '',
    days TEXT NOT NULL DEFAULT '0123456',
    start_time TEXT NOT NULL DEFAULT '',
    end_time TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS loyalty_moves (
    id {pk},
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    sale_id INTEGER REFERENCES sales(id),
    points INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_payments_sale ON sale_payments(sale_id);
CREATE INDEX IF NOT EXISTS idx_loyalty_customer ON loyalty_moves(customer_id);
CREATE TABLE IF NOT EXISTS refunds (
    id {pk},
    number TEXT UNIQUE NOT NULL,
    sale_id INTEGER NOT NULL REFERENCES sales(id),
    created_at TEXT NOT NULL,
    user_name TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    method TEXT NOT NULL,
    base {real} NOT NULL,
    tax {real} NOT NULL,
    total {real} NOT NULL
);
CREATE TABLE IF NOT EXISTS refund_items (
    id {pk},
    refund_id INTEGER NOT NULL REFERENCES refunds(id) ON DELETE CASCADE,
    sale_item_id INTEGER NOT NULL REFERENCES sale_items(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    name TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    net_amount {real} NOT NULL,
    unit_cost {real} NOT NULL
);
CREATE TABLE IF NOT EXISTS credit_notes (
    id {pk},
    number TEXT UNIQUE NOT NULL,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    refund_id INTEGER UNIQUE NOT NULL REFERENCES refunds(id),
    issued_at TEXT NOT NULL,
    issued_by TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_refunds_sale ON refunds(sale_id);
CREATE TABLE IF NOT EXISTS dining_tables (
    id {pk},
    name TEXT NOT NULL,
    zone TEXT NOT NULL DEFAULT 'Sala',
    seats INTEGER NOT NULL DEFAULT 4,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS orders (
    id {pk},
    table_id INTEGER REFERENCES dining_tables(id),
    label TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'abierta' CONSTRAINT ck_orders_status
        CHECK (status IN ('abierta', 'cobrada', 'cancelada')),
    opened_at TEXT NOT NULL,
    opened_by TEXT NOT NULL DEFAULT '',
    guests INTEGER NOT NULL DEFAULT 0,
    closed_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS order_items (
    id {pk},
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    name TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    notes TEXT NOT NULL DEFAULT '',
    added_by TEXT NOT NULL DEFAULT '',
    added_at TEXT NOT NULL,
    kitchen TEXT NOT NULL DEFAULT 'pendiente' CONSTRAINT ck_order_items_kitchen
        CHECK (kitchen IN ('pendiente', 'preparando', 'listo', 'servido')),
    sale_id INTEGER REFERENCES sales(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_one_open_per_table ON orders(table_id) WHERE status = 'abierta';
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
CREATE TABLE IF NOT EXISTS suppliers (
    id {pk},
    name TEXT NOT NULL,
    tax_id TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS recurring_expenses (
    id {pk},
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    amount {real} NOT NULL,
    day_of_month INTEGER NOT NULL,
    method TEXT NOT NULL DEFAULT 'Transferencia',
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS purchase_orders (
    id {pk},
    number TEXT UNIQUE NOT NULL,
    supplier_id INTEGER REFERENCES suppliers(id),
    status TEXT NOT NULL DEFAULT 'borrador' CONSTRAINT ck_purchase_orders_status
        CHECK (status IN ('borrador', 'enviado', 'recibido', 'cancelado')),
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT '',
    received_at TEXT NOT NULL DEFAULT '',
    received_by TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    total {real} NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS purchase_items (
    id {pk},
    po_id INTEGER NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    name TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_cost {real} NOT NULL,
    received INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS expenses (
    id {pk},
    day TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    amount {real} NOT NULL,
    method TEXT NOT NULL DEFAULT 'Transferencia',
    supplier_id INTEGER REFERENCES suppliers(id),
    purchase_id INTEGER REFERENCES purchase_orders(id),
    recurring_id INTEGER REFERENCES recurring_expenses(id),
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_expenses_day ON expenses(day);
CREATE TABLE IF NOT EXISTS users (
    id {pk},
    username TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL CONSTRAINT ck_users_role CHECK (role IN ('admin', 'encargado', 'empleado')),
    secret_hash TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    lockouts INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT NOT NULL DEFAULT '',
    last_login TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    id {pk},
    happened_at TEXT NOT NULL,
    username TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_audit_happened ON audit_log(happened_at);
CREATE INDEX IF NOT EXISTS idx_sales_created ON sales(created_at);
CREATE INDEX IF NOT EXISTS idx_items_sale ON sale_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_appointments_start ON appointments(starts_at);
CREATE TABLE IF NOT EXISTS stock_moves (
    id {pk},
    product_id INTEGER NOT NULL REFERENCES products(id),
    delta INTEGER NOT NULL,
    stock_after INTEGER NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    user_name TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_stock_moves_product ON stock_moves(product_id);
CREATE TABLE IF NOT EXISTS recovery_codes (
    id {pk},
    user_id INTEGER NOT NULL REFERENCES users(id),
    code_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    used_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS locations (
    id {pk},
    name TEXT NOT NULL,
    address TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS location_stock (
    id {pk},
    location_id INTEGER NOT NULL REFERENCES locations(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    stock INTEGER NOT NULL DEFAULT 0,
    UNIQUE (location_id, product_id)
);
CREATE TABLE IF NOT EXISTS counters (
    series TEXT PRIMARY KEY,
    value INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id {pk},
    user_id INTEGER NOT NULL REFERENCES users(id),
    token_hash TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    ended_at TEXT NOT NULL DEFAULT '',
    user_agent TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS password_resets (
    id {pk},
    user_id INTEGER NOT NULL REFERENCES users(id),
    code_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    used_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS app_errors (
    id {pk},
    happened_at TEXT NOT NULL,
    ref TEXT NOT NULL,
    page TEXT NOT NULL DEFAULT '',
    username TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL,
    where_ TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_app_errors_happened ON app_errors(happened_at);
-- The ticket being rung up: a convenience, deliberately without a foreign key, so it can never stop the till.
CREATE TABLE IF NOT EXISTS pos_carts (
    user_id INTEGER PRIMARY KEY,
    cart TEXT NOT NULL DEFAULT '{{}}',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS billing_records (
    id {pk},
    kind TEXT NOT NULL,
    invoice_type TEXT NOT NULL DEFAULT '',
    number TEXT NOT NULL,
    issued_on TEXT NOT NULL,
    issuer_tax_id TEXT NOT NULL,
    tax_total TEXT NOT NULL DEFAULT '',
    amount_total TEXT NOT NULL DEFAULT '',
    breakdown TEXT NOT NULL DEFAULT '[]',
    previous_hash TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    hash TEXT UNIQUE NOT NULL,
    source TEXT,
    source_id INTEGER
);
CREATE TABLE IF NOT EXISTS schema_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sales_customer ON sales(customer_id);
CREATE INDEX IF NOT EXISTS idx_refunds_created ON refunds(created_at);
CREATE INDEX IF NOT EXISTS idx_refund_items_refund ON refund_items(refund_id);
CREATE INDEX IF NOT EXISTS idx_billing_source ON billing_records(source, source_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
-- Sales of one product (analytics), points of one sale (voids, returns), voided sales by period (accounting).
CREATE INDEX IF NOT EXISTS idx_items_product ON sale_items(product_id);
CREATE INDEX IF NOT EXISTS idx_loyalty_sale ON loyalty_moves(sale_id);
CREATE INDEX IF NOT EXISTS idx_sales_status ON sales(status, created_at);
CREATE INDEX IF NOT EXISTS idx_stock_moves_created ON stock_moves(created_at);
CREATE INDEX IF NOT EXISTS idx_password_resets_user ON password_resets(user_id);
CREATE INDEX IF NOT EXISTS idx_recovery_codes_user ON recovery_codes(user_id);
-- A cash closing that was reopened: kept whole, so the count, the difference and who closed it are never lost.
CREATE TABLE IF NOT EXISTS cash_reopenings (
    id {pk},
    day TEXT NOT NULL,
    location_id INTEGER,
    closing TEXT NOT NULL,
    reopened_by TEXT NOT NULL DEFAULT '',
    reopened_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS login_throttle (
    key TEXT PRIMARY KEY,
    fails TEXT NOT NULL DEFAULT '[]',
    blocked_until BIGINT NOT NULL DEFAULT 0,
    level INTEGER NOT NULL DEFAULT 0,
    updated BIGINT NOT NULL DEFAULT 0
)
"""

# Columns added after the first release, applied to existing databases on start-up.
MIGRATIONS = [
    ("customers", "address", "TEXT NOT NULL DEFAULT ''"),
    # Who did it: names are stored as text so backups restore cleanly into any team.
    ("sales", "user_name", "TEXT NOT NULL DEFAULT ''"),
    ("invoices", "issued_by", "TEXT NOT NULL DEFAULT ''"),
    ("appointments", "created_by", "TEXT NOT NULL DEFAULT ''"),
    ("cash_closings", "closed_by", "TEXT NOT NULL DEFAULT ''"),
    # Promotions, loyalty and the per-line share of the final base (exact analytics with any discount).
    ("sale_items", "line_discount", "{real} NOT NULL DEFAULT 0"),
    ("sale_items", "promo_name", "TEXT NOT NULL DEFAULT ''"),
    ("sale_items", "net_amount", "{real}"),
    ("sales", "promo_discount", "{real} NOT NULL DEFAULT 0"),
    ("sales", "loyalty_discount", "{real} NOT NULL DEFAULT 0"),
    ("sales", "points_redeemed", "INTEGER NOT NULL DEFAULT 0"),
    ("sales", "points_earned", "INTEGER NOT NULL DEFAULT 0"),
    ("products", "supplier_id", "INTEGER REFERENCES suppliers(id)"),
    ("sales", "voided_by", "TEXT NOT NULL DEFAULT ''"),
    ("sales", "voided_at", "TEXT"),
    # Two-step verification secret (TOTP) of administrators who turn it on.
    ("users", "totp_secret", "TEXT NOT NULL DEFAULT ''"),
    # Who authorised a manual discount above the staff limit.
    ("sales", "discount_approved_by", "TEXT NOT NULL DEFAULT ''"),
    # VAT per product (empty: the business default) and each sold or returned line's base, VAT and final price,
    # so tickets, invoices and returns break VAT down per rate. Prices include VAT (see _migrate_prices).
    ("products", "tax_rate", "{real}"),
    ("sale_items", "tax_rate", "{real}"),
    ("sale_items", "tax_amount", "{real}"),
    ("sale_items", "gross_amount", "{real}"),
    ("refund_items", "tax_rate", "{real}"),
    ("refund_items", "tax_amount", "{real}"),
    # Income tax withheld on invoices of professionals to companies (retención de IRPF).
    ("invoices", "irpf_rate", "{real} NOT NULL DEFAULT 0"),
    ("invoices", "irpf_amount", "{real} NOT NULL DEFAULT 0"),
    # Data protection: consent to marketing (and when it was given or withdrawn) and erasure.
    ("customers", "marketing_consent", "INTEGER NOT NULL DEFAULT 0"),
    ("customers", "consent_at", "TEXT NOT NULL DEFAULT ''"),
    ("customers", "anonymized_at", "TEXT NOT NULL DEFAULT ''"),
    # The supplier's invoice behind an expense, for the register of invoices received (deductible VAT).
    ("expenses", "invoice_number", "TEXT NOT NULL DEFAULT ''"),
    ("expenses", "issuer_tax_id", "TEXT NOT NULL DEFAULT ''"),
    ("expenses", "issuer_name", "TEXT NOT NULL DEFAULT ''"),
    ("expenses", "tax_rate", "{real}"),
    # Online booking: the customer's contact (erased CONTACT_DAYS after the appointment), party size and cancel link.
    ("appointments", "phone", "TEXT NOT NULL DEFAULT ''"),
    ("appointments", "email", "TEXT NOT NULL DEFAULT ''"),
    ("appointments", "people", "INTEGER NOT NULL DEFAULT 0"),
    ("appointments", "source", "TEXT NOT NULL DEFAULT 'equipo'"),
    ("appointments", "cancel_hash", "TEXT NOT NULL DEFAULT ''"),
    ("appointments", "reminded_at", "TEXT NOT NULL DEFAULT ''"),
    # Sales made on the offline till: its own id, so importing the same file twice never duplicates a sale.
    ("sales", "offline_id", "TEXT NOT NULL DEFAULT ''"),
    # Several locations (locales): where each sale, closing, table, stock move, order and person belongs.
    ("sales", "location_id", "INTEGER REFERENCES locations(id)"),
    ("cash_closings", "location_id", "INTEGER REFERENCES locations(id)"),
    ("dining_tables", "location_id", "INTEGER REFERENCES locations(id)"),
    ("stock_moves", "location_id", "INTEGER REFERENCES locations(id)"),
    ("purchase_orders", "location_id", "INTEGER REFERENCES locations(id)"),
    # A person pinned to a location that a restored copy no longer has is simply unpinned.
    ("users", "location_id", "INTEGER REFERENCES locations(id) ON DELETE SET NULL"),
    # The time step of the last two-step code accepted: the same code is never accepted twice.
    ("users", "totp_last_step", "INTEGER NOT NULL DEFAULT 0"),
    # Set when someone else chose this person's PIN: they must choose their own at the next sign-in.
    ("users", "must_change", "INTEGER NOT NULL DEFAULT 0"),
    # Orders imported from an online shop («shopify:1001»): importing the same file twice never duplicates them.
    ("sales", "external_ref", "TEXT NOT NULL DEFAULT ''"),
]

# One-off changes to existing data or column types, applied once each, in order, and recorded in
# `schema_migrations`. Add new ones at the end with the next number; never renumber or edit an applied one.
VERSIONED_MIGRATIONS = [
    (1, "importes exactos (NUMERIC) en PostgreSQL", "_money_to_numeric"),
    (2, "claves foráneas de locales y proveedores", "_add_foreign_keys"),
    (3, "valores permitidos en estados y roles", "_add_checks"),
]

# Allowed values of status-like columns (databases created since then have them in their tables already).
CHECKS = {
    "ck_sales_status": ("sales", "status IN ('completada', 'anulada')"),
    "ck_appointments_status": ("appointments", "status IN ('pendiente', 'completada', 'cancelada', 'no_presentado')"),
    "ck_orders_status": ("orders", "status IN ('abierta', 'cobrada', 'cancelada')"),
    "ck_order_items_kitchen": ("order_items", "kitchen IN ('pendiente', 'preparando', 'listo', 'servido')"),
    "ck_purchase_orders_status": ("purchase_orders", "status IN ('borrador', 'enviado', 'recibido', 'cancelado')"),
    "ck_users_role": ("users", "role IN ('admin', 'encargado', 'empleado')"),
}

# Foreign keys of columns added after the first release (databases created since then have them already).
# (table, column, referenced table, ON DELETE action)
ADDED_FOREIGN_KEYS = [
    ("products", "supplier_id", "suppliers", ""),
    ("sales", "location_id", "locations", ""),
    ("cash_closings", "location_id", "locations", ""),
    ("dining_tables", "location_id", "locations", ""),
    ("stock_moves", "location_id", "locations", ""),
    ("purchase_orders", "location_id", "locations", ""),
    ("users", "location_id", "locations", "ON DELETE SET NULL"),
]

# Insertion order respects foreign keys; deletion goes in reverse.
DATA_TABLES = ["locations", "suppliers", "products", "location_stock", "stock_moves", "customers", "sales", "sale_items", "invoices", "appointments", "cash_closings", "cash_reopenings",
               "sale_payments", "promotions", "loyalty_moves", "refunds", "refund_items", "credit_notes",
               "dining_tables", "orders", "order_items", "recurring_expenses", "purchase_orders",
               "purchase_items", "expenses", "billing_records"]
ALL_TABLES = ["settings", *DATA_TABLES]
# Tables any backup must have; newer ones are created when an older backup is opened.
CORE_TABLES = {"settings", "products", "customers", "sales", "sale_items"}

# Records a business must keep (invoices: 4 years for tax, 6 under the Commercial Code). Once real ones exist,
# nothing in the app may delete or replace them.
FISCAL_TABLES = ["sales", "invoices", "refunds", "credit_notes", "cash_closings", "billing_records"]
FISCAL_DATA_MESSAGE = ("Este negocio ya tiene ventas, facturas o cierres de caja reales y la ley obliga a conservarlos, "
                       "así que no se pueden borrar ni sustituir desde la app.")


# Billing records (VERI*FACTU) are append-only: the database itself refuses to change or delete them.
APPEND_ONLY_MESSAGE = "Los registros de facturación no se pueden modificar ni borrar"
