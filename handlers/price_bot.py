"""
Habesha Build Hub — PRICE BOT v3
Categories pulled from DB, not hardcoded.
"""
import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from config import PRICE_BOT_TOKEN
from models.database import get_latest_prices
from keyboards.builders import price_cat_kb, kb
from utils.messages import fmt_price_report

logging.basicConfig(format="%(asctime)s [PRICE] %(levelname)s %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

WELCOME = (
    "💰 *HBH Material Price Bot*\n\n"
    "Real-time construction material prices in Ethiopia.\n"
    "Updated weekly from verified suppliers.\n\n"
    "Select a category:"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME, parse_mode="Markdown",
                                     reply_markup=price_cat_kb())

async def price_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    cat = q.data.split(":",1)[1]
    if cat == "back":
        await q.edit_message_text(WELCOME, parse_mode="Markdown",
                                   reply_markup=price_cat_kb()); return
    prices = get_latest_prices()
    report = fmt_price_report(prices, None if cat == "all" else cat)
    await q.edit_message_text(
        report, parse_mode="Markdown",
        reply_markup=kb([
            [("↩️ Another Category", "price:back")],
            [("📢 Join @hbhmarketprice for weekly updates", "price:sub")],
        ])
    )

async def sub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(
        "📢 *Stay Updated*\n\n"
        "Join our free weekly price alert channel:\n"
        "👉 @hbhmarketprice\n\n"
        "Also join our main community:\n"
        "👉 https://t.me/habeshabuildethio\n\n"
        "_Every Tuesday: full material price update across Addis Ababa._",
        parse_mode="Markdown",
        reply_markup=kb([[("↩️ Back", "price:back")]])
    )

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Use /start to check prices 💰",
                                     reply_markup=price_cat_kb())

async def error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}", exc_info=context.error)

def build_price_app():
    app = Application.builder().token(PRICE_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(sub_callback,  pattern=r"^price:sub$"))
    app.add_handler(CallbackQueryHandler(price_query,   pattern=r"^price:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))
    app.add_error_handler(error_handler)
    return app
