"""
Habesha Build Hub — Config v3
Categories are now DB-managed (categories table).
This file only holds tokens, IDs, and conversation state constants.
"""
import os

BUYER_BOT_TOKEN    = os.getenv("BUYER_BOT_TOKEN",    "8244040673:AAFG2cCUIjwihfUwhA3_CmKzYp_gnOeuNss")
SUPPLIER_BOT_TOKEN = os.getenv("SUPPLIER_BOT_TOKEN", "8690492918:AAHM4ist_GTMPcwL8gx6V7N6zthRFo1JS78")
PRICE_BOT_TOKEN    = os.getenv("PRICE_BOT_TOKEN",    "8759019215:AAE3q5T341mZG3lLpT5-162lQ_5YyijykNA")
ADMIN_BOT_TOKEN    = os.getenv("ADMIN_BOT_TOKEN",    "8614679579:AAE-7DFSdD5S8C0Iy7RGV17w2WDcZAU-mGA")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "391373033").split(",")]

CITIES = ["Addis Ababa","Adama","Bahir Dar","Hawassa","Dire Dawa","Mekelle","Jimma","Other"]

BUYER_TYPES = {
    "contractor": "🧱 Contractor",
    "developer":  "🏢 Real Estate Developer",
    "engineer":   "⚙️ Engineer / Site Manager",
    "homeowner":  "🏠 Homeowner / Private Builder",
}

TIMELINES = {
    "today":    "Today",
    "asap":     "As soon as possible",
    "urgent":   "Within 3 days",
    "week":     "Within 1 week",
    "twoweeks": "Within 2 weeks",
    "flexible": "Flexible",
}

BUDGETS = {
    "under50": "Under 50,000 ETB",
    "50_200":  "50,000 – 200,000 ETB",
    "200_500": "200,000 – 500,000 ETB",
    "over500": "500,000+ ETB",
    "nosay":   "Prefer not to say",
}

PROJECT_TYPES = {
    "res_small":  "Residential – Small (villa/house)",
    "res_large":  "Residential – Large (apartment building)",
    "comm_small": "Commercial – Small (shop/office)",
    "comm_large": "Commercial – Large (complex/warehouse)",
}

# ── CONVERSATION STATES ────────────────────────────────────────────────────────
(B_NAME, B_PHONE, B_TYPE, B_CITY)                         = range(4)
# PO flow — quantity step removed (detail covers it)
(PO_CATS, PO_DETAIL, PO_FILE, PO_LOC, PO_TIMELINE,
 PO_BUDGET, PO_NOTES, PO_CONFIRM)                         = range(10, 18)
PO_QTY = 99   # retired — kept so old imports don't crash
# BOQ flow — clean sequential states
(BOQ_UPLOAD, BOQ_PTYPE, BOQ_SCOPE, BOQ_CONFIRM)           = range(20, 24)
(REV_SCORE, REV_COMMENT)                                   = range(30, 32)
(S_CATS, S_NAME, S_PHONE, S_CITY, S_CONFIRM)              = range(40, 45)
# Quote flow — text or file (proforma)
(Q_TYPE, Q_PRICE, Q_DELIVERY, Q_NOTES, Q_CONFIRM,
 Q_PROFORMA)                                              = range(50, 56)
(ADM_PRICE_EDIT, ADM_PRICE_ADD, ADM_CAT_ADD,
 ADM_BROADCAST_TEXT)                                       = range(70, 74)
ADM_BOQ_DELIVER_FILE = 80
ADM_BOQ_DELIVER_NOTE = 81
