"""Habesha Build Hub — Message Templates v3
PO terminology throughout. Phone privacy: shows only first 4 digits.
"""
import json
from datetime import datetime
from config import BUYER_TYPES, TIMELINES, BUDGETS

def _cat_map():
    from models.database import get_category_map
    return get_category_map()

def _fmt_cats(cats_json):
    try:
        keys = json.loads(cats_json) if isinstance(cats_json, str) else cats_json
    except Exception:
        return str(cats_json)
    cm = _cat_map()
    return ", ".join(cm.get(k, k) for k in keys) if keys else "—"

# Public alias so handlers can import without the underscore
fmt_cats = _fmt_cats

def _mask_phone(phone):
    """Show only first 4 digits: 0911 ******"""
    if not phone: return "—"
    p = str(phone).strip()
    return p[:4] + " " + ("*" * max(0, len(p)-4)) if len(p) > 4 else p

# ── PO ─────────────────────────────────────────────────────────────────────────

def fmt_po(po, include_id=True):
    header = f"📋 *{po['po_code']}*\n" if include_id else ""
    tl  = TIMELINES.get(po.get('timeline',''), po.get('timeline','—'))
    bgt = BUDGETS.get(po.get('budget_range',''), po.get('budget_range','Not specified'))
    return (
        f"{header}"
        f"📦 *Materials:* {_fmt_cats(po.get('categories','[]'))}\n"
        f"🔍 *Detail:* {po.get('material_detail','—')}\n"
        f"📐 *Quantity:* {po.get('quantity','—')} {po.get('unit','')}\n"
        f"📍 *Location:* {po.get('location','—')}\n"
        f"⏱️ *Needed:* {tl}\n"
        f"💰 *Budget:* {bgt}\n"
        f"📝 *Notes:* {po.get('notes','None') or 'None'}\n"
        f"📊 *Status:* {po.get('status','open').upper()} | "
        f"💬 Quotes: {po.get('quotes_count',0)}"
    )

def fmt_po_lead(po, buyer):
    """Lead notification sent to supplier — concise, useful only."""
    tl  = TIMELINES.get(po.get('timeline',''), po.get('timeline',''))
    bgt = BUDGETS.get(po.get('budget_range',''), po.get('budget_range',''))
    btype = BUYER_TYPES.get(buyer.get('buyer_type',''), buyer.get('buyer_type',''))
    return (
        f"🔔 *New Purchase Order*\n"
        f"{'─'*28}\n"
        f"🆔 {po['po_code']}\n"
        f"📦 *{_fmt_cats(po.get('categories','[]'))}*\n"
        f"🔍 {po.get('material_detail','—')}\n"
        f"📐 Qty: *{po.get('quantity','—')} {po.get('unit','')}*\n"
        f"📍 {po.get('location','—')}\n"
        f"⏱️ {tl}  ·  💰 {bgt}\n"
        f"👤 {btype}\n"
        f"{'─'*28}\n"
        f"_via Habesha Build Hub_"
    )

def fmt_quotes(quotes, po):
    cats  = _fmt_cats(po.get('categories','[]'))
    lines = [
        f"📊 *Quotes — {po['po_code']}*",
        f"_{cats} · {po['quantity']} {po.get('unit','')}_ ",
        "─"*30,
    ]
    medals = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣"]
    for i, q in enumerate(quotes):
        badge = " ✅" if q.get('verified') else ""
        stars = "⭐"*round(q['score']) if q.get('score') else "New"
        lines.append(
            f"\n{medals[i]} *{q['business_name']}*{badge}\n"
            f"   💵 {q['unit_price']:,.0f} ETB/unit  ·  Total: {q['total_price']:,.0f} ETB\n"
            f"   🚚 {q['delivery_days']} day(s)  ·  {stars}\n"
            f"   📝 {q.get('notes') or '—'}"
        )
    lines.append("\n─"*15)
    if quotes:
        best  = min(quotes, key=lambda x: x['unit_price'])
        rated = max(quotes, key=lambda x: x.get('score') or 0)
        lines.append(f"💡 Lowest price: *{best['business_name']}*")
        if rated['supplier_id'] != best['supplier_id']:
            lines.append(f"⭐ Best rated: *{rated['business_name']}*")
    lines.append("\n_Select a supplier below to connect directly._")
    return "\n".join(lines)

def fmt_supplier_dashboard(s):
    stars    = "⭐"*round(s.get('score',0)) if s.get('score') else "No ratings yet"
    resp_pct = 0
    if s.get('leads_received',0) > 0:
        resp_pct = round(100*s.get('leads_responded',0)/s['leads_received'])
    return (
        f"📊 *Your Dashboard*\n{'─'*30}\n"
        f"🏢 *Business:* {s.get('business_name','—')}\n"
        f"📦 *Supplies:* {_fmt_cats(s.get('categories','[]'))}\n"
        f"📍 *City:* {s.get('city','—')}\n"
        f"✅ *Verified:* {'Yes ✅' if s.get('verified') else 'No'}\n"
        f"🏆 *Score:* {s.get('score',0):.1f}/5.0  {stars}\n"
        f"📨 *Leads received:* {s.get('leads_received',0)}\n"
        f"📤 *Quotes sent:* {s.get('leads_responded',0)} ({resp_pct}%)\n"
        f"✅ *Orders done:* {s.get('orders_done',0)}\n"
    )

def fmt_price_report(prices, category=None):
    if category and category != "all":
        prices = [p for p in prices if p['material_type'].lower() == category.lower()]
    if not prices:
        return "No price data available for this category yet."
    lines = [
        f"💰 *Material Prices — Addis Ababa*",
        f"📅 {datetime.now().strftime('%d %b %Y')}",
        "─"*30,
    ]
    cur = None
    for p in prices:
        if p['material_type'] != cur:
            cur = p['material_type']
            lines.append(f"\n*{cur}*")
        lines.append(f"  • {p['brand']} — {p['price_etb']:,.0f} ETB/{p['unit']}")
    lines.append(f"\n{'─'*30}\n_Source: HBH Survey · Prices may vary by supplier_")
    return "\n".join(lines)

def fmt_platform_stats(s):
    return (
        f"👥 Buyers: *{s['buyers']}*\n"
        f"🏭 Suppliers: *{s['suppliers']}* ({s['verified']} verified)\n"
        f"📋 Purchase Orders: *{s['total_pos']}* ({s['open_pos']} open)\n"
        f"💬 Quotes: *{s['total_quotes']}*\n"
        f"📊 BOQ Jobs: *{s['total_boqs']}*"
    )

def fmt_boq_confirm(boq):
    return (
        f"✅ *BOQ Received!*\n{'─'*26}\n"
        f"🆔 `{boq['boq_code']}`\n"
        f"📄 {boq.get('file_name','—')}\n"
        f"🏗️ {boq.get('project_type','—')}\n"
        f"📋 {boq.get('scope','—')}\n{'─'*26}\n"
        f"A specialist will review within *2 hours* and confirm the fee.\n"
        f"📬 We'll message you here."
    )

# ── CONNECTION MESSAGE ─────────────────────────────────────────────────────────

def fmt_buyer_intro(supplier, quote, po):
    """Sent to buyer after selecting a supplier — full direct introduction."""
    tg = f"@{supplier['tg_username']}" if supplier.get('tg_username') else "_(no username set)_"
    return (
        f"🤝 *You're connected!*\n{'─'*28}\n\n"
        f"You selected *{supplier.get('business_name','—')}*\n\n"
        f"📱 *Phone:* {supplier.get('phone','—')}\n"
        f"💬 *Telegram:* {tg}\n\n"
        f"📋 *PO:* `{po['po_code']}`\n"
        f"💵 *Price agreed:* {quote['unit_price']:,.0f} ETB/unit\n"
        f"🚚 *Delivery:* {quote['delivery_days']} day(s)\n\n"
        f"_Contact them directly to confirm delivery details._\n\n"
        f"_Connection made via Habesha Build Hub_ 🏗️"
    )

def fmt_supplier_selected(buyer, po):
    """Sent to supplier when selected by buyer."""
    tg = f"@{buyer.get('tg_username','')}" if buyer.get('tg_username') else "_(no username)_"
    return (
        f"🎉 *Your quote was selected!*\n{'─'*28}\n\n"
        f"A buyer chose you for *{po.get('po_code','')}*\n\n"
        f"👤 *Buyer:* {buyer.get('name','—')}\n"
        f"📱 *Phone:* {buyer.get('phone','—')}\n"
        f"💬 *Telegram:* {tg}\n\n"
        f"_Contact them to confirm delivery details._\n\n"
        f"_Order placed via Habesha Build Hub_ 🏗️"
    )

def fmt_new_quote_alert(po, supplier, quote):
    """Sent to buyer instantly when supplier submits a quote — minimal & useful."""
    return (
        f"💬 *New quote received!*\n\n"
        f"*{supplier.get('business_name','—')}* quoted for your order "
        f"`{po.get('po_code','')}`\n\n"
        f"💵 {quote['unit_price']:,.0f} ETB/unit  ·  🚚 {quote['delivery_days']} day(s)\n\n"
        f"_Open your order to compare all quotes._"
    )

# ── WELCOME ────────────────────────────────────────────────────────────────────

BUYER_WELCOME = (
    "ሰላም! 👋 *Welcome to Habesha Build Hub* 🏗️\n\n"
    "Ethiopia's free construction procurement platform.\n\n"
    "• Submit purchase orders — get quotes in hours\n"
    "• Compare supplier prices side by side\n"
    "• Get BOQ cost estimates\n"
    "• Check real market prices\n\n"
    "*100% free — no fees, ever.*\n\n"
    "What best describes you?"
)

SUPPLIER_WELCOME = (
    "ሰላም! 👋 *Welcome to Habesha Build Hub — Suppliers* 🏭\n\n"
    "Receive qualified buyer purchase orders directly on Telegram.\n\n"
    "✅ *Completely free — unlimited leads, no subscription needed.*\n\n"
    "Let's set up your profile.\n\n"
    "*What do you supply?* _(Select all that apply)_"
)
