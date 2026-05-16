#!/usr/bin/env python3
"""Fix bugs in HBH bot handler files"""
import os
import sys

def fix_supplier_bot_proforma():
    """Fix BUG 3: Supplier proforma delivery error handling"""
    fpath = r'c:\Users\dell\OneDrive\Desktop\hbh_bot_v6\hbh_bot\handlers\supplier_bot.py'
    
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix 1: Better error handling in proforma_confirm
    old = '''    except Exception as e:
        logger.warning(f"Proforma delivery to buyer failed: {e}")

    return ConversationHandler.END'''
    
    new = '''    except TelegramError as e:
        logger.error(f"PROFORMA_CONFIRM: Telegram error sending proforma to buyer: {type(e).__name__} - {e}")
    except Exception as e:
        logger.error(f"PROFORMA_CONFIRM: Unexpected error delivering proforma to buyer: {e}", exc_info=e)

    return ConversationHandler.END'''
    
    if old in content:
        content = content.replace(old, new)
        print('✓ Fixed proforma_confirm error handling')
    else:
        print('✗ Proforma error handling section not found')
    
    # Fix 2: Add result checking for file sending
    old2 = '''            await send_file_preview(
                bot=buyer_bot,
                chat_id=buyer['telegram_id'],
                file_id=pf['file_id'],
                filename=pf.get('file_name', 'proforma.jpg'),
                caption=caption,
                parse_mode="Markdown"
            )
            mark_buyer_notified(quote['quote_id'])'''
    
    new2 = '''            result = await send_file_preview(
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
                logger.error(f"PROFORMA_CONFIRM: send_file_preview returned False for buyer {buyer['telegram_id']}")'''
    
    if old2 in content:
        content = content.replace(old2, new2)
        print('✓ Added file send result checking')
    else:
        print('✗ File send section not found')
    
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f'✓ supplier_bot.py updated')

def fix_database_matching_logging():
    """Fix BUG 2: Add logging to supplier matching function"""
    fpath = r'c:\Users\dell\OneDrive\Desktop\hbh_bot_v6\hbh_bot\models\database.py'
    
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    old = '''def get_suppliers_matching_categories(categories):
    """Return suppliers (up to 20) that have ANY overlap with given categories."""
    suppliers = get_all_suppliers()
    matched = []
    for s in suppliers:
        try:
            sup_cats = json.loads(s.get('categories','[]'))
        except Exception:
            sup_cats = []
        if sup_cats and set(sup_cats) & set(categories):
            matched.append(s)
            if len(matched) >= 20:
                break
    return matched'''
    
    new = '''def get_suppliers_matching_categories(categories):
    """Return suppliers (up to 20) that have ANY overlap with given categories."""
    import logging
    logger = logging.getLogger(__name__)
    
    suppliers = get_all_suppliers()
    matched = []
    
    logger.info(f"Category matching: searching {len(suppliers)} suppliers for categories {categories}")
    
    for s in suppliers:
        sup_id = s.get('supplier_id', '?')
        try:
            sup_cats = json.loads(s.get('categories','[]'))
        except Exception as e:
            logger.warning(f"Failed to parse categories for supplier {sup_id}: {e}")
            sup_cats = []
        
        if sup_cats and set(sup_cats) & set(categories):
            matched.append(s)
            logger.debug(f"Matched supplier {sup_id} with categories {sup_cats}")
            if len(matched) >= 20:
                break
    
    logger.info(f"Category matching: {len(matched)}/{len(suppliers)} suppliers matched categories {categories}")
    
    return matched'''
    
    if old in content:
        content = content.replace(old, new)
        print('✓ Added logging to get_suppliers_matching_categories')
    else:
        print('✗ get_suppliers_matching_categories section not found')
    
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f'✓ database.py updated')

if __name__ == '__main__':
    print("Fixing HBH Bot production bugs...")
    fix_supplier_bot_proforma()
    fix_database_matching_logging()
    print("\n✅ All fixes applied")
