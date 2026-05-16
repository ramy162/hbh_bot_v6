#!/usr/bin/env python3
"""Fix the syntax error in supplier_bot.py"""
import re

fpath = r'c:\Users\dell\OneDrive\Desktop\hbh_bot_v6\hbh_bot\handlers\supplier_bot.py'

with open(fpath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and fix the malformed got_proforma_file function
# The issue is lines 419-422 have literal \n sequences
output_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # Look for the malformed logger.warning line
    if 'got_proforma_file' in line and 'quote' in line and 'context missing' in line and '\\n' in line:
        # Replace this malformed multi-line string with correct version
        output_lines.append('    if \'quote\' not in context.user_data:\n')
        output_lines.append('        logger.warning(f"got_proforma_file: \'quote\' context missing for user {update.effective_user.id}")\n')
        output_lines.append('        context.user_data[\'quote\'] = {\'po_id\': None, \'type\': \'file\'}\n')
        # Skip the malformed lines
        i += 1
        # Find where this malformed section ends - should end at next proper Python line
        while i < len(lines):
            if lines[i].strip() == '' or (not lines[i].startswith(' '*8) and lines[i].strip() != ''):
                # Found end of malformed section
                break
            i += 1
        i -= 1  # Back up one since we'll increment at the end of the loop
    else:
        output_lines.append(line)
    
    i += 1

with open(fpath, 'w', encoding='utf-8') as f:
    f.writelines(output_lines)

print("✓ Fixed syntax error in got_proforma_file")
