"""
Habesha Build Hub — SUPPLIER BOT v5
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
v5 changes:
  • All inline imports moved to top level
  • File previews use utils.files for proper photo/document detection
  • Proforma delivery shows actual file preview to buyer
  • Hardened upload validation
"""

import logging, json
from telegram import Update, Bot
from telegram.error import TelegramError
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, filters, ContextTypes
)
from config import (
    SUPPLIER_BOT_TOKEN, BUYER_BOT_TOKEN, ADMIN_IDS,
    S_CATS, S_NAME, S_PHONE, S_CITY, S_CONFIRM,
    Q_TYPE, Q_PRICE, Q_DELIVERY, Q_NOTES, Q_CONFIRM, Q_PROFORMA,
)
from models.database import (
    get_supplier, upsert_supplier, create_quote, get_po,
    get_buyer_by_id, get_platform_stats, get_supplier_by_id,
    get_po_quotes, mark_buyer_notified, get_category_map
)
from keyboards.builders import (
    supplier_menu_kb, city_kb, license_kb, lead_kb,
    quote_type_kb, quote_confirm_kb, proforma_confirm_kb,
    back_supplier, supplier_cat_kb
)
from utils.messages import (
    SUPPLIER_WELCOME, fmt_supplier_dashboard, fmt_po_lead, _fmt_cats
)
from utils.files import (
    send_file_preview, reply_file_preview, extract_file_info, validate_upload
)

logging.basicConfig(format="%(asctime)s [SUPPLIER] %(levelname)s %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

SUPPORT = "@hbh_supportbot"

# ── CANCEL (universal) ─────────────────────────────────────────────────────────

async def cancel_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('quote',    None)
    context.user_data.pop('sreg',     None)
    context.user_data.pop('proforma', None)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "Cancelled.", reply_markup=supplier_menu_kb()
        )
    else:
        await update.message.reply_text("Cancelled.", reply_markup=supplier_menu_kb())
    return ConversationHandler.END

# ── /getfile — download any file by file ID ────────────────────────────────────

async def getfile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /getfile FILE_ID
    Fetches and previews the buyer's attached PO file.
    Images shown as photos, documents as downloadable files.
    """
    parts = update.message.text.strip().split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await update.message.reply_text(
            "📎 *How to use /getfile:*\n\n"
            "Type `/getfile` followed by the file ID shown in the lead message.\n\n"
            "*Example:*\n"
            "`/getfile BQACAgIAAxkBAAI...`\n\n"
            "_The file ID appears when a buyer attached a file to their order._",
            parse_mode="Markdown", reply_markup=back_supplier()
        )
        return

    file_id  = parts[1].strip()
    thinking = await update.message.reply_text("⏳ Fetching file...")
    success  = await reply_file_preview(
        message=update.message,
        file_id=file_id,
        filename=context.user_data.get(f'filename_{file_id}', 'po_attachment'),
        caption="📎 *Purchase Order attachment.*\n_via Habesha Build Hub_ 🏗️",
        parse_mode="Markdown"
    )
    try:
        await thinking.delete()
    except Exception:
        pass
    if not success:
        await update.message.reply_text(
            "❌ Could not fetch that file.\n\n"
            "Check that you copied the full file ID from the lead message.",
            reply_markup=back_supplier()
        )

# ── /start ─────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid      = update.effective_user.id
    username = update.effective_user.username or ""
    logger.info(f"SUPPLIER START: user {uid} username={username}")
    supplier = get_supplier(uid)
    if supplier and supplier.get('business_name'):
        logger.info(f"SUPPLIER START: returning user {uid} - {supplier.get('supplier_id')} already registered")
        upsert_supplier(uid, tg_username=username)
        score = supplier.get('score', 0)
        stars = '⭐' * round(score) if score else ''
        await update.message.reply_text(
            f"ሰላም {supplier['business_name']}! 👋 Welcome back.\n"
            f"{stars} Score: {score:.1f}/5.0",
            reply_markup=supplier_menu_kb()
        )
        return ConversationHandler.END
    logger.info(f"SUPPLIER START: new supplier {uid}, initiating registration")
    upsert_supplier(uid, tg_username=username)
    context.user_data['sreg'] = {'categories': []}
    await update.message.reply_text(
        SUPPLIER_WELCOME, parse_mode="Markdown",
        reply_markup=supplier_cat_kb([], prefix="scat")
    )
    return S_CATS

# ── ONBOARDING ─────────────────────────────────────────────────────────────────

async def cat_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    key = q.data.split(":")[1]
    if key == "cancel":
        return await cancel_to_menu(update, context)
    cats = context.user_data.setdefault('sreg', {}).setdefault('categories', [])
    if key == "done":
        if not cats:
            await q.answer("Select at least one category.", show_alert=True)
            return S_CATS
        from models.database import get_category_map
        labels = ", ".join(get_category_map().get(k, k) for k in cats)
        await q.edit_message_text(
            f"Selected: *{labels}*\n\n*Your business name?*",
            parse_mode="Markdown"
        )
        return S_NAME
    if key in cats: cats.remove(key)
    else:           cats.append(key)
    await q.edit_message_reply_markup(reply_markup=supplier_cat_kb(cats, prefix="scat"))
    return S_CATS

async def got_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['sreg']['business_name'] = update.message.text.strip()
    await update.message.reply_text(
        "📍 *Where are you located?*",
        parse_mode="Markdown", reply_markup=city_kb("scity")
    )
    return S_CITY

async def got_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data['sreg']['city'] = q.data.split(":",1)[1]
    await q.edit_message_text(
        "📞 Your *contact phone number?*\n_(e.g. 0911 *****)_",
        parse_mode="Markdown"
    )
    return S_PHONE

async def got_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['sreg']['phone'] = update.message.text.strip()
    await update.message.reply_text(
        "📄 Do you have a *trade license* or business registration?",
        parse_mode="Markdown", reply_markup=license_kb()
    )
    return S_CONFIRM

async def got_license(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "smenu:main":
        return await cancel_to_menu(update, context)
    uid  = update.effective_user.id
    sreg = context.user_data.pop('sreg', {})
    
    logger.info(f"SUPPLIER CONFIRM: user {uid} registering with categories {sreg.get('categories')} business={sreg.get('business_name')}")
    
    upsert_supplier(uid,
        business_name=sreg.get('business_name'),
        phone=sreg.get('phone'),
        categories=sreg.get('categories', []),
        city=sreg.get('city'),
        score=0.0,
    )
    supplier = get_supplier(uid)
    
    logger.info(f"SUPPLIER CONFIRM: supplier {supplier.get('supplier_id')} created successfully with telegram_id={uid}")
    
    stats    = get_platform_stats()
    from models.database import get_category_map
    cat_labels = ", ".join(
        get_category_map().get(k, k) for k in sreg.get('categories', [])
    )
    await q.edit_message_text(
        f"✅ *Supplier profile created!*\n\n"
        f"🆔 `HBH-S-{supplier['supplier_id']:04d}`\n"
        f"🏢 {supplier.get('business_name','—')}\n"
        f"📦 {cat_labels or '—'}\n"
        f"📍 {supplier.get('city','—')}\n\n"
        f"Platform: *{stats['buyers']} buyers* | *{stats['total_pos']} purchase orders*\n\n"
        f"You'll receive leads automatically. *Free, unlimited.*\n\n"
        f"💡 Tip: Use `/getfile FILE_ID` to download any file "
        f"a buyer attaches to their order.",
        parse_mode="Markdown", reply_markup=supplier_menu_kb()
    )
    return ConversationHandler.END

# ── SUPPLIER MENU ──────────────────────────────────────────────────────────────

async def smenu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    action   = q.data.split(":")[1]
    uid      = update.effective_user.id
    supplier = get_supplier(uid)

    if action == "main":
        await q.edit_message_text("Supplier Menu 🏭", reply_markup=supplier_menu_kb())

    elif action == "dashboard":
        if not supplier:
            await q.edit_message_text("Please /start to register."); return
        await q.edit_message_text(
            fmt_supplier_dashboard(supplier),
            parse_mode="Markdown", reply_markup=back_supplier()
        )

    elif action == "leads":
        await q.edit_message_text(
            "🔔 *Your Leads*\n\n"
            "Purchase order leads are sent to you automatically "
            "when a buyer's order matches your categories.\n\n"
            "💡 *If a buyer attached a file to their order*, use:\n"
            "`/getfile FILE_ID`\n"
            "_The file ID is shown in the lead message._\n\n"
            "You can submit a text quote OR send a proforma file.",
            parse_mode="Markdown", reply_markup=back_supplier()
        )

    elif action == "profile":
        if not supplier:
            await q.edit_message_text("Please /start to register."); return
        from models.database import get_category_map
        import json as _json
        try:
            cat_keys = _json.loads(supplier.get('categories','[]'))
        except Exception:
            cat_keys = []
        cat_labels = ", ".join(get_category_map().get(k, k) for k in cat_keys)
        score = supplier.get('score', 0)
        stars = '⭐' * round(score) if score else 'No ratings yet'
        await q.edit_message_text(
            f"👤 *Your Profile*\n{'─'*26}\n"
            f"🆔 `HBH-S-{supplier['supplier_id']:04d}`\n"
            f"🏢 {supplier.get('business_name','—')}\n"
            f"📱 {supplier.get('phone','—')}\n"
            f"📦 {cat_labels or '—'}\n"
            f"📍 {supplier.get('city','—')}\n"
            f"✅ Verified: {'Yes' if supplier.get('verified') else 'No'}\n"
            f"⭐ Score: {score:.1f}/5.0  {stars}\n"
            f"📨 Leads: {supplier.get('leads_received',0)}\n"
            f"📤 Quotes: {supplier.get('leads_responded',0)}\n",
            parse_mode="Markdown", reply_markup=back_supplier()
        )

    elif action == "verify":
        if supplier and supplier.get('verified'):
            await q.edit_message_text(
                "✅ Your account is already *verified*!",
                parse_mode="Markdown", reply_markup=back_supplier()
            ); return
        await q.edit_message_text(
            "✅ *Get Verified*\n\n"
            "Send your trade license to @hbh_supportbot.\n"
            "We review within 24 hours.\n\n"
            "_Verification is free._",
            parse_mode="Markdown", reply_markup=back_supplier()
        )

    elif action == "support":
        await q.edit_message_text(
            f"📞 *Support*\n\nMessage: {SUPPORT}\n"
            "Response within 2 hours.",
            parse_mode="Markdown", reply_markup=back_supplier()
        )

# ── SKIP LEAD ──────────────────────────────────────────────────────────────────

async def skip_lead(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer("Lead skipped.")
    await q.edit_message_text(
        "_Lead skipped._\nYou'll receive the next matching order automatically.",
        parse_mode="Markdown", reply_markup=back_supplier()
    )

# ── QUOTE TYPE SELECTION ───────────────────────────────────────────────────────

async def start_quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Supplier taps 'Submit Quote' on a lead — first ask: text or proforma file?"""
    q = update.callback_query; await q.answer()
    po_id = int(q.data.split(":")[1])
    po    = get_po(po_id)
    if not po or po['status'] != 'open':
        await q.edit_message_text(
            "This purchase order is no longer open.", reply_markup=back_supplier()
        )
        return ConversationHandler.END
    # Clear previous quote state
    context.user_data.pop('quote', None)
    context.user_data.pop('proforma', None)
    context.user_data['quote'] = {'po_id': po_id}
    await q.edit_message_text(
        f"📤 *Respond to {po['po_code']}*\n\n"
        f"📦 {_fmt_cats(po.get('categories','[]'))}\n"
        f"🔍 {po.get('material_detail','—')}\n"
        f"📍 {po.get('location','—')}\n\n"
        f"How would you like to respond?",
        parse_mode="Markdown",
        reply_markup=quote_type_kb(po_id)
    )
    return Q_TYPE

async def quote_type_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Supplier chose to type their quote."""
    q = update.callback_query; await q.answer()
    po_id = int(q.data.split(":")[2])
    context.user_data['quote']['po_id'] = po_id
    context.user_data['quote']['type']  = 'text'
    await q.edit_message_text(
        "*Your price or offer?*\n\n"
        "_Write anything — e.g. '95,000 including transport', "
        "'8500 per quintal', 'depends on grade, call me'_",
        parse_mode="Markdown"
    )
    return Q_PRICE

async def quote_type_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Supplier chose to send a proforma file."""
    q = update.callback_query; await q.answer()
    po_id = int(q.data.split(":")[2])
    context.user_data['quote']['po_id'] = po_id
    context.user_data['quote']['type']  = 'file'
    await q.edit_message_text(
        "📎 *Send your proforma file:*\n\n"
        "_Accepted: Excel (.xlsx), PDF, PNG, JPG, or any image_\n\n"
        "The buyer will receive the file directly.\n\n"
        "_(Type /cancel to go back)_",
        parse_mode="Markdown"
    )
    return Q_PROFORMA

# ── TEXT QUOTE FLOW ────────────────────────────────────────────────────────────

async def got_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['quote']['price_text'] = update.message.text.strip()
    await update.message.reply_text(
        f"Price: *{context.user_data['quote']['price_text']}*\n\n"
        f"*Estimated delivery time?*\n"
        f"_e.g. '3 days', 'same day', 'within a week'_",
        parse_mode="Markdown"
    )
    return Q_DELIVERY

async def got_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['quote']['delivery_text'] = update.message.text.strip()
    await update.message.reply_text(
        "📝 *Anything else the buyer should know?*\n"
        "_Minimum order, payment terms, brand — or type 'none'_",
        parse_mode="Markdown"
    )
    return Q_NOTES

async def got_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    notes = update.message.text.strip()
    context.user_data['quote']['notes'] = '' if notes.lower() == 'none' else notes
    qd = context.user_data['quote']
    await update.message.reply_text(
        f"*Confirm your quote:*\n\n"
        f"💵 {qd['price_text']}\n"
        f"🚚 {qd['delivery_text']}\n"
        f"📝 {qd.get('notes','—') or '—'}\n",
        parse_mode="Markdown", reply_markup=quote_confirm_kb()
    )
    return Q_CONFIRM

async def quote_confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    action = q.data.split(":")[1]
    if action in ("cancel", "main"):
        return await cancel_to_menu(update, context)
    if action == "edit":
        po_id = context.user_data['quote']['po_id']
        context.user_data['quote'] = {'po_id': po_id, 'type': 'text'}
        await q.edit_message_text("*Your price or offer?*", parse_mode="Markdown")
        return Q_PRICE

    uid      = update.effective_user.id
    supplier = get_supplier(uid)
    qd       = context.user_data.pop('quote', {})

    full_notes = f"Price: {qd['price_text']} | Delivery: {qd['delivery_text']}"
    if qd.get('notes'):
        full_notes += f" | {qd['notes']}"

    quote = create_quote(qd['po_id'], supplier['supplier_id'], 0, 0, 0, full_notes)
    upsert_supplier(uid, leads_responded=supplier.get('leads_responded',0)+1)

    await q.edit_message_text(
        f"✅ *Quote submitted!*\n\n"
        f"💵 {qd['price_text']}\n"
        f"🚚 {qd['delivery_text']}\n\n"
        f"The buyer is being notified with your contact details now.",
        parse_mode="Markdown", reply_markup=back_supplier()
    )

    await _notify_buyer_of_quote(context, qd, supplier, quote)
    return ConversationHandler.END

# ── PROFORMA FILE FLOW ─────────────────────────────────────────────────────────

async def got_proforma_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Supplier sends a proforma file (Excel/image)."""
    # Defensive: ensure 'quote' context exists (should be set by entry point)
    if 'quote' not in context.user_data:
        logger.warning(f"got_proforma_file: 'quote' context missing for user {update.effective_user.id}")
        context.user_data['quote'] = {'po_id': None, 'type': 'file'}
    
    doc = update.message.document or (
        update.message.photo[-1] if update.message.photo else None
    )
    if not doc:
        logger.debug(f"Q_PROFORMA: No document received from user {update.effective_user.id}")
        await update.message.reply_text(
            "Please send a file or photo, or type /cancel."
        )
        return Q_PROFORMA

    try:
        # Validate upload using utils
        is_valid, error_msg = validate_upload(update.message)
        if not is_valid:
            logger.warning(f"Q_PROFORMA: Validation failed for user {update.effective_user.id}: {error_msg}")
            await update.message.reply_text(error_msg, parse_mode="Markdown")
            return Q_PROFORMA
        
        file_id   = doc.file_id
        file_name = getattr(doc, 'file_name', 'proforma.jpg')
        
        # Validate file attributes
        if not file_id:
            logger.error(f"Q_PROFORMA: file_id is empty for user {update.effective_user.id}")
            await update.message.reply_text("❌ File ID missing. Please try again.")
            return Q_PROFORMA
        
        # Store in context under 'proforma' dict
        context.user_data['proforma'] = {
            'file_id':   file_id,
            'file_name': file_name,
        }
        
        logger.info(f"Q_PROFORMA: Stored file {file_name} (ID: {file_id[:20]}...) for user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Q_PROFORMA: Exception extracting file info: {e}", exc_info=e)
        await update.message.reply_text("❌ File processing error. Please try again.")
        return Q_PROFORMA
    await update.message.reply_text(
        f"📎 Got it: *{context.user_data['proforma']['file_name']}*\n\n"
        f"*Add a short note for the buyer?*\n"
        f"_e.g. 'Proforma valid 7 days', 'Call for negotiation' — or type 'none'_",
        parse_mode="Markdown",
        reply_markup=proforma_confirm_kb()
    )
    return Q_PROFORMA

async def proforma_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Called when supplier taps 'Send this proforma'."""
    q = update.callback_query; await q.answer()
    action = q.data.split(":")[1]
    if action in ("cancel", "main"):
        return await cancel_to_menu(update, context)

    uid      = update.effective_user.id
    supplier = get_supplier(uid)
    qd       = context.user_data.pop('quote',    {})
    pf       = context.user_data.pop('proforma', {})

    quote = create_quote(
        qd['po_id'], supplier['supplier_id'],
        0, 0, 0,
        notes=f"Proforma attached: {pf.get('file_name','')}",
        proforma_file_id=pf.get('file_id'),
        proforma_file_name=pf.get('file_name'),
    )
    upsert_supplier(uid, leads_responded=supplier.get('leads_responded',0)+1)

    await q.edit_message_text(
        f"✅ *Proforma sent!*\n\n"
        f"📎 {pf.get('file_name','')}\n\n"
        f"The buyer is receiving your proforma and contact details now.",
        parse_mode="Markdown", reply_markup=back_supplier()
    )

    # Send proforma file + contact details to buyer with proper preview
    try:
        po    = get_po(qd['po_id'])
        buyer = get_buyer_by_id(po['buyer_id'])
        if buyer:
            buyer_bot = Bot(token=BUYER_BOT_TOKEN)
            tg = f"@{supplier.get('tg_username','')}" if supplier.get('tg_username') else "_(no username)_"
            caption = (
                f"📎 *Proforma received for {po.get('po_code','')}*\n\n"
                f"From: *{supplier.get('business_name','—')}*\n"
                f"📱 Phone: {supplier.get('phone','—')}\n"
                f"💬 Telegram: {tg}\n\n"
                f"_File ID: `{pf['file_id']}`_\n"
                f"_Use `/getfile {pf['file_id']}` to re-download anytime._\n\n"
                f"_Contact them directly to discuss._\n"
                f"_via Habesha Build Hub_ 🏗️"
            )
            result = await send_file_preview(
                bot=buyer_bot,
                chat_id=buyer['telegram_id'],
                file_id=pf['file_id'],
                filename=pf.get('file_name', 'proforma.jpg'),
                caption=caption,
                parse_mode="Markdown"
            )
            
            if result:
                logger.info(f"PROFORMA_CONFIRM: Proforma sent successfully to buyer {buyer['telegram_id']}")
                mark_buyer_notified(quote['quote_id'])
            else:
                logger.error(f"PROFORMA_CONFIRM: send_file_preview returned False for buyer {buyer['telegram_id']}")
    except TelegramError as e:
        logger.error(f"PROFORMA_CONFIRM: Telegram error sending proforma to buyer: {type(e).__name__} - {e}")
    except Exception as e:
        logger.error(f"PROFORMA_CONFIRM: Unexpected error delivering proforma to buyer: {e}", exc_info=e)

    return ConversationHandler.END

async def proforma_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Supplier typed a note after uploading proforma — save it then confirm."""
    note = update.message.text.strip()
    if note.lower() != 'none':
        context.user_data.setdefault('proforma', {})['note'] = note
    pf = context.user_data.get('proforma', {})
    await update.message.reply_text(
        f"📎 *Ready to send:*\n\n"
        f"File: {pf.get('file_name','—')}\n"
        f"Note: {pf.get('note','—') or '—'}\n",
        parse_mode="Markdown", reply_markup=proforma_confirm_kb()
    )
    return Q_PROFORMA

# ── BUYER NOTIFICATION HELPER ──────────────────────────────────────────────────

async def _notify_buyer_of_quote(context, qd, supplier, quote):
    try:
        po    = get_po(qd['po_id'])
        buyer = get_buyer_by_id(po['buyer_id'])
        if not buyer: return
        buyer_bot = Bot(token=BUYER_BOT_TOKEN)
        tg  = f"@{supplier.get('tg_username','')}" if supplier.get('tg_username') else "_(no username)_"
        msg = (
            f"💬 *New response on {po.get('po_code','')}*\n\n"
            f"*{supplier.get('business_name','—')}* responded.\n\n"
            f"💵 *Offer:* {qd.get('price_text','—')}\n"
            f"🚚 *Delivery:* {qd.get('delivery_text','—')}\n"
            f"📝 *Notes:* {qd.get('notes','—') or '—'}\n\n"
            f"{'─'*26}\n"
            f"📱 Phone: {supplier.get('phone','—')}\n"
            f"💬 Telegram: {tg}\n"
            f"{'─'*26}\n"
            f"_Contact them directly or wait for more quotes._\n"
            f"_via Habesha Build Hub_ 🏗️"
        )
        await buyer_bot.send_message(buyer['telegram_id'], msg, parse_mode="Markdown")
        mark_buyer_notified(quote['quote_id'])
    except Exception as e:
        logger.warning(f"Buyer notification failed: {e}")

# ── FALLBACK ───────────────────────────────────────────────────────────────────

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    supplier = get_supplier(update.effective_user.id)
    if supplier and supplier.get('business_name'):
        await update.message.reply_text("Use the menu below 👇", reply_markup=supplier_menu_kb())
    else:
        await update.message.reply_text("Send /start to begin.")

async def error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}", exc_info=context.error)

# ── BUILD ──────────────────────────────────────────────────────────────────────

def build_supplier_app():
    app = Application.builder().token(SUPPLIER_BOT_TOKEN).build()

    cancel_cb = CallbackQueryHandler(cancel_to_menu, pattern=r"^(quote|proforma):cancel$")

    onboarding = ConversationHandler(
        per_chat=True,
        per_user=True,
        per_message=True,
        entry_points=[CommandHandler("start", start)],
        states={
            S_CATS:    [CallbackQueryHandler(cat_toggle, pattern=r"^scat:")],
            S_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, got_name)],
            S_CITY:    [CallbackQueryHandler(got_city,    pattern=r"^scity:")],
            S_PHONE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, got_phone)],
            S_CONFIRM: [CallbackQueryHandler(got_license, pattern=r"^(license:|smenu:main)")],
        },
        fallbacks=[CommandHandler("cancel", cancel_to_menu), cancel_cb],
        allow_reentry=True,
    )

    quote_conv = ConversationHandler(
        per_chat=True,
        per_user=True,
        per_message=True,
        entry_points=[CallbackQueryHandler(start_quote, pattern=r"^quoterpo:")],
        states={
            Q_TYPE: [
                CallbackQueryHandler(quote_type_text, pattern=r"^qtype:text:"),
                CallbackQueryHandler(quote_type_file, pattern=r"^qtype:file:"),
                CallbackQueryHandler(cancel_to_menu,  pattern=r"^quote:cancel$"),
                CallbackQueryHandler(cancel_to_menu,  pattern=r"^smenu:main$"),
            ],
            Q_PRICE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, got_price)],
            Q_DELIVERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_delivery)],
            Q_NOTES:    [MessageHandler(filters.TEXT & ~filters.COMMAND, got_notes)],
            Q_CONFIRM: [
                CallbackQueryHandler(quote_confirm_handler, pattern=r"^quote:"),
                CallbackQueryHandler(cancel_to_menu, pattern=r"^smenu:main$"),
            ],
            Q_PROFORMA: [
                # File sent
                MessageHandler(
                    (filters.Document.ALL | filters.PHOTO) & ~filters.COMMAND,
                    got_proforma_file
                ),
                # Note text after file uploaded
                MessageHandler(filters.TEXT & ~filters.COMMAND, proforma_note),
                # Confirm button
                CallbackQueryHandler(proforma_confirm, pattern=r"^proforma:"),
                CallbackQueryHandler(cancel_to_menu,   pattern=r"^quote:cancel$"),
                CallbackQueryHandler(cancel_to_menu,   pattern=r"^smenu:main$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_to_menu), cancel_cb],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("getfile", getfile_cmd))
    app.add_handler(onboarding)
    app.add_handler(quote_conv)
    app.add_handler(CallbackQueryHandler(smenu_callback, pattern=r"^smenu:"))
    app.add_handler(CallbackQueryHandler(skip_lead,      pattern=r"^skiplead:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))
    app.add_error_handler(error_handler)
    return app

