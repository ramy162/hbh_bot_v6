"""
Habesha Build Hub — Database Layer v3
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Changes from v2:
  • RFQ renamed → purchase_orders (PO) throughout
  • supplier categories = JSON array (multi-category)
  • categories table — admin-managed, no longer hardcoded in config
  • price_reports: versioned, soft-delete, admin-editable
  • quotes: duplicate prevention, buyer instant-notify flag
  • platform_events table for lightweight audit log
  • All free — no tiers, no limits stored in DB
"""

import sqlite3, os, json, random, string
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'hbh.db')


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # concurrent reads safe
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_connection()
    c = conn.cursor()
    c.executescript("""
    -- ── CATEGORIES (admin-managed) ──────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS categories (
        cat_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        key         TEXT UNIQUE NOT NULL,
        label       TEXT NOT NULL,
        emoji       TEXT DEFAULT '📦',
        sort_order  INTEGER DEFAULT 99,
        is_active   INTEGER DEFAULT 1,
        created_at  TEXT DEFAULT (datetime('now'))
    );

    -- ── BUYERS ──────────────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS buyers (
        buyer_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE NOT NULL,
        tg_username TEXT,
        name        TEXT,
        phone       TEXT,
        buyer_type  TEXT,
        city        TEXT,
        verified    INTEGER DEFAULT 0,
        po_count    INTEGER DEFAULT 0,
        created_at  TEXT DEFAULT (datetime('now')),
        last_active TEXT DEFAULT (datetime('now'))
    );

    -- ── SUPPLIERS ───────────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS suppliers (
        supplier_id     INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id     INTEGER UNIQUE NOT NULL,
        tg_username     TEXT,
        business_name   TEXT,
        phone           TEXT,
        categories      TEXT DEFAULT '[]',   -- JSON array of category keys
        city            TEXT,
        verified        INTEGER DEFAULT 0,
        score           REAL DEFAULT 0.0,
        leads_received  INTEGER DEFAULT 0,
        leads_responded INTEGER DEFAULT 0,
        orders_done     INTEGER DEFAULT 0,
        created_at      TEXT DEFAULT (datetime('now')),
        last_active     TEXT DEFAULT (datetime('now'))
    );

    -- ── PURCHASE ORDERS (was: rfqs) ─────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS purchase_orders (
        po_id           INTEGER PRIMARY KEY AUTOINCREMENT,
        po_code         TEXT UNIQUE,
        buyer_id        INTEGER REFERENCES buyers(buyer_id),
        categories      TEXT DEFAULT '[]',
        material_detail TEXT,
        po_file_id      TEXT,
        po_file_name    TEXT,
        quantity        TEXT,
        unit            TEXT,
        location        TEXT,
        timeline        TEXT,
        budget_range    TEXT,
        notes           TEXT,
        status          TEXT DEFAULT 'open',
        quotes_count    INTEGER DEFAULT 0,
        created_at      TEXT DEFAULT (datetime('now')),
        expires_at      TEXT
    );

    -- ── QUOTES ──────────────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS quotes (
        quote_id        INTEGER PRIMARY KEY AUTOINCREMENT,
        po_id           INTEGER REFERENCES purchase_orders(po_id),
        supplier_id     INTEGER REFERENCES suppliers(supplier_id),
        unit_price      REAL,
        total_price     REAL,
        delivery_days   INTEGER,
        notes           TEXT,
        proforma_file_id   TEXT,
        proforma_file_name TEXT,
        status          TEXT DEFAULT 'pending',
        buyer_notified  INTEGER DEFAULT 0,
        submitted_at    TEXT DEFAULT (datetime('now'))
    );

    -- ── BOQ JOBS ────────────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS boq_jobs (
        boq_id          INTEGER PRIMARY KEY AUTOINCREMENT,
        boq_code        TEXT UNIQUE,
        buyer_id        INTEGER REFERENCES buyers(buyer_id),
        file_id         TEXT,
        file_name       TEXT,
        project_type    TEXT,
        scope           TEXT,
        status          TEXT DEFAULT 'received',
        notes           TEXT,
        created_at      TEXT DEFAULT (datetime('now'))
    );

    -- ── REVIEWS ─────────────────────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS reviews (
        review_id       INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_id     INTEGER REFERENCES suppliers(supplier_id),
        buyer_id        INTEGER REFERENCES buyers(buyer_id),
        score           INTEGER CHECK(score BETWEEN 1 AND 5),
        comment         TEXT,
        created_at      TEXT DEFAULT (datetime('now'))
    );

    -- ── PRICE REPORTS (versioned) ────────────────────────────────────────────
    CREATE TABLE IF NOT EXISTS price_reports (
        price_id        INTEGER PRIMARY KEY AUTOINCREMENT,
        material_type   TEXT NOT NULL,
        brand           TEXT NOT NULL,
        unit            TEXT NOT NULL,
        price_etb       REAL NOT NULL,
        city            TEXT DEFAULT 'Addis Ababa',
        source          TEXT DEFAULT 'Admin',
        is_active       INTEGER DEFAULT 1,
        uploaded_by     INTEGER,            -- admin telegram_id
        batch_id        TEXT,               -- groups bulk-upload rows
        reported_date   TEXT DEFAULT (datetime('now'))
    );

    -- ── PLATFORM EVENTS (lightweight audit log) ──────────────────────────────
    CREATE TABLE IF NOT EXISTS platform_events (
        event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type  TEXT,   -- po_created / quote_submitted / po_closed / etc.
        actor_type  TEXT,   -- buyer / supplier / admin
        actor_id    INTEGER,
        ref_id      INTEGER,
        meta        TEXT,   -- JSON blob
        created_at  TEXT DEFAULT (datetime('now'))
    );
    """)

    # ── Seed categories ──────────────────────────────────────────────────────
    c.execute("SELECT COUNT(*) FROM categories")
    if c.fetchone()[0] == 0:
        cats = [
            ("cement",     "🪨 Cement",               1),
            ("rebar",      "🔩 Rebar / Steel",         2),
            ("sand",       "🏜️ Sand & Aggregate",      3),
            ("tiles",      "🔲 Tiles & Finishing",     4),
            ("electrical", "🔌 Electrical & Plumbing", 5),
            ("equipment",  "🏗️ Equipment Rental",      6),
            ("boq",        "📋 BOQ / QS Service",      7),
            ("contractor", "🏠 Contractor Services",   8),
            ("other",      "📦 Other",                 9),
        ]
        for key, label, order in cats:
            emoji = label.split()[0]
            c.execute(
                "INSERT INTO categories (key,label,emoji,sort_order) VALUES (?,?,?,?)",
                (key, label, emoji, order)
            )

    # ── Seed prices (only if empty) ──────────────────────────────────────────
    c.execute("SELECT COUNT(*) FROM price_reports WHERE is_active=1")
    if c.fetchone()[0] == 0:
        seed = [
            ("Cement",    "Derba",              "bag (50kg)", 425.0),
            ("Cement",    "Messebo",            "bag (50kg)", 418.0),
            ("Cement",    "Habesha",            "bag (50kg)", 412.0),
            ("Rebar",     "10mm",               "kg",          88.0),
            ("Rebar",     "12mm",               "kg",          91.0),
            ("Rebar",     "16mm",               "kg",          94.0),
            ("Rebar",     "20mm",               "kg",          97.0),
            ("Sand",      "River sand",         "m³",        1250.0),
            ("Aggregate", 'Crushed stone 3/4"', "m³",        1450.0),
            ("Tiles",     "Ceramic 30x30",      "m²",         320.0),
            ("Tiles",     "Porcelain 60x60",    "m²",         580.0),
            ("Paint",     "Crown exterior 20L", "bucket",    2100.0),
        ]
        c.executemany(
            "INSERT INTO price_reports (material_type,brand,unit,price_etb,source,batch_id) "
            "VALUES (?,?,?,?,'Seed','seed-001')",
            seed
        )

    conn.commit()
    conn.close()
    print(f"✅ Database initialised at {DB_PATH}")


# ── CATEGORIES ─────────────────────────────────────────────────────────────────

def get_active_categories():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM categories WHERE is_active=1 ORDER BY sort_order"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_category_map():
    """Returns {key: label} dict — replaces hardcoded MATERIAL_CATEGORIES."""
    return {c['key']: c['label'] for c in get_active_categories()}

def add_category(key, label, emoji='📦', sort_order=99):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO categories (key,label,emoji,sort_order) VALUES (?,?,?,?)",
            (key.lower().strip(), label.strip(), emoji, sort_order)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def edit_category(cat_id, **kwargs):
    conn = get_connection()
    sets = ', '.join(f"{k}=?" for k in kwargs)
    conn.execute(f"UPDATE categories SET {sets} WHERE cat_id=?",
                 list(kwargs.values()) + [cat_id])
    conn.commit(); conn.close()

def archive_category(cat_id):
    conn = get_connection()
    conn.execute("UPDATE categories SET is_active=0 WHERE cat_id=?", (cat_id,))
    conn.commit(); conn.close()


# ── BUYERS ─────────────────────────────────────────────────────────────────────

def get_buyer(telegram_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM buyers WHERE telegram_id=?", (telegram_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_buyer_by_id(buyer_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM buyers WHERE buyer_id=?", (buyer_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def upsert_buyer(telegram_id, **kwargs):
    buyer = get_buyer(telegram_id)
    conn  = get_connection()
    if buyer:
        sets = ', '.join(f"{k}=?" for k in kwargs)
        conn.execute(
            f"UPDATE buyers SET {sets}, last_active=datetime('now') WHERE telegram_id=?",
            list(kwargs.values()) + [telegram_id]
        )
    else:
        kwargs['telegram_id'] = telegram_id
        cols = ', '.join(kwargs.keys())
        ph   = ', '.join(['?'] * len(kwargs))
        conn.execute(f"INSERT INTO buyers ({cols}) VALUES ({ph})", list(kwargs.values()))
    conn.commit(); conn.close()


# ── SUPPLIERS ──────────────────────────────────────────────────────────────────

def get_supplier(telegram_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM suppliers WHERE telegram_id=?", (telegram_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_supplier_by_id(supplier_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM suppliers WHERE supplier_id=?", (supplier_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def upsert_supplier(telegram_id, **kwargs):
    if 'categories' in kwargs and isinstance(kwargs['categories'], list):
        kwargs['categories'] = json.dumps(kwargs['categories'])
    supplier = get_supplier(telegram_id)
    conn     = get_connection()
    if supplier:
        sets = ', '.join(f"{k}=?" for k in kwargs)
        conn.execute(
            f"UPDATE suppliers SET {sets}, last_active=datetime('now') WHERE telegram_id=?",
            list(kwargs.values()) + [telegram_id]
        )
    else:
        kwargs['telegram_id'] = telegram_id
        cols = ', '.join(kwargs.keys())
        ph   = ', '.join(['?'] * len(kwargs))
        conn.execute(f"INSERT INTO suppliers ({cols}) VALUES ({ph})", list(kwargs.values()))
    conn.commit(); conn.close()

def get_supplier_categories(telegram_id):
    s = get_supplier(telegram_id)
    if not s: return []
    try:    return json.loads(s.get('categories', '[]'))
    except: return []

def get_suppliers_matching_categories(categories: list):
    """Return suppliers who supply ANY of the given categories."""
    conn = get_connection()
    all_rows = conn.execute("SELECT * FROM suppliers").fetchall()
    conn.close()
    matched = []
    for row in all_rows:
        row = dict(row)
        try:
            sup_cats = set(json.loads(row.get('categories', '[]')))
        except Exception:
            sup_cats = set()
        if sup_cats & set(categories):
            matched.append(row)
    # Sort by score desc
    matched.sort(key=lambda x: x.get('score', 0), reverse=True)
    return matched

def update_supplier_score(supplier_id):
    conn = get_connection()
    avg  = conn.execute(
        "SELECT AVG(score) FROM reviews WHERE supplier_id=?", (supplier_id,)
    ).fetchone()[0]
    if avg:
        conn.execute("UPDATE suppliers SET score=? WHERE supplier_id=?", (round(avg, 1), supplier_id))
        conn.commit()
    conn.close()


# ── PURCHASE ORDERS ────────────────────────────────────────────────────────────

def create_po(buyer_id, **kwargs):
    code = 'PO-' + ''.join(random.choices(string.digits, k=6))
    if 'categories' in kwargs and isinstance(kwargs['categories'], list):
        kwargs['categories'] = json.dumps(kwargs['categories'])
    conn = get_connection()
    conn.execute(
        """INSERT INTO purchase_orders
           (po_code,buyer_id,categories,material_detail,po_file_id,po_file_name,
            quantity,unit,location,timeline,budget_range,notes,expires_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,datetime('now','+72 hours'))""",
        (code, buyer_id,
         kwargs.get('categories','[]'),
         kwargs.get('material_detail'),
         kwargs.get('po_file_id'),
         kwargs.get('po_file_name'),
         kwargs.get('quantity'),
         kwargs.get('unit'),
         kwargs.get('location'),
         kwargs.get('timeline'),
         kwargs.get('budget_range'),
         kwargs.get('notes'))
    )
    conn.commit()
    po = dict(conn.execute("SELECT * FROM purchase_orders WHERE po_code=?", (code,)).fetchone())
    conn.close()
    log_event('po_created', 'buyer', buyer_id, po['po_id'])
    return po

def get_po(po_id):
    conn = get_connection()
    row  = conn.execute("SELECT * FROM purchase_orders WHERE po_id=?", (po_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_buyer_pos(buyer_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM purchase_orders WHERE buyer_id=? ORDER BY created_at DESC LIMIT 10",
        (buyer_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_open_pos():
    conn = get_connection()
    rows = conn.execute(
        "SELECT p.*, b.name as buyer_name FROM purchase_orders p "
        "JOIN buyers b ON p.buyer_id=b.buyer_id "
        "WHERE p.status='open' ORDER BY p.created_at DESC LIMIT 20"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def close_po(po_id):
    conn = get_connection()
    conn.execute("UPDATE purchase_orders SET status='closed' WHERE po_id=?", (po_id,))
    conn.commit(); conn.close()


# ── QUOTES ─────────────────────────────────────────────────────────────────────

def create_quote(po_id, supplier_id, unit_price, total_price, delivery_days,
                 notes='', proforma_file_id=None, proforma_file_name=None):
    conn = get_connection()
    existing = conn.execute(
        "SELECT quote_id FROM quotes WHERE po_id=? AND supplier_id=?", (po_id, supplier_id)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE quotes SET unit_price=?,total_price=?,delivery_days=?,notes=?,"
            "proforma_file_id=?,proforma_file_name=?,"
            "submitted_at=datetime('now'),buyer_notified=0 "
            "WHERE po_id=? AND supplier_id=?",
            (unit_price, total_price, delivery_days, notes,
             proforma_file_id, proforma_file_name, po_id, supplier_id)
        )
        quote_id = existing[0]
    else:
        cur = conn.execute(
            "INSERT INTO quotes (po_id,supplier_id,unit_price,total_price,delivery_days,"
            "notes,proforma_file_id,proforma_file_name) VALUES (?,?,?,?,?,?,?,?)",
            (po_id, supplier_id, unit_price, total_price, delivery_days,
             notes, proforma_file_id, proforma_file_name)
        )
        quote_id = cur.lastrowid
        conn.execute(
            "UPDATE purchase_orders SET quotes_count=quotes_count+1 WHERE po_id=?", (po_id,)
        )
    conn.commit()
    q = dict(conn.execute("SELECT * FROM quotes WHERE quote_id=?", (quote_id,)).fetchone())
    conn.close()
    log_event('quote_submitted', 'supplier', supplier_id, po_id)
    return q

def get_po_quotes(po_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT q.*, s.business_name, s.score, s.verified, s.phone,
               s.telegram_id as supplier_tg_id, s.tg_username
        FROM quotes q
        JOIN suppliers s ON q.supplier_id=s.supplier_id
        WHERE q.po_id=? AND q.status != 'rejected'
        ORDER BY q.unit_price ASC
    """, (po_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def mark_buyer_notified(quote_id):
    conn = get_connection()
    conn.execute("UPDATE quotes SET buyer_notified=1 WHERE quote_id=?", (quote_id,))
    conn.commit(); conn.close()

def select_quote(quote_id):
    conn = get_connection()
    conn.execute("UPDATE quotes SET status='selected' WHERE quote_id=?", (quote_id,))
    q = dict(conn.execute("SELECT * FROM quotes WHERE quote_id=?", (quote_id,)).fetchone())
    conn.execute("UPDATE purchase_orders SET status='closed' WHERE po_id=?", (q['po_id'],))
    conn.commit(); conn.close()
    log_event('po_closed', 'buyer', None, q['po_id'])
    return q


# ── BOQ ────────────────────────────────────────────────────────────────────────

def create_boq_job(buyer_id, file_id, file_name, project_type, scope):
    code = 'BOQ-' + ''.join(random.choices(string.digits, k=5))
    conn = get_connection()
    conn.execute(
        "INSERT INTO boq_jobs (boq_code,buyer_id,file_id,file_name,project_type,scope) "
        "VALUES (?,?,?,?,?,?)",
        (code, buyer_id, file_id, file_name, project_type, scope)
    )
    conn.commit()
    job = dict(conn.execute("SELECT * FROM boq_jobs WHERE boq_code=?", (code,)).fetchone())
    conn.close()
    return job


# ── REVIEWS ────────────────────────────────────────────────────────────────────

def create_review(supplier_id, buyer_id, score, comment=''):
    conn = get_connection()
    conn.execute(
        "INSERT INTO reviews (supplier_id,buyer_id,score,comment) VALUES (?,?,?,?)",
        (supplier_id, buyer_id, score, comment)
    )
    conn.commit(); conn.close()
    update_supplier_score(supplier_id)


# ── PRICES ─────────────────────────────────────────────────────────────────────

def get_latest_prices():
    """One latest active price per material+brand."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT p1.* FROM price_reports p1
        WHERE p1.is_active=1
          AND p1.price_id=(
              SELECT p2.price_id FROM price_reports p2
              WHERE p2.material_type=p1.material_type AND p2.brand=p1.brand AND p2.is_active=1
              ORDER BY p2.reported_date DESC LIMIT 1
          )
        ORDER BY p1.material_type, p1.brand
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_active_prices():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM price_reports WHERE is_active=1 ORDER BY material_type,brand,reported_date DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_price(material_type, brand, unit, price_etb, source='Admin', admin_id=None, batch_id=None):
    conn = get_connection()
    conn.execute(
        "INSERT INTO price_reports (material_type,brand,unit,price_etb,source,uploaded_by,batch_id) "
        "VALUES (?,?,?,?,?,?,?)",
        (material_type.strip(), brand.strip(), unit.strip(),
         float(price_etb), source, admin_id, batch_id)
    )
    conn.commit(); conn.close()

def edit_price(price_id, new_price_etb):
    conn = get_connection()
    conn.execute(
        "UPDATE price_reports SET price_etb=?, reported_date=datetime('now') WHERE price_id=?",
        (float(new_price_etb), price_id)
    )
    conn.commit(); conn.close()

def delete_price(price_id):
    """Soft delete — keeps history."""
    conn = get_connection()
    conn.execute("UPDATE price_reports SET is_active=0 WHERE price_id=?", (price_id,))
    conn.commit(); conn.close()

def rollback_batch(batch_id):
    """Undo an entire bulk upload by batch ID."""
    conn = get_connection()
    conn.execute("UPDATE price_reports SET is_active=0 WHERE batch_id=?", (batch_id,))
    conn.commit(); conn.close()

def bulk_import_prices(rows: list[dict], admin_id=None) -> dict:
    """
    rows: list of {'material_type','brand','unit','price_etb'}
    Returns {'imported': N, 'skipped': N, 'errors': [...], 'batch_id': str}
    """
    import uuid
    batch_id  = str(uuid.uuid4())[:8]
    imported  = 0
    skipped   = 0
    errors    = []
    conn      = get_connection()
    for i, row in enumerate(rows):
        try:
            mat   = str(row.get('material_type','')).strip()
            brand = str(row.get('brand','')).strip()
            unit  = str(row.get('unit','')).strip()
            price = float(str(row.get('price_etb','')).replace(',',''))
            if not mat or not brand or not unit or price <= 0:
                skipped += 1
                continue
            conn.execute(
                "INSERT INTO price_reports (material_type,brand,unit,price_etb,source,uploaded_by,batch_id) "
                "VALUES (?,?,?,?,?,?,?)",
                (mat, brand, unit, price, 'Bulk Upload', admin_id, batch_id)
            )
            imported += 1
        except Exception as e:
            errors.append(f"Row {i+2}: {e}")
    conn.commit(); conn.close()
    return dict(imported=imported, skipped=skipped, errors=errors, batch_id=batch_id)


# ── EVENTS LOG ─────────────────────────────────────────────────────────────────

def log_event(event_type, actor_type, actor_id, ref_id, meta=None):
    try:
        conn = get_connection()
        conn.execute(
            "INSERT INTO platform_events (event_type,actor_type,actor_id,ref_id,meta) VALUES (?,?,?,?,?)",
            (event_type, actor_type, actor_id, ref_id, json.dumps(meta) if meta else None)
        )
        conn.commit(); conn.close()
    except Exception:
        pass   # logging must never crash the main flow


# ── STATS ──────────────────────────────────────────────────────────────────────

def get_platform_stats():
    conn = get_connection()
    def scalar(sql): return conn.execute(sql).fetchone()[0]
    s = dict(
        buyers          = scalar("SELECT COUNT(*) FROM buyers"),
        suppliers       = scalar("SELECT COUNT(*) FROM suppliers"),
        verified        = scalar("SELECT COUNT(*) FROM suppliers WHERE verified=1"),
        total_pos       = scalar("SELECT COUNT(*) FROM purchase_orders"),
        open_pos        = scalar("SELECT COUNT(*) FROM purchase_orders WHERE status='open'"),
        total_quotes    = scalar("SELECT COUNT(*) FROM quotes"),
        total_boqs      = scalar("SELECT COUNT(*) FROM boq_jobs"),
    )
    conn.close()
    return s
