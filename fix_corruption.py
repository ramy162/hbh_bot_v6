#!/usr/bin/env python3
"""Restore supplier_bot.py file from backup and apply fixes properly"""

# This will read the file and fix the corrupted got_proforma_file section
fpath = r'c:\Users\dell\OneDrive\Desktop\hbh_bot_v6\hbh_bot\handlers\supplier_bot.py'

with open(fpath, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the corrupted got_proforma_file section
corrupted = r'''async def got_proforma_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Supplier sends a proforma file (Excel/image)."""
    # Defensive: ensure 'quote' context exists (should be set by entry point)
    if 'quote' not in context.user_data:
        logger.warning(f"got_proforma_file: 'quote' context missing for user {update.effective_user.id}\")\n        context.user_data['quote'] = {'po_id': None, 'type': 'file'}\n    \n    doc = update.message.document or (\n        update.message.photo[-1] if update.message.photo else None\n    )\n    if not doc:\n        logger.debug(f\"Q_PROFORMA: No document received from user {update.effective_user.id}\")\n        await update.message.reply_text(\n            \"Please send a file or photo, or type /cancel.\"\n        )\n        return Q_PROFORMA\n\n    try:\n        file_id   = doc.file_id\n        file_name = getattr(doc, 'file_name', 'proforma.jpg')\n        \n        # Validate file attributes\n        if not file_id:\n            logger.error(f\"Q_PROFORMA: file_id is empty for user {update.effective_user.id}\")\n            await update.message.reply_text(\"❌ File ID missing. Please try again.\")\n            return Q_PROFORMA\n        \n        # Store in context under 'proforma' dict\n        context.user_data['proforma'] = {\n            'file_id':   file_id,\n            'file_name': file_name,\n        }\n        \n        logger.info(f\"Q_PROFORMA: Stored file {file_name} (ID: {file_id[:20]}...) for user {update.effective_user.id}\")\n    except Exception as e:\n        logger.error(f\"Q_PROFORMA: Exception extracting file info: {e}\", exc_info=e)\n        await update.message.reply_text(\"❌ File processing error. Please try again.\")\n        return Q_PROFORMA'''

# Replacement with proper formatting
fixed = '''async def got_proforma_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        return Q_PROFORMA'''

if corrupted in content:
    content = content.replace(corrupted, fixed)
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✓ Fixed got_proforma_file function")
else:
    print("✗ Corrupted section not found in expected format")
    # Try to find and fix by line
    lines = content.split('\n')
    
    # Find the line with the corrupted logger.warning
    for i, line in enumerate(lines):
        if r'\")\n' in line and 'got_proforma_file' in line:
            print(f"Found corrupted line at {i+1}")
            # Extract the key parts and reconstruct properly
            lines[i] = '        logger.warning(f"got_proforma_file: \'quote\' context missing for user {update.effective_user.id}")'
            if i+1 < len(lines):
                lines[i+1] = '        context.user_data[\'quote\'] = {\'po_id\': None, \'type\': \'file\'}'
            break
    
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print("✓ Fixed via line-by-line reconstruction")
