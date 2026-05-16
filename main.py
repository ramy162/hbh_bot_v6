"""
Habesha Build Hub — Main Launcher v3
python-telegram-bot 21.x  |  Python 3.12+
"""
import asyncio, sys, os, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.database import init_db
from handlers.buyer_bot    import build_buyer_app
from handlers.supplier_bot import build_supplier_app
from handlers.price_bot    import build_price_app
from handlers.admin_bot    import build_admin_app
from config import BUYER_BOT_TOKEN, SUPPLIER_BOT_TOKEN, PRICE_BOT_TOKEN, ADMIN_BOT_TOKEN

logging.basicConfig(format="%(asctime)s [HBH] %(levelname)s %(message)s", level=logging.INFO)
logger = logging.getLogger("HBH")

async def run_all():
    init_db()
    logger.info("📦 Database ready.")

    bots = [
        (build_buyer_app,    "Buyer",    BUYER_BOT_TOKEN),
        (build_supplier_app, "Supplier", SUPPLIER_BOT_TOKEN),
        (build_price_app,    "Price",    PRICE_BOT_TOKEN),
        (build_admin_app,    "Admin",    ADMIN_BOT_TOKEN),
    ]

    apps = []
    for builder, name, token in bots:
        if "YOUR_" in token:
            logger.warning(f"Skipping {name} — token not set"); continue
        try:
            app = builder()
            apps.append((app, name))
            logger.info(f"Built {name} bot OK")
        except Exception as e:
            logger.error(f"Could not build {name}: {e}")

    if not apps:
        logger.error("No bots started. Check tokens in config.py"); return

    for app, name in apps:
        await app.initialize()
    for app, name in apps:
        await app.start()
    for app, name in apps:
        await app.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"]
        )
        logger.info(f"🤖 {name} bot is LIVE")

    logger.info(f"🚀 ALL {len(apps)} BOTS RUNNING — Ctrl+C to stop")

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        logger.info("Shutting down...")
        for app, name in reversed(apps):
            try:
                await app.updater.stop()
                await app.stop()
                await app.shutdown()
            except Exception: pass
        logger.info("All bots stopped cleanly.")

if __name__ == "__main__":
    try:
        asyncio.run(run_all())
    except KeyboardInterrupt:
        pass
