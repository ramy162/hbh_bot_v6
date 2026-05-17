"""
Habesha Build Hub — BUYER BOT v6
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
v6 changes:
  • All inline imports moved to top level (stability fix)
  • File preview via utils.files — images show as photos, docs as documents
  • /getfile shows actual file preview, not just downloads
  • Hardened upload validation (type check, graceful errors)
  • All fragile late-import patterns eliminated
"""

import logging, json
from telegram import Update, Bot
from telegram.error import TelegramError
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, filters, ContextTypes
)
from config import (
    BUYER_BOT_TOKEN, SUPPLIER_BOT_TOKEN, ADMIN_IDS,
    B_NAME, B_PHONE, B_TYPE, B_CITY,
    PO_CATS, PO_DETAIL, PO_FILE, PO_LOC, PO_TIMELINE,
    PO_BUDGET, PO_NOTES, PO_CONFIRM,
    BOQ_UPLOAD, BOQ_PTYPE, BOQ_SCOPE, BOQ_CONFIRM,
    REV_SCORE, REV_COMMENT,
    BUYER_TYPES, TIMELINES, PROJECT_TYPES,
)
from models.database import (
    get_buyer, upsert_buyer, create_po, get_buyer_pos,
    get_po, create_boq_job, create_review, get_latest_prices,
    select_quote, get_supplier_by_id, get_buyer_by_id,
    mark_buyer_notified, get_suppliers_matching_categories,
    get_supplier, get_po_quotes, get_category_map
)
from keyboards.builders import (
    buyer_type_kb, city_kb, buyer_main_menu_kb, multi_cat_kb,
    timeline_kb, skip_kb, po_file_kb, po_confirm_kb, project_type_kb,
    boq_confirm_kb, quotes_kb, back_buyer, price_cat_kb, lead_kb
)
from utils.messages import (
    BUYER_WELCOME, fmt_po, fmt_quotes, fmt_boq_confirm,
    fmt_price_report, fmt_buyer_intro, fmt_supplier_selected,
    _fmt_cats
)
from utils.files import (
    send_file_preview, reply_file_preview,
    extract_file_info, validate_upload, is_image
)


def lead_kb_import(po_id):
    return lead_kb(po_id)

logging.basicConfig(format="%(asctime)s [BUYER] %(levelname)s %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

SUPPORT = "@hbh_supportbot"
CHANNEL = "https://t.me/habeshabuildethio"

# ── /start ─────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid         = update.effective_user.id
    tg_username = update.effective_user.username or ""
    buyer       = get_buyer(uid)
    upsert_buyer(uid, tg_username=tg_username)
    if buyer and buyer.get('name'):
        await update.message.reply_text(
            f"ሰላም {buyer['name']}! 👋 Welcome back to *Habesha Build Hub* 🏗️",
            parse_mode="Markdown", reply_markup=buyer_main_menu_kb()
        )
        return ConversationHandler.END
    await update.message.reply_text(
        BUYER_WELCOME, parse_mode="Markdown", reply_markup=buyer_type_kb()
    )
    return B_TYPE

async def got_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "menu:main":
        await q.edit_message_text("Main Menu 🏗️", reply_markup=buyer_main_menu_kb())
        return ConversationHandler.END
    context.user_data['reg'] = {'buyer_type': q.data.split(":")[1]}
    await q.edit_message_text("👤 Your *name* or *company name*?", parse_mode="Markdown")
    return B_NAME

async def got_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 2:
        await update.message.reply_text("Please enter a valid name."); return B_NAME
    context.user_data['reg']['name'] = name
    await update.message.reply_text(
        "📍 *Which city are you building in?*",
        parse_mode="Markdown", reply_markup=city_kb("regcity")
    )
    return B_CITY

async def got_city_reg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data['reg']['city'] = q.data.split(":",1)[1]
    await q.edit_message_text(
        "📞 Your *phone number*?\n_(e.g. 0911 *****)_\n\n"
        "_Shared only when you connect with a supplier._",
        parse_mode="Markdown"
    )
    return B_PHONE

async def got_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    reg = context.user_data.pop('reg', {})
    reg['phone'] = update.message.text.strip()
    upsert_buyer(uid, **reg)
    buyer = get_buyer(uid)
    await update.message.reply_text(
        f"✅ *Profile created!*\n\n"
        f"🆔 ID: `HBH-B-{buyer['buyer_id']:04d}`\n\n"
        f"Everything is *free* — submit as many orders as you need.\n\n"
        f"What would you like to do?",
        parse_mode="Markdown", reply_markup=buyer_main_menu_kb()
    )
    return ConversationHandler.END

# ── CANCEL (universal) ─────────────────────────────────────────────────────────

async def cancel_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles both /cancel command and po:cancel / boq:cancel callbacks."""
    context.user_data.pop('po',  None)
    context.user_data.pop('boq', None)
    context.user_data.pop('reg', None)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "Cancelled. What would you like to do?",
            reply_markup=buyer_main_menu_kb()
        )
    else:
        await update.message.reply_text(
            "Cancelled. What would you like to do?",
            reply_markup=buyer_main_menu_kb()
        )
    return ConversationHandler.END

# ── MENU ───────────────────────────────────────────────────────────────────────

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    action = q.data.split(":")[1]
    uid    = update.effective_user.id

    if action == "main":
        await q.edit_message_text("Main Menu 🏗️", reply_markup=buyer_main_menu_kb())

    elif action == "prices":
        await q.edit_message_text(
            "💰 *Select a category:*",
            parse_mode="Markdown", reply_markup=price_cat_kb()
        )

    elif action == "mypos":
        buyer = get_buyer(uid)
        if not buyer:
            await q.edit_message_text("Please /start first."); return
        pos = get_buyer_pos(buyer['buyer_id'])
        if not pos:
            await q.edit_message_text(
                "You haven't submitted any purchase orders yet.\n\n"
                "Tap *New Purchase Order* to get started!",
                parse_mode="Markdown", reply_markup=back_buyer()
            ); return
        text = "📁 *Your Purchase Orders*\n\n"
        for po in pos[:5]:
            text += fmt_po(po) + "\n\n" + "─"*26 + "\n\n"
        await q.edit_message_text(text, parse_mode="Markdown", reply_markup=back_buyer())

    elif action == "profile":
        buyer = get_buyer(uid)
        if not buyer:
            await q.edit_message_text("Please /start first."); return
        btype = BUYER_TYPES.get(buyer.get('buyer_type',''), buyer.get('buyer_type',''))
        await q.edit_message_text(
            f"👤 *Your Profile*\n{'─'*26}\n"
            f"🆔 `HBH-B-{buyer['buyer_id']:04d}`\n"
            f"👤 {buyer.get('name','—')}\n"
            f"📱 {buyer.get('phone','—')}\n"
            f"🏷️ {btype}\n"
            f"📍 {buyer.get('city','—')}\n"
            f"📋 Orders: {buyer.get('po_count',0)}\n",
            parse_mode="Markdown", reply_markup=back_buyer()
        )

    elif action == "support":
        await q.edit_message_text(
            f"📞 *Support*\n\n"
            f"Message us: {SUPPORT}\n"
            f"We respond within 2 hours.\n\n"
            f"Channel: {CHANNEL}",
            parse_mode="Markdown", reply_markup=back_buyer()
        )

# ── PO FLOW ────────────────────────────────────────────────────────────────────

async def po_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start PO flow — clear previous state to prevent contamination."""
    q = update.callback_query; await q.answer()
    # Clean up any lingering state from other flows
    context.user_data.pop('boq',  None)
    context.user_data.pop('quote', None)
    context.user_data.pop('review', None)
    context.user_data.pop('sreg', None)
    # Initialize fresh PO state
    context.user_data['po'] = {'categories': []}
    await q.edit_message_text(
        "📋 *New Purchase Order*\n\n"
        "Select the materials you need:\n"
        "_(Tap to select, tap again to deselect. Multiple allowed.)_",
        parse_mode="Markdown",
        reply_markup=multi_cat_kb([], prefix="pocat")
    )
    return PO_CATS

async def po_cat_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    key  = q.data.split(":")[1]

    # Cancel/menu taps handled inline
    if key == "cancel":
        return await cancel_to_menu(update, context)

    cats = context.user_data.setdefault('po', {}).setdefault('categories', [])
    if key == "done":
        if not cats:
            await q.answer("Please select at least one material.", show_alert=True)
            return PO_CATS
        labels = ", ".join(get_category_map().get(k, k) for k in cats)
        await q.edit_message_text(
            f"Selected: *{labels}*\n\n"
            f"Describe what you need in detail:\n"
            f"_Include brand, grade, quantity, specs — anything helpful_\n\n"
            f"_e.g. 'Derba cement 50kg bags, 500 bags + 12mm rebar 2 tonnes'_",
            parse_mode="Markdown"
        )
        return PO_DETAIL

    if key in cats: cats.remove(key)
    else:           cats.append(key)
    await q.edit_message_reply_markup(reply_markup=multi_cat_kb(cats, prefix="pocat"))
    return PO_CATS

async def po_got_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['po']['material_detail'] = update.message.text.strip()
    await update.message.reply_text(
        "📎 *Do you want to attach a file to this order?*\n\n"
        "You can attach an Excel spreadsheet, PNG, JPG, or any image "
        "with your order details, drawings, or specifications.\n\n"
        "This is optional — suppliers will be able to download it.",
        parse_mode="Markdown",
        reply_markup=po_file_kb()
    )
    return PO_FILE

async def po_attach_file_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buyer chose to attach a file — wait for the file."""
    q = update.callback_query; await q.answer()
    await q.edit_message_text(
        "📎 *Send your file now:*\n\n"
        "_Accepted: Excel (.xlsx), PDF, PNG, JPG, or any image_\n\n"
        "_(Or type /cancel to go back to the menu)_",
        parse_mode="Markdown"
    )
    return PO_FILE

async def po_got_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buyer sends a file or photo to attach to the PO."""
    # Defensive: ensure 'po' context exists
    if 'po' not in context.user_data:
        logger.warning(f"po_got_file: 'po' context missing for user {update.effective_user.id}")
        context.user_data['po'] = {'categories': []}
    
    doc = update.message.document or (
        update.message.photo[-1] if update.message.photo else None
    )
    if not doc:
        logger.debug(f"PO_FILE: No document received from user {update.effective_user.id}")
        await update.message.reply_text(
            "Please send a file or photo, or type /cancel."
        )
        return PO_FILE

    try:
        # Validate upload using utils
        is_valid, error_msg = validate_upload(update.message)
        if not is_valid:
            logger.warning(f"PO_FILE: Validation failed for user {update.effective_user.id}: {error_msg}")
            await update.message.reply_text(error_msg, parse_mode="Markdown")
            return PO_FILE
        
        file_id   = doc.file_id
        file_name = getattr(doc, 'file_name', 'po_attachment.jpg')
        
        # Validate file attributes
        if not file_id:
            logger.error(f"PO_FILE: file_id is empty for user {update.effective_user.id}")
            await update.message.reply_text("❌ File ID missing. Please try again.")
            return PO_FILE
        
        # Store in context
        context.user_data['po']['po_file_id']   = file_id
        context.user_data['po']['po_file_name'] = file_name
        
        logger.info(f"PO_FILE: Stored file {file_name} (ID: {file_id[:20]}...) for user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"PO_FILE: Exception extracting file info: {e}", exc_info=e)
        await update.message.reply_text("❌ File processing error. Please try again.")
        return PO_FILE

    await update.message.reply_text(
        f"✅ File attached: *{context.user_data['po']['po_file_name']}*\n\n"
        f"📍 *Delivery location?*\n"
        f"_e.g. 'Bole, near Edna Mall, Addis Ababa'_",
        parse_mode="Markdown"
    )
    return PO_LOC

async def po_skip_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buyer chose to skip file attachment."""
    q = update.callback_query; await q.answer()
    context.user_data['po']['po_file_id']   = None
    context.user_data['po']['po_file_name'] = None
    await q.edit_message_text(
        "📍 *Delivery location?*\n"
        "_e.g. 'Bole, near Edna Mall, Addis Ababa'_",
        parse_mode="Markdown"
    )
    return PO_LOC

async def po_got_loc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['po']['location'] = update.message.text.strip()
    await update.message.reply_text(
        "⏱️ *When do you need delivery?*",
        parse_mode="Markdown", reply_markup=timeline_kb()
    )
    return PO_TIMELINE

async def po_got_timeline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if "cancel" in q.data:
        return await cancel_to_menu(update, context)
    context.user_data['po']['timeline'] = q.data.split(":")[1]
    await q.edit_message_text(
        "💰 *Budget?* _(Optional)_\n\n"
        "Type your budget freely, or tap Skip.\n\n"
        "_Examples: 'Around 500k', 'Under 1 million', 'Negotiable'_",
        parse_mode="Markdown", reply_markup=skip_kb()
    )
    return PO_BUDGET

async def po_got_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['po']['budget_range'] = update.message.text.strip()
    await update.message.reply_text(
        "📝 *Any extra notes?*\n"
        "_Payment terms, site access hours, preferred brand — or type 'none'_",
        parse_mode="Markdown"
    )
    return PO_NOTES

async def po_skip_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data['po']['budget_range'] = ''
    await q.edit_message_text(
        "📝 *Any extra notes?*\n"
        "_Payment terms, site access, preferred brand — or type 'none'_",
        parse_mode="Markdown"
    )
    return PO_NOTES

async def po_got_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    notes = update.message.text.strip()
    context.user_data['po']['notes'] = '' if notes.lower() == 'none' else notes
    pd = context.user_data['po']
    tl       = TIMELINES.get(pd.get('timeline',''), pd.get('timeline',''))
    has_file = f"📎 {pd.get('po_file_name','')}" if pd.get('po_file_id') else "None"
    preview  = (
        f"*Confirm your Purchase Order:*\n\n"
        f"📦 {_fmt_cats(pd.get('categories',[]))}\n"
        f"🔍 {pd.get('material_detail','—')}\n"
        f"📎 Attachment: {has_file}\n"
        f"📍 {pd.get('location','—')}\n"
        f"⏱️ {tl}\n"
        f"💰 {pd.get('budget_range','Not specified') or 'Not specified'}\n"
        f"📝 {pd.get('notes','—') or '—'}\n"
    )
    await update.message.reply_text(
        preview, parse_mode="Markdown", reply_markup=po_confirm_kb()
    )
    return PO_CONFIRM

async def po_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    action = q.data.split(":")[1]

    if action in ("cancel", "main"):
        return await cancel_to_menu(update, context)

    if action == "edit":
        context.user_data['po'] = {'categories': []}
        await q.edit_message_text(
            "Let's start over. Select the materials you need:",
            reply_markup=multi_cat_kb([], prefix="pocat")
        )
        return PO_CATS

    uid   = update.effective_user.id
    buyer = get_buyer(uid)
    po    = create_po(buyer['buyer_id'], **context.user_data.pop('po', {}))
    upsert_buyer(uid, po_count=buyer.get('po_count',0)+1)

    file_note = (
        f"\n📎 Attachment: `{po.get('po_file_name','')}`\n"
        f"_Suppliers can download it with:_ `/getfile {po.get('po_file_id','')}`"
        if po.get('po_file_id') else ""
    )

    await q.edit_message_text(
        f"✅ *Purchase Order Submitted!*\n\n"
        f"🆔 `{po['po_code']}`\n"
        f"{file_note}\n"
        f"Matching suppliers are being notified now.\n"
        f"📬 You'll receive supplier responses directly here.",
        parse_mode="Markdown", reply_markup=back_buyer()
    )

    # ── Auto-route to matching suppliers ──────────────────────────────────────
    try:
        po_cats = json.loads(po.get('categories','[]'))
        logger.info(f"PO_CONFIRM: Parsed categories {po_cats} for PO {po['po_code']}")
    except Exception as e:
        logger.error(f"PO_CONFIRM: Failed to parse PO categories: {e}")
        po_cats = []
    
    logger.info(f"PO_CONFIRM: Buyer {buyer.get('buyer_id')} PO {po['po_code']} categories (raw)={po_cats}")
    suppliers = get_suppliers_matching_categories(po_cats)
    logger.info(f"PO_CONFIRM: Matched {len(suppliers)} suppliers for PO {po['po_code']}")

    if not suppliers:
        logger.warning(f"PO_CONFIRM: No suppliers matched categories {po_cats}. PO {po['po_code']} won't be routed.")
        # Inform admins immediately about no auto-routing
        for aid in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    aid,
                    f"⚠️ *Auto-routing failed* — `{po['po_code']}`\nNo suppliers matched categories: {po_cats}",
                    parse_mode="Markdown"
                )
            except Exception:
                logger.debug(f"PO_CONFIRM: Failed to notify admin {aid} about routing failure")
    
    sup_bot  = Bot(token=SUPPLIER_BOT_TOKEN)
    notified = 0
    file_delivery_success = 0
    # Log matched supplier id and telegram_id list
    try:
        supplier_summary = [f"{s.get('supplier_id')}@{s.get('telegram_id')}" for s in suppliers]
    except Exception:
        supplier_summary = []
    logger.info(f"PO_CONFIRM: Suppliers matched (id@tg): {supplier_summary}")

    for idx, s in enumerate(suppliers[:8], 1):
        try:
            supplier_id = s.get('supplier_id', 'UNKNOWN')
            telegram_id = s.get('telegram_id')
            
            if not telegram_id:
                logger.error(f"PO_CONFIRM: Supplier {supplier_id} has no telegram_id")
                continue
            
            logger.debug(f"PO_CONFIRM: Sending PO lead to supplier {supplier_id} (tg:{telegram_id}) - {idx}/8")
            
            # ── Send text message with PO details and contact info ──────────────
            try:
                await sup_bot.send_message(
                    telegram_id,
                    fmt_po_lead_with_contact(po, buyer),
                    parse_mode="Markdown",
                    reply_markup=lead_kb_import(po['po_id'])
                )
                logger.info(f"PO_CONFIRM: Text message sent to supplier {supplier_id} (tg:{telegram_id})")
            except TelegramError as te:
                logger.warning(f"PO_CONFIRM: TelegramError sending text to supplier {supplier_id} (tg:{telegram_id}): {te}")
                continue
            except Exception as send_e:
                logger.error(f"PO_CONFIRM: Unexpected error sending text to supplier {supplier_id} (tg:{telegram_id}): {send_e}", exc_info=send_e)
                continue
            
            # ── Send PO file if it exists as TRUE Telegram-native attachment ────
            if po.get('po_file_id'):
                try:
                    logger.debug(f"PO_CONFIRM: Sending PO file to supplier {supplier_id} (tg:{telegram_id})")
                    file_caption = (
                        f"📎 *Attachment for {po['po_code']}*\n\n"
                        f"_Buyer: {buyer.get('name','—')}_\n"
                        f"_via Habesha Build Hub_ 🏗️"
                    )
                    file_sent = await send_file_preview(
                        bot=sup_bot,
                        chat_id=telegram_id,
                        file_id=po['po_file_id'],
                        filename=po.get('po_file_name', 'po_attachment'),
                        caption=file_caption,
                        parse_mode="Markdown"
                    )
                    if file_sent:
                        logger.info(f"PO_CONFIRM: File delivered successfully to supplier {supplier_id} (tg:{telegram_id})")
                        file_delivery_success += 1
                    else:
                        logger.warning(f"PO_CONFIRM: File delivery failed for supplier {supplier_id} (tg:{telegram_id}) — file may have expired")
                except TelegramError as fe:
                    logger.warning(f"PO_CONFIRM: TelegramError sending file to supplier {supplier_id} (tg:{telegram_id}): {fe}")
                except Exception as file_e:
                    logger.error(f"PO_CONFIRM: Unexpected error sending file to supplier {supplier_id} (tg:{telegram_id}): {file_e}", exc_info=file_e)
            else:
                logger.debug(f"PO_CONFIRM: No file attached to PO {po['po_code']}, skipping file delivery")
            
            # Update supplier leads_received counter
            from models.database import get_connection as _gc
            _conn = _gc()
            _conn.execute(
                "UPDATE suppliers SET leads_received=leads_received+1 WHERE supplier_id=?",
                (supplier_id,)
            )
            _conn.commit(); _conn.close()
            notified += 1
            logger.info(f"PO_CONFIRM: Successfully routed PO {po['po_code']} to supplier {supplier_id} (file: {'YES' if po.get('po_file_id') else 'NO'})")
            
        except TelegramError as e:
            logger.warning(f"PO_CONFIRM: Telegram error routing to supplier {s.get('supplier_id','?')}: {type(e).__name__} - {e}")
        except Exception as e:
            logger.error(f"PO_CONFIRM: Unexpected error routing to supplier {s.get('supplier_id','?')}: {e}", exc_info=e)

    for aid in ADMIN_IDS:
        try:
            await context.bot.send_message(
                aid,
                f"📋 *New PO Routed* — `{po['po_code']}`\n"
                f"Buyer: {buyer.get('name','—')}\n"
                f"Detail: {po.get('material_detail','—')}\n"
                f"File: {po.get('po_file_name') or 'None'}\n"
                f"Location: {po.get('location','—')}\n"
                f"Categories: {po_cats}\n"
                f"Suppliers matched: {len(suppliers)}\n"
                f"Suppliers notified: {notified}\n"
                f"Files delivered: {file_delivery_success}",
                parse_mode="Markdown"
            )
        except TelegramError as e:
            logger.warning(f"PO_CONFIRM: Failed to notify admin {aid}: {e}")
        except Exception as e:
            logger.error(f"PO_CONFIRM: Error notifying admin {aid}: {e}", exc_info=e)

    return ConversationHandler.END

# ── BOQ FLOW ───────────────────────────────────────────────────────────────────

async def boq_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point — triggered by menu:boq button. Clear previous state."""
    q = update.callback_query; await q.answer()
    # Clean up any lingering state from other flows
    context.user_data.pop('po',  None)
    context.user_data.pop('quote', None)
    context.user_data.pop('review', None)
    context.user_data.pop('sreg', None)
    # Initialize fresh BOQ state
    context.user_data['boq'] = {}
    await q.edit_message_text(
        "📊 *BOQ Cost Estimation*\n\n"
        "Upload your BOQ file and our specialists will:\n"
        "✅ Extract all quantities\n"
        "✅ Apply current market prices\n"
        "✅ Produce a full cost estimate\n\n"
        "⏱️ Turnaround: 24–72 hours  ·  *Free*\n\n"
        "*Send your file now:*\n"
        "_PDF, Excel (.xlsx), Word, or a photo of your BOQ_\n\n"
        "_Tap ❌ Cancel to go back._",
        parse_mode="Markdown"
    )
    return BOQ_UPLOAD

async def boq_got_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Defensive: ensure 'boq' context exists
    if 'boq' not in context.user_data:
        logger.warning(f"boq_got_file: 'boq' context missing for user {update.effective_user.id}")
        context.user_data['boq'] = {}
    
    doc = update.message.document or (
        update.message.photo[-1] if update.message.photo else None
    )
    if not doc:
        logger.debug(f"BOQ_UPLOAD: No document received from user {update.effective_user.id}")
        await update.message.reply_text(
            "Please send a file or photo, or type /cancel."
        )
        return BOQ_UPLOAD

    try:
        # Validate upload using utils
        is_valid, error_msg = validate_upload(update.message)
        if not is_valid:
            logger.warning(f"BOQ_UPLOAD: Validation failed for user {update.effective_user.id}: {error_msg}")
            await update.message.reply_text(error_msg, parse_mode="Markdown")
            return BOQ_UPLOAD
        
        file_id   = doc.file_id
        file_name = getattr(doc, 'file_name', 'boq_photo.jpg')
        
        # Validate file attributes
        if not file_id:
            logger.error(f"BOQ_UPLOAD: file_id is empty for user {update.effective_user.id}")
            await update.message.reply_text("❌ File ID missing. Please try again.")
            return BOQ_UPLOAD
        
        # Store in context
        context.user_data['boq']['file_id']   = file_id
        context.user_data['boq']['file_name'] = file_name
        
        logger.info(f"BOQ_UPLOAD: Stored file {file_name} (ID: {file_id[:20]}...) for user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"BOQ_UPLOAD: Exception extracting file info: {e}", exc_info=e)
        await update.message.reply_text("❌ File processing error. Please try again.")
        return BOQ_UPLOAD

    await update.message.reply_text(
        f"✅ Got it — *{context.user_data['boq']['file_name']}*\n\n"
        f"🏗️ *What type of project is this?*",
        parse_mode="Markdown", reply_markup=project_type_kb()
    )
    return BOQ_PTYPE

async def boq_got_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if "cancel" in q.data:
        return await cancel_to_menu(update, context)
    if 'boq' not in context.user_data:
        context.user_data['boq'] = {}
    context.user_data['boq']['project_type'] = PROJECT_TYPES.get(
        q.data.split(":")[1], q.data.split(":")[1]
    )
    await q.edit_message_text(
        "📋 *Briefly describe the scope:*\n\n"
        "_e.g. 'G+2 residential villa, structural + finishing'\n"
        "'Foundation only'\n"
        "'Full MEP works for 4-storey building'_\n\n"
        "_(Type /cancel to go back to the menu)_",
        parse_mode="Markdown"
    )
    return BOQ_SCOPE

async def boq_got_scope(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'boq' not in context.user_data:
        context.user_data['boq'] = {}
    context.user_data['boq']['scope'] = update.message.text.strip()
    b = context.user_data['boq']
    await update.message.reply_text(
        f"📋 *Confirm BOQ submission:*\n\n"
        f"📄 File: {b.get('file_name','—')}\n"
        f"🏗️ Project: {b.get('project_type','—')}\n"
        f"📋 Scope: {b.get('scope','—')}\n",
        parse_mode="Markdown", reply_markup=boq_confirm_kb()
    )
    return BOQ_CONFIRM

async def boq_confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data.split(":")[1] in ("cancel", "main"):
        return await cancel_to_menu(update, context)

    uid   = update.effective_user.id
    buyer = get_buyer(uid)
    if not buyer:
        await q.edit_message_text("Session expired. Please /start again.")
        return ConversationHandler.END

    b   = context.user_data.pop('boq', {})
    job = create_boq_job(
        buyer['buyer_id'],
        b.get('file_id'), b.get('file_name'),
        b.get('project_type'), b.get('scope')
    )
    await q.edit_message_text(
        fmt_boq_confirm(job),
        parse_mode="Markdown", reply_markup=back_buyer()
    )
    for aid in ADMIN_IDS:
        try:
            await context.bot.send_message(
                aid,
                f"📊 *New BOQ* — `{job['boq_code']}`\n"
                f"Buyer: {buyer.get('name','—')}\n"
                f"Project: {job.get('project_type','—')}\n"
                f"Scope: {job.get('scope','—')}\n"
                f"File ID: `{job.get('file_id','—')}`\n\n"
                f"_To open: /getfile {job.get('file_id','—')}_",
                parse_mode="Markdown"
            )
        except Exception: pass
    return ConversationHandler.END

# ── PRICE CHECK ────────────────────────────────────────────────────────────────

async def price_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    cat    = q.data.split(":",1)[1]
    prices = get_latest_prices()
    await q.edit_message_text(
        fmt_price_report(prices, cat),
        parse_mode="Markdown", reply_markup=back_buyer()
    )

# ── QUOTE SELECTION ────────────────────────────────────────────────────────────

async def select_quote_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    quote_id = int(q.data.split(":")[1])
    quote    = select_quote(quote_id)
    supplier = get_supplier_by_id(quote['supplier_id'])
    po       = get_po(quote['po_id'])
    buyer    = get_buyer(update.effective_user.id)

    await q.edit_message_text(
        fmt_buyer_intro(supplier, quote, po),
        parse_mode="Markdown", reply_markup=back_buyer()
    )
    try:
        sup_bot = Bot(token=SUPPLIER_BOT_TOKEN)
        await sup_bot.send_message(
            supplier['telegram_id'],
            fmt_supplier_selected(buyer, po),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.warning(f"Could not notify supplier of selection: {e}")

async def view_quotes_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    po_id  = int(q.data.split(":")[1])
    po     = get_po(po_id)
    quotes = get_po_quotes(po_id)
    if not quotes:
        await q.edit_message_text(
            "No quotes yet — suppliers will respond shortly.",
            reply_markup=back_buyer()
        ); return
    await q.edit_message_text(
        fmt_quotes(quotes, po),
        parse_mode="Markdown", reply_markup=quotes_kb(quotes)
    )

# ── REVIEW ─────────────────────────────────────────────────────────────────────

async def review_score_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _, sid, score = q.data.split(":")
    context.user_data['rev'] = {'supplier_id': int(sid), 'score': int(score)}
    await q.edit_message_text(
        f"You rated: {'⭐'*int(score)}\n\nLeave a comment? _(or type 'skip')_",
        parse_mode="Markdown"
    )
    return REV_COMMENT

async def review_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid     = update.effective_user.id
    buyer   = get_buyer(uid)
    rv      = context.user_data.pop('rev', {})
    comment = update.message.text.strip()
    create_review(
        rv['supplier_id'], buyer['buyer_id'], rv['score'],
        '' if comment.lower() == 'skip' else comment
    )
    await update.message.reply_text(
        "✅ *Review submitted. Thank you!*",
        parse_mode="Markdown", reply_markup=buyer_main_menu_kb()
    )
    return ConversationHandler.END

# ── HELPERS ────────────────────────────────────────────────────────────────────

def fmt_po_lead_with_contact(po, buyer):
    tl  = TIMELINES.get(po.get('timeline',''), po.get('timeline',''))
    tg  = f"@{buyer.get('tg_username','')}" if buyer.get('tg_username') else "_(no username)_"
    file_line = (
        f"\n📎 *Attached file:* {po.get('po_file_name','')}\n"
        f"_Download with:_ `/getfile {po.get('po_file_id','')}`"
        if po.get('po_file_id') else ""
    )
    return (
        f"🔔 *New Purchase Order*\n{'─'*28}\n"
        f"🆔 {po['po_code']}\n"
        f"📦 *{_fmt_cats(po.get('categories','[]'))}*\n"
        f"🔍 {po.get('material_detail','—')}\n"
        f"{file_line}\n"
        f"📍 {po.get('location','—')}\n"
        f"⏱️ {tl}\n"
        f"💰 {po.get('budget_range','Not specified') or 'Not specified'}\n"
        f"{'─'*28}\n"
        f"👤 *Buyer contact:*\n"
        f"Name: {buyer.get('name','—')}\n"
        f"📱 Phone: {buyer.get('phone','—')}\n"
        f"💬 Telegram: {tg}\n"
        f"{'─'*28}\n"
        f"_via Habesha Build Hub_ 🏗️"
    )

# ── FALLBACK ───────────────────────────────────────────────────────────────────

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buyer = get_buyer(update.effective_user.id)
    if buyer and buyer.get('name'):
        await update.message.reply_text(
            "Use the menu below 👇", reply_markup=buyer_main_menu_kb()
        )
    else:
        await update.message.reply_text("Send /start to begin.")

async def error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}", exc_info=context.error)

from utils.messages import fmt_quotes, fmt_supplier_selected

# ── /getfile — buyer downloads proformas or BOQ results ───────────────────────

async def getfile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /getfile FILE_ID
    Downloads and previews any file sent to this buyer:
      - Proforma files from suppliers   (shown as photo or document)
      - BOQ estimation results from admin
    File ID is always shown in the message where the file was mentioned.
    """
    parts = update.message.text.strip().split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await update.message.reply_text(
            "📎 *How to use /getfile:*\n\n"
            "Type `/getfile` followed by the file ID shown in a message.\n\n"
            "*Example:*\n"
            "`/getfile BQACAgIAAxkBAAI...`\n\n"
            "*Where to find file IDs:*\n"
            "• Proforma from supplier — file ID shown in that message\n"
            "• BOQ result from admin — file ID shown in the delivery message\n\n"
            "_Copy the full ID and paste it after /getfile_",
            parse_mode="Markdown",
            reply_markup=back_buyer()
        )
        return

    file_id  = parts[1].strip()
    thinking = await update.message.reply_text("⏳ Fetching your file...")

    # Try to detect filename from context — default to generic
    filename = context.user_data.get(f'filename_{file_id}', 'file')

    success = await reply_file_preview(
        message=update.message,
        file_id=file_id,
        filename=filename,
        caption=(
            "📎 *Your file is ready.*\n\n"
            f"_File ID: `{file_id}`_\n"
            "_via Habesha Build Hub_ 🏗️"
        ),
        parse_mode="Markdown"
    )
    try:
        await thinking.delete()
    except Exception:
        pass

    if not success:
        await update.message.reply_text(
            "❌ *Could not preview that file.*\n\n"
            "Possible reasons:\n"
            "• The file ID was copied incorrectly\n"
            "• The file has expired on Telegram's servers\n\n"
            f"Contact support: {SUPPORT}",
            parse_mode="Markdown",
            reply_markup=back_buyer()
        )

# ── BUILD ──────────────────────────────────────────────────────────────────────

def build_buyer_app():
    app = Application.builder().token(BUYER_BOT_TOKEN).build()

    cancel_cb = CallbackQueryHandler(cancel_to_menu, pattern=r"^(po|boq):cancel$")

    onboarding = ConversationHandler(
        per_chat=True,
        per_user=True,
        per_message=True,
        entry_points=[CommandHandler("start", start)],
        states={
            B_TYPE:  [CallbackQueryHandler(got_type,     pattern=r"^(btype:|menu:main)")],
            B_NAME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, got_name)],
            B_CITY:  [CallbackQueryHandler(got_city_reg, pattern=r"^regcity:")],
            B_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_phone)],
        },
        fallbacks=[CommandHandler("cancel", cancel_to_menu), cancel_cb],
        allow_reentry=True,
    )

    po_conv = ConversationHandler(
        per_chat=True,
        per_user=True,
        per_message=True,
        entry_points=[CallbackQueryHandler(po_start, pattern=r"^menu:po$")],
        states={
            PO_CATS: [
                CallbackQueryHandler(po_cat_toggle, pattern=r"^pocat:"),
                CallbackQueryHandler(cancel_to_menu, pattern=r"^po:cancel$"),
            ],
            PO_DETAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, po_got_detail),
            ],
            PO_FILE: [
                # File or photo sent
                MessageHandler(
                    (filters.Document.ALL | filters.PHOTO) & ~filters.COMMAND,
                    po_got_file
                ),
                # "Attach a file" button
                CallbackQueryHandler(po_attach_file_prompt, pattern=r"^po:attach_file$"),
                # "Skip" button
                CallbackQueryHandler(po_skip_file, pattern=r"^po:skip_file$"),
                # Cancel
                CallbackQueryHandler(cancel_to_menu, pattern=r"^po:cancel$"),
            ],
            PO_LOC:      [MessageHandler(filters.TEXT & ~filters.COMMAND, po_got_loc)],
            PO_TIMELINE: [
                CallbackQueryHandler(po_got_timeline, pattern=r"^timeline:"),
                CallbackQueryHandler(cancel_to_menu,  pattern=r"^po:cancel$"),
            ],
            PO_BUDGET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, po_got_budget),
                CallbackQueryHandler(po_skip_budget, pattern=r"^skip:budget$"),
                CallbackQueryHandler(cancel_to_menu, pattern=r"^po:cancel$"),
            ],
            PO_NOTES:   [MessageHandler(filters.TEXT & ~filters.COMMAND, po_got_notes)],
            PO_CONFIRM: [CallbackQueryHandler(po_confirm, pattern=r"^po:")],
        },
        fallbacks=[CommandHandler("cancel", cancel_to_menu), cancel_cb],
        allow_reentry=True,
    )

    boq_conv = ConversationHandler(
        per_chat=True,
        per_user=True,
        per_message=True,
        entry_points=[CallbackQueryHandler(boq_start, pattern=r"^menu:boq$")],
        states={
            BOQ_UPLOAD: [
                MessageHandler(
                    (filters.Document.ALL | filters.PHOTO) & ~filters.COMMAND,
                    boq_got_file
                ),
                CallbackQueryHandler(cancel_to_menu, pattern=r"^boq:cancel$"),
            ],
            BOQ_PTYPE: [
                CallbackQueryHandler(boq_got_type, pattern=r"^ptype:"),
                CallbackQueryHandler(cancel_to_menu, pattern=r"^boq:cancel$"),
            ],
            BOQ_SCOPE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, boq_got_scope)],
            BOQ_CONFIRM: [CallbackQueryHandler(boq_confirm_handler, pattern=r"^boq:")],
        },
        fallbacks=[CommandHandler("cancel", cancel_to_menu), cancel_cb],
        allow_reentry=True,
    )

    review_conv = ConversationHandler(
        per_chat=True,
        per_user=True,
        per_message=True,
        entry_points=[CallbackQueryHandler(review_score_cb, pattern=r"^rev:")],
        states={REV_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, review_comment)]},
        fallbacks=[CommandHandler("cancel", cancel_to_menu)],
    )

    app.add_handler(CommandHandler("getfile", getfile_cmd))
    app.add_handler(onboarding)
    app.add_handler(po_conv)
    app.add_handler(boq_conv)
    app.add_handler(review_conv)
    app.add_handler(CallbackQueryHandler(menu_callback,         pattern=r"^menu:"))
    app.add_handler(CallbackQueryHandler(price_callback,        pattern=r"^price:"))
    app.add_handler(CallbackQueryHandler(select_quote_callback, pattern=r"^selectquote:"))
    app.add_handler(CallbackQueryHandler(view_quotes_callback,  pattern=r"^viewquotes:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))
    app.add_error_handler(error_handler)
    return app
