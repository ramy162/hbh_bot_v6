"""Habesha Build Hub — Keyboard Builders v4
Changes:
  • Every flow step now has Cancel + Main Menu buttons
  • lead_kb includes /getfile instruction
  • quote_confirm_kb has Cancel + Main Menu
  • New: proforma_confirm_kb for supplier file upload
  • New: po_file_or_text_kb — buyer can choose to attach a file to their PO
  • back_buyer / back_supplier always show on dead-end screens
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import BUYER_TYPES, CITIES, TIMELINES, PROJECT_TYPES

def kb(rows):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text=label, callback_data=data) for label, data in row]
        for row in rows
    ])

# ── Universal navigation rows (reused everywhere) ─────────────────────────────
def _cancel_main_buyer():
    return [("❌ Cancel", "po:cancel"), ("🏠 Main Menu", "menu:main")]

def _cancel_main_supplier():
    return [("❌ Cancel", "quote:cancel"), ("🏭 My Menu", "smenu:main")]

def back_buyer():
    return kb([[("🏠 Main Menu", "menu:main")]])

def back_supplier():
    return kb([[("🏭 My Menu", "smenu:main")]])

def back_admin():
    return kb([[("🔙 Admin Menu", "adm:home")]])

def _get_cats():
    from models.database import get_category_map
    return get_category_map()

# ── BUYER ──────────────────────────────────────────────────────────────────────

def buyer_type_kb():
    rows = [[( v, f"btype:{k}")] for k, v in BUYER_TYPES.items()]
    rows.append([("❌ Cancel", "menu:main")])
    return kb(rows)

def city_kb(prefix="city"):
    rows = [CITIES[i:i+3] for i in range(0, len(CITIES), 3)]
    result = [[(c, f"{prefix}:{c}") for c in row] for row in rows]
    return kb(result)

def buyer_main_menu_kb():
    return kb([
        [("📋 New Purchase Order", "menu:po"),   ("📊 Upload BOQ",  "menu:boq")],
        [("💰 Material Prices",    "menu:prices"),("📁 My Orders",  "menu:mypos")],
        [("👤 My Profile",         "menu:profile"),("📞 Support",   "menu:support")],
    ])

def multi_cat_kb(selected: list, prefix="pocat", done_label="✔️ Done — Continue"):
    """Multi-select keyboard with Cancel + Main Menu at bottom."""
    cats  = _get_cats()
    items = list(cats.items())
    rows  = [items[i:i+2] for i in range(0, len(items), 2)]
    btns  = []
    for row in rows:
        btns.append([
            (("✅ " if k in selected else "") + v, f"{prefix}:{k}")
            for k, v in row
        ])
    if selected:
        btns.append([(done_label, f"{prefix}:done")])
    btns.append([("❌ Cancel", "po:cancel"), ("🏠 Main Menu", "menu:main")])
    return kb(btns)

def timeline_kb():
    return kb([
        [("Today",               "timeline:today"),
         ("As soon as possible", "timeline:asap")],
        [("Within 3 days",       "timeline:urgent"),
         ("Within 1 week",       "timeline:week")],
        [("Within 2 weeks",      "timeline:twoweeks"),
         ("Flexible",            "timeline:flexible")],
        [("❌ Cancel", "po:cancel"), ("🏠 Main Menu", "menu:main")],
    ])

def skip_kb():
    """Budget step — skip or cancel."""
    return kb([
        [("⏭️ Skip", "skip:budget")],
        [("❌ Cancel", "po:cancel"), ("🏠 Main Menu", "menu:main")],
    ])

def po_file_kb():
    """After buyer types their detail — offer to attach a file or continue."""
    return kb([
        [("📎 Attach a file (Excel/Image)", "po:attach_file")],
        [("➡️ Continue without file",        "po:skip_file")],
        [("❌ Cancel", "po:cancel"), ("🏠 Main Menu", "menu:main")],
    ])

def po_confirm_kb():
    return kb([
        [("✅ Submit Order",  "po:confirm")],
        [("✏️ Start Over",   "po:edit"),   ("❌ Cancel", "po:cancel")],
        [("🏠 Main Menu",    "menu:main")],
    ])

def project_type_kb():
    items = list(PROJECT_TYPES.items())
    return kb([
        [(v, f"ptype:{k}") for k, v in items[:2]],
        [(v, f"ptype:{k}") for k, v in items[2:]],
        [("❌ Cancel", "boq:cancel"), ("🏠 Main Menu", "menu:main")],
    ])

def boq_confirm_kb():
    return kb([
        [("✅ Submit BOQ",   "boq:confirm")],
        [("❌ Cancel",        "boq:cancel"), ("🏠 Main Menu", "menu:main")],
    ])

def quotes_kb(quotes):
    rows = []
    for i, q in enumerate(quotes, 1):
        label = f"✅ Choose #{i} — {q['business_name']}"
        rows.append([(label, f"selectquote:{q['quote_id']}")])
    rows.append([("🏠 Main Menu", "menu:main")])
    return kb(rows)

def review_kb(supplier_id):
    return kb([
        [("⭐ 1", f"rev:{supplier_id}:1"), ("⭐⭐ 2", f"rev:{supplier_id}:2"),
         ("⭐⭐⭐ 3", f"rev:{supplier_id}:3")],
        [("⭐⭐⭐⭐ 4", f"rev:{supplier_id}:4"),
         ("⭐⭐⭐⭐⭐ 5", f"rev:{supplier_id}:5")],
        [("🏠 Main Menu", "menu:main")],
    ])

def price_cat_kb():
    cats  = _get_cats()
    items = list(cats.items())
    rows  = [items[i:i+2] for i in range(0, len(items), 2)]
    btns  = [[(v, f"price:{k}") for k, v in row] for row in rows]
    btns.append([("📊 All Materials", "price:all")])
    btns.append([("🏠 Main Menu", "menu:main")])
    return kb(btns)

# ── SUPPLIER ───────────────────────────────────────────────────────────────────

def supplier_menu_kb():
    return kb([
        [("🔔 Active Leads",  "smenu:leads"),    ("📊 Dashboard",   "smenu:dashboard")],
        [("👤 My Profile",    "smenu:profile"),  ("✅ Get Verified", "smenu:verify")],
        [("📞 Support",       "smenu:support")],
    ])

def supplier_cat_kb(selected=None, prefix="scat"):
    return multi_cat_kb(
        selected or [], prefix=prefix,
        done_label="✔️ Save Categories"
    )

def lead_kb(po_id):
    """Shown to supplier when they receive a new PO lead."""
    return kb([
        [("📤 Submit Quote / Proforma", f"quoterpo:{po_id}")],
        [("⏭️ Skip this lead",           f"skiplead:{po_id}")],
        [("🏭 My Menu",                  "smenu:main")],
    ])

def quote_type_kb(po_id):
    """Supplier chooses: type a quote OR send a proforma file."""
    return kb([
        [("✏️ Type my quote",              f"qtype:text:{po_id}")],
        [("📎 Send proforma file (Excel/Image)", f"qtype:file:{po_id}")],
        [("❌ Cancel", "quote:cancel"), ("🏭 My Menu", "smenu:main")],
    ])

def quote_confirm_kb():
    return kb([
        [("✅ Submit Quote",  "quote:confirm")],
        [("✏️ Re-enter",     "quote:edit"),  ("❌ Cancel", "quote:cancel")],
        [("🏭 My Menu",      "smenu:main")],
    ])

def proforma_confirm_kb():
    """Confirm sending a proforma file."""
    return kb([
        [("✅ Send this proforma", "proforma:confirm")],
        [("❌ Cancel",              "proforma:cancel"), ("🏭 My Menu", "smenu:main")],
    ])

def license_kb():
    return kb([
        [("✅ Yes — I'll upload it",  "license:yes")],
        [("⏳ Applied / pending",     "license:pending")],
        [("❌ Not registered yet",    "license:no")],
        [("🏭 My Menu",               "smenu:main")],
    ])

# ── ADMIN ──────────────────────────────────────────────────────────────────────

def admin_menu_kb():
    return kb([
        [("📊 Stats",         "adm:stats"),    ("👥 Buyers",      "adm:buyers")],
        [("🏭 Suppliers",     "adm:suppliers"),("📋 Open POs",    "adm:pos")],
        [("💰 Manage Prices", "adm:prices"),   ("📦 BOQ Queue",   "adm:boqs")],
        [("✅ Verify",        "adm:verify"),    ("📂 Categories",  "adm:cats")],
        [("📢 Broadcast",     "adm:broadcast")],
    ])

def verify_action_kb(supplier_id):
    return kb([
        [("✅ Approve", f"adm_verify:{supplier_id}:approve"),
         ("❌ Reject",  f"adm_verify:{supplier_id}:reject")],
        [("🔙 Admin Menu", "adm:home")],
    ])

def price_mgmt_kb(prices):
    rows = []
    for p in prices:
        label = f"{p['material_type']} · {p['brand']} · {p['price_etb']:,.0f} ETB/{p['unit']}"
        rows.append([(f"✏️ {label}", f"adm_price:edit:{p['price_id']}")])
        rows.append([("🗑️ Delete", f"adm_price:del:{p['price_id']}")])
    rows.append([("➕ Add New Price",    "adm_price:add"),
                 ("📎 Upload CSV/Excel", "adm_price:upload")])
    rows.append([("🔙 Admin Menu", "adm:home")])
    return kb(rows)

def cat_mgmt_kb(cats):
    rows = []
    for c in cats:
        status = "✅" if c['is_active'] else "🚫"
        rows.append([(f"{status} {c['label']}", f"adm_cat:toggle:{c['cat_id']}")])
    rows.append([("➕ Add Category", "adm_cat:add"), ("🔙 Admin Menu", "adm:home")])
    return kb(rows)
