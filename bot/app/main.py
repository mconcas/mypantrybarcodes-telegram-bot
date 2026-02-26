"""Pantry Bot — entry point."""

from __future__ import annotations

import logging

from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
)

from app.config import LOG_LEVEL, OPENSEARCH_HOST, OPENSEARCH_PORT, TELEGRAM_BOT_TOKEN
from app.handlers.categories import (
    build_add_category_conversation,
    categories_command,
    category_delete_cb,
)
from app.handlers.pantry import (
    pantry_category_cb,
    pantry_command,
    pantry_delete_cb,
)
from app.handlers.review import (
    build_review_conversation,
    review_action_cb,
    review_command,
)
from app.handlers.scan import build_webapp_scan_conversation
from app.handlers.start import menu_callback, start_command
from app.services.opensearch_client import OpenSearchClient


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s %(name)-30s  %(levelname)-7s  %(message)s",
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    )
    logger = logging.getLogger(__name__)

    # ── OpenSearch ────────────────────────────────────────────────────
    os_client = OpenSearchClient(OPENSEARCH_HOST, OPENSEARCH_PORT)
    os_client.wait_for_cluster()
    os_client.init_indices()
    logger.info("OpenSearch ready")

    # ── Telegram application ──────────────────────────────────────────
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.bot_data["os_client"] = os_client

    # 1. WebApp scan conversation (catches WEB_APP_DATA first)
    app.add_handler(build_webapp_scan_conversation())

    # 2. Add-category conversation
    app.add_handler(build_add_category_conversation())

    # 3. Review rename conversation
    app.add_handler(build_review_conversation())

    # 4. Slash commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", start_command))
    app.add_handler(CommandHandler("pantry", pantry_command))
    app.add_handler(CommandHandler("categories", categories_command))
    app.add_handler(CommandHandler("review", review_command))

    # 5. Callback-query handlers (most-specific patterns first)
    app.add_handler(CallbackQueryHandler(pantry_command, pattern=r"^menu:pantry$"))
    app.add_handler(CallbackQueryHandler(categories_command, pattern=r"^menu:categories$"))
    app.add_handler(CallbackQueryHandler(review_command, pattern=r"^menu:review$"))

    app.add_handler(CallbackQueryHandler(pantry_category_cb, pattern=r"^pantry:cat:"))
    app.add_handler(CallbackQueryHandler(pantry_delete_cb, pattern=r"^pantry:del:"))

    app.add_handler(CallbackQueryHandler(category_delete_cb, pattern=r"^catdel:"))

    app.add_handler(CallbackQueryHandler(review_action_cb, pattern=r"^rev:"))

    app.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu:"))

    logger.info("Starting polling …")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
