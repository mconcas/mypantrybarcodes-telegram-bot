"""Review handler — verify auto-detected product names."""

from __future__ import annotations

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

from app.handlers.pantry import _os, _owner_id

logger = logging.getLogger(__name__)

# Conversation state: user is typing a corrected name
TYPING_NAME = 0


# =====================================================================
#  /review — show unverified items one by one
# =====================================================================

async def review_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the next unverified item for review."""
    owner = _owner_id(update)
    unverified = _os(context).get_unverified_items(owner)

    is_cb = update.callback_query is not None
    if is_cb:
        await update.callback_query.answer()  # type: ignore[union-attr]

    if not unverified:
        text = "✅ All items have been reviewed! Nothing to verify."
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data="menu:back")],
        ])
        if is_cb:
            await update.callback_query.edit_message_text(text, reply_markup=kb)  # type: ignore[union-attr]
        else:
            await update.message.reply_text(text, reply_markup=kb)  # type: ignore[union-attr]
        return

    item = unverified[0]
    remaining = len(unverified)
    context.user_data["review_barcode"] = item["barcode"]

    text = (
        f"🔍 *Review Product* ({remaining} remaining)\n\n"
        f"Barcode: `{item['barcode']}`\n"
        f"Auto-detected name: *{item['product_name']}*\n"
        f"Category: {item.get('category', '?')}\n\n"
        "Is this name correct?"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Correct", callback_data=f"rev:ok:{item['barcode']}"),
            InlineKeyboardButton("✏️ Rename", callback_data=f"rev:rename:{item['barcode']}"),
        ],
        [
            InlineKeyboardButton("⏭️ Skip", callback_data="rev:skip"),
            InlineKeyboardButton("❌ Done", callback_data="rev:done"),
        ],
    ])

    if is_cb:
        await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")  # type: ignore[union-attr]
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")  # type: ignore[union-attr]


async def review_action_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    """Handle review actions: ok, rename, skip, done."""
    query = update.callback_query
    assert query is not None
    await query.answer()

    parts = query.data.split(":")  # type: ignore[union-attr]
    action = parts[1]

    if action == "done":
        await query.edit_message_text("✅ Review session ended.")
        return ConversationHandler.END if context.user_data.get("_in_review_conv") else None

    if action == "skip":
        # Show next unverified
        await review_command(update, context)
        return None

    barcode = ":".join(parts[2:]) if len(parts) > 2 else ""
    owner = _owner_id(update)

    if action == "ok":
        count = _os(context).verify_items_by_barcode(owner, barcode)
        await query.answer(f"✅ Verified {count} item(s)", show_alert=False)
        # Show next
        await review_command(update, context)
        return None

    if action == "rename":
        context.user_data["review_barcode"] = barcode
        context.user_data["_in_review_conv"] = True
        await query.edit_message_text(
            f"✏️ Type the correct product name for barcode `{barcode}`:",
            parse_mode="Markdown",
        )
        return TYPING_NAME

    return None


async def review_received_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User typed a corrected product name."""
    new_name = update.message.text.strip()  # type: ignore[union-attr]
    barcode = context.user_data.pop("review_barcode", "")
    context.user_data.pop("_in_review_conv", None)

    if not new_name or not barcode:
        await update.message.reply_text("❌ Cancelled.")  # type: ignore[union-attr]
        return ConversationHandler.END

    owner = _owner_id(update)
    count = _os(context).verify_items_by_barcode(owner, barcode, new_name=new_name)

    # Also update the product cache
    _os(context).cache_product(barcode=barcode, product_name=new_name)

    await update.message.reply_text(  # type: ignore[union-attr]
        f"✅ Renamed {count} item(s) to *{new_name}* and marked as verified.\n\n"
        "Use /review to continue reviewing.",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def review_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel review."""
    context.user_data.pop("review_barcode", None)
    context.user_data.pop("_in_review_conv", None)
    await update.message.reply_text("❌ Review cancelled.")  # type: ignore[union-attr]
    return ConversationHandler.END


def build_review_conversation() -> ConversationHandler:
    """Return the review ConversationHandler for rename flow."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(review_action_cb, pattern=r"^rev:rename:"),
        ],
        states={
            TYPING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, review_received_name),
            ],
        },
        fallbacks=[CommandHandler("cancel", review_cancel)],
        per_user=True,
        per_chat=True,
    )
