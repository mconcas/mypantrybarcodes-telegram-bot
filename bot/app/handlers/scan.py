"""Handlers for the webapp barcode scan flow — add & remove items."""

from __future__ import annotations

import json
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.config import DEFAULT_CATEGORIES
from app.handlers.pantry import _ensure_owner_categories, _os, _owner_id
from app.services.product_lookup import lookup_barcode

logger = logging.getLogger(__name__)

# Conversation state: after receiving webapp data, ask for category
SELECT_CATEGORY = 0


async def _process_scan_batch(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    scans: list[dict],
    mode: str,
    category: str,
) -> str:
    """Process a batch of scanned barcodes — add or remove. Returns summary text."""
    owner = context.user_data.get("_override_owner") or _owner_id(update)
    os_client = _os(context)
    lines: list[str] = []

    if mode == "remove":
        for scan in scans:
            barcode = scan.get("code", "")
            deleted = os_client.delete_items_by_barcode(owner, barcode, category=category, limit=1)
            if deleted:
                lines.append(f"🗑️ Removed: `{barcode}`")
            else:
                lines.append(f"❌ Not found: `{barcode}`")
        return "\n".join(lines) if lines else "Nothing to remove."

    # mode == "add"
    for scan in scans:
        barcode = scan.get("code", "")
        if not barcode:
            continue

        # 1. Check product cache
        cached = os_client.get_cached_product(barcode)
        product_name = ""
        product_info: dict | None = None
        verified = False

        if cached:
            product_name = cached.get("product_name", "")
            verified = True  # already seen before
        else:
            # 2. Try Open Food Facts
            result = await lookup_barcode(barcode)
            if result:
                product_name = result["product_name"]
                product_info = result.get("raw")
                # Cache it
                os_client.cache_product(
                    barcode=barcode,
                    product_name=product_name,
                    brand=result.get("brand", ""),
                    image_url=result.get("image_url", ""),
                    raw=result.get("raw"),
                )
            else:
                product_name = f"Unknown ({barcode})"

        doc_id = os_client.add_item(
            owner_id=owner,
            barcode=barcode,
            product_name=product_name,
            category=category,
            quantity=1,
            product_info=product_info,
            verified=verified,
        )

        mark = "✅" if verified else "❓"
        lines.append(f"{mark} *{product_name}*")

    return "\n".join(lines) if lines else "No items to add."


async def webapp_scan_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry: receive barcode data from the WebApp."""
    logger.info("WebApp scan data received from user %s", update.effective_user.id)

    data = update.effective_message.web_app_data.data  # type: ignore[union-attr]
    try:
        payload = json.loads(data)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Invalid JSON from webapp: %s", data)
        await update.message.reply_text("❌ Invalid data from scanner.")  # type: ignore[union-attr]
        return ConversationHandler.END

    # payload is either a single scan or a batch:
    # Single: {"code": "...", "format": "...", "mode": "add"|"remove"}
    # Batch:  {"scans": [...], "mode": "add"|"remove"}
    mode = payload.get("mode", "add")
    scans: list[dict] = payload.get("scans", [])
    if not scans and "code" in payload:
        scans = [{"code": payload["code"], "format": payload.get("format", "")}]

    if not scans:
        await update.message.reply_text("❌ No barcodes received.")  # type: ignore[union-attr]
        return ConversationHandler.END

    # Store in user_data for category selection step
    context.user_data["scan_scans"] = scans
    context.user_data["scan_mode"] = mode

    # Ensure categories exist
    await _ensure_owner_categories(update, context)
    owner = _owner_id(update)
    categories = _os(context).get_categories(owner)

    count = len(scans)
    mode_label = "add" if mode == "add" else "remove"
    summary = f"📷 *Scanned {count} barcode{'s' if count != 1 else ''}* ({mode_label} mode)\n\n"
    for s in scans[:10]:
        summary += f"• `{s.get('code', '?')}`\n"
    if count > 10:
        summary += f"_…and {count - 10} more_\n"

    # Ask which category
    rows: list[list[InlineKeyboardButton]] = []
    for cat in categories:
        rows.append([InlineKeyboardButton(f"📦 {cat}", callback_data=f"scancat:{cat}")])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="scancat:__cancel__")])

    summary += "\nSelect the category:"

    await update.message.reply_text(  # type: ignore[union-attr]
        summary,
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode="Markdown",
    )
    return SELECT_CATEGORY


async def webapp_select_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User selected a category — process the batch."""
    query = update.callback_query
    assert query is not None
    await query.answer()

    category = query.data.split(":")[1]  # type: ignore[union-attr]

    if category == "__cancel__":
        context.user_data.pop("scan_scans", None)
        context.user_data.pop("scan_mode", None)
        await query.edit_message_text("❌ Cancelled.")
        return ConversationHandler.END

    scans = context.user_data.pop("scan_scans", [])
    mode = context.user_data.pop("scan_mode", "add")
    group_chat_id = context.user_data.pop("scan_target_chat", None)
    actual_owner_update = update

    # If scanning for a group via deep-link
    if group_chat_id:
        # Temporarily override the owner by injecting into context
        context.user_data["_override_owner"] = group_chat_id

    await query.edit_message_text("⏳ Processing…")

    try:
        summary = await _process_scan_batch(
            actual_owner_update, context, scans, mode, category
        )
    finally:
        context.user_data.pop("_override_owner", None)

    mode_emoji = "📥" if mode == "add" else "📤"
    final_text = f"{mode_emoji} *{'Added to' if mode == 'add' else 'Removed from'} {category}:*\n\n{summary}"

    if mode == "add":
        unverified = [s for s in summary.split("\n") if s.startswith("❓")]
        if unverified:
            final_text += "\n\n💡 Items marked ❓ need review. Use /review to verify product names."

    await query.edit_message_text(final_text, parse_mode="Markdown")

    # Notify group if scanning via deep-link
    if group_chat_id:
        user_name = update.effective_user.first_name  # type: ignore[union-attr]
        try:
            await context.bot.send_message(
                chat_id=group_chat_id,
                text=(
                    f"📦 *{user_name}* {'added items to' if mode == 'add' else 'removed items from'} *{category}*:\n\n"
                    f"{summary}\n\n"
                    "Use /pantry to see the full list."
                ),
                parse_mode="Markdown",
            )
        except Exception:
            logger.warning("Could not notify group %s", group_chat_id)

    return ConversationHandler.END


async def webapp_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the scan flow."""
    context.user_data.pop("scan_scans", None)
    context.user_data.pop("scan_mode", None)
    context.user_data.pop("scan_target_chat", None)
    await update.message.reply_text("❌ Cancelled.")  # type: ignore[union-attr]
    return ConversationHandler.END


def build_webapp_scan_conversation() -> ConversationHandler:
    """Return a ConversationHandler for the webapp scan → category → process flow."""
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_scan_entry),
        ],
        states={
            SELECT_CATEGORY: [
                CallbackQueryHandler(webapp_select_category, pattern=r"^scancat:"),
            ],
        },
        fallbacks=[CommandHandler("cancel", webapp_cancel)],
        per_user=True,
        per_chat=True,
    )
