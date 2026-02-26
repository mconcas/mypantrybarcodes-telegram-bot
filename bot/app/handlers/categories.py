"""Category management handlers."""

from __future__ import annotations

import logging

from telegram import ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.handlers.pantry import _ensure_owner_categories, _os, _owner_id

logger = logging.getLogger(__name__)

# Conversation state
NEW_CATEGORY_NAME = 0


# =====================================================================
#  /categories — list and manage
# =====================================================================

async def categories_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show categories with add/delete options."""
    await _ensure_owner_categories(update, context)
    owner = _owner_id(update)
    categories = _os(context).get_categories(owner)

    is_cb = update.callback_query is not None
    if is_cb:
        await update.callback_query.answer()  # type: ignore[union-attr]

    rows: list[list[InlineKeyboardButton]] = []
    for cat in categories:
        items = _os(context).get_items(owner, category=cat)
        count = sum(i.get("quantity", 1) for i in items)
        rows.append([
            InlineKeyboardButton(
                f"📦 {cat} ({count})",
                callback_data=f"catview:{cat}",
            ),
            InlineKeyboardButton(
                "🗑️",
                callback_data=f"catdel:{cat}",
            ),
        ])

    rows.append([InlineKeyboardButton("➕ Add Category", callback_data="catadd")])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="menu:back")])

    text = "📂 *Categories*\n\nManage your pantry categories:"
    kb = InlineKeyboardMarkup(rows)

    if is_cb:
        await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")  # type: ignore[union-attr]
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")  # type: ignore[union-attr]


async def category_delete_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a category after confirmation."""
    query = update.callback_query
    assert query is not None
    await query.answer()

    category = ":".join(query.data.split(":")[1:])  # type: ignore[union-attr]
    owner = _owner_id(update)

    # Check if category has items
    items = _os(context).get_items(owner, category=category)
    if items:
        await query.edit_message_text(
            f"⚠️ *{category}* still has {len(items)} item(s).\n"
            "Remove all items first before deleting the category.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back to Categories", callback_data="menu:categories")],
            ]),
            parse_mode="Markdown",
        )
        return

    deleted = _os(context).delete_category(owner, category)
    if deleted:
        await query.edit_message_text(
            f"✅ Category *{category}* deleted.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back to Categories", callback_data="menu:categories")],
            ]),
            parse_mode="Markdown",
        )
    else:
        await query.edit_message_text("❌ Category not found.")


# =====================================================================
#  Add-category conversation
# =====================================================================

async def add_category_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask the user for a category name."""
    query = update.callback_query
    is_group = update.effective_chat and update.effective_chat.type != "private"  # type: ignore[union-attr]
    prompt = "➕ *New Category*\n\nType the category name (e.g. \"Bathroom\"):"

    if query:
        await query.answer()
        # In groups, send a new message with ForceReply so the bot receives
        # the user's response (privacy mode blocks plain text in groups).
        if is_group:
            await query.message.reply_text(  # type: ignore[union-attr]
                prompt,
                parse_mode="Markdown",
                reply_markup=ForceReply(selective=True),
            )
        else:
            await query.edit_message_text(
                prompt,
                parse_mode="Markdown",
            )
    else:
        await update.message.reply_text(  # type: ignore[union-attr]
            prompt,
            parse_mode="Markdown",
            reply_markup=ForceReply(selective=True) if is_group else None,
        )
    return NEW_CATEGORY_NAME


async def received_category_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Create the new category."""
    name = update.message.text.strip()  # type: ignore[union-attr]
    if not name:
        await update.message.reply_text("❌ Name cannot be empty. Try again:")  # type: ignore[union-attr]
        return NEW_CATEGORY_NAME

    owner = _owner_id(update)
    success = _os(context).add_category(owner, name)

    if success:
        await update.message.reply_text(  # type: ignore[union-attr]
            f"✅ Category *{name}* created!\n\nUse /categories to manage.",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(  # type: ignore[union-attr]
            f"⚠️ Category *{name}* already exists.",
            parse_mode="Markdown",
        )
    return ConversationHandler.END


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """``/cancel`` fallback."""
    await update.message.reply_text("❌ Cancelled.")  # type: ignore[union-attr]
    return ConversationHandler.END


def build_add_category_conversation() -> ConversationHandler:
    """Return the add-category ConversationHandler."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(add_category_entry, pattern=r"^catadd$"),
        ],
        states={
            NEW_CATEGORY_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_category_name),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        per_user=True,
        per_chat=True,
    )
