#!/usr/bin/env python3
"""Apply additional bug fixes for supplier notification"""

def fix_notify_buyer():
    """Fix BUG 2: Better error handling in _notify_buyer_of_quote"""
    fpath = r'c:\Users\dell\OneDrive\Desktop\hbh_bot_v6\hbh_bot\handlers\supplier_bot.py'
    
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    old = '''async def _notify_buyer_of_quote(context, qd, supplier, quote):
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
        logger.warning(f"Buyer notification failed: {e}")'''
    
    new = '''async def _notify_buyer_of_quote(context, qd, supplier, quote):
    """Notify buyer of text quote from supplier."""
    try:
        po    = get_po(qd['po_id'])
        buyer = get_buyer_by_id(po['buyer_id'])
        
        if not buyer:
            logger.error(f"_notify_buyer: Buyer {po['buyer_id']} not found for quote {quote['quote_id']}")
            return
        
        if not buyer.get('telegram_id'):
            logger.error(f"_notify_buyer: Buyer {buyer['buyer_id']} has no telegram_id")
            return
        
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
        
        logger.debug(f"_notify_buyer: Sending quote notification to buyer {buyer['telegram_id']} for PO {po['po_code']}")
        
        await buyer_bot.send_message(buyer['telegram_id'], msg, parse_mode="Markdown")
        mark_buyer_notified(quote['quote_id'])
        logger.info(f"_notify_buyer: Quote notification sent to buyer {buyer['telegram_id']}")
        
    except TelegramError as e:
        logger.error(f"_notify_buyer: Telegram error notifying buyer: {type(e).__name__} - {e}")
    except Exception as e:
        logger.error(f"_notify_buyer: Unexpected error notifying buyer: {e}", exc_info=e)'''
    
    if old in content:
        content = content.replace(old, new)
        print('✓ Fixed _notify_buyer_of_quote error handling')
    else:
        print('✗ _notify_buyer_of_quote section not found')
    
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    fix_notify_buyer()
    print("✅ Supplier notification fixes applied")
