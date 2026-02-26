"""Pantry CRUD handlers — list, add-single, delete."""

from __future__ import annotations

import logging
from collections import Counter

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.config import DEFAULT_CATEGORIES
from app.services.opensearch_client import OpenSearchClient

logger = logging.getLogger(__name__)


def _os(context: ContextTypes.DEFAULT_TYPE) -> OpenSearchClient:
    return context.bot_data["os_client"]


def _owner_id(update: Update) -> int:
    """Return owner: user_id in private chats, chat_id in groups."""
    chat = update.effective_chat
    if chat and chat.type != "private":
        return chat.id
    return update.effective_user.id  # type: ignore[union-attr]


async def _ensure_owner_categories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Make sure the default categories exist for this owner."""
    owner = _owner_id(update)
    _os(context).ensure_categories(owner, DEFAULT_CATEGORIES)


# =====================================================================
#  /pantry — list items
# =====================================================================

async def pantry_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show categories as top-level entry into pantry view."""
    await _ensure_owner_categories(update, context)
    owner = _owner_id(update)
    categories = _os(context).get_categories(owner)

    is_cb = update.callback_query is not None
    if is_cb:
        await update.callback_query.answer()  # type: ignore[union-attr]

    if not categories:
        text = "📂 No categories yet. Use /categories to add one."
        if is_cb:
            await update.callback_query.edit_message_text(text)  # type: ignore[union-attr]
        else:
            await update.message.reply_text(text)  # type: ignore[union-attr]
        return

    # Show category buttons with item counts
    rows: list[list[InlineKeyboardButton]] = []
    for cat in categories:
        items = _os(context).get_items(owner, category=cat)
        count = sum(i.get("quantity", 1) for i in items)
        label = f"📦 {cat} ({count} item{'s' if count != 1 else ''})"
        rows.append([InlineKeyboardButton(label, callback_data=f"pantry:cat:{cat}")])

    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="menu:back")])

    text = "🗄️ *Your Pantry*\n\nSelect a category to view items:"
    kb = InlineKeyboardMarkup(rows)
    if is_cb:
        await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")  # type: ignore[union-attr]
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")  # type: ignore[union-attr]


async def pantry_category_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show items in a specific category."""
    query = update.callback_query
    assert query is not None
    if not context.user_data.pop("_skip_answer", False):
        await query.answer()

    # Extract category — callback_data is "pantry:cat:<name>"
    category = ":".join(query.data.split(":")[2:])  # type: ignore[union-attr]
    owner = _owner_id(update)
    items = _os(context).get_items(owner, category=category)

    if not items:
        await query.edit_message_text(
            f"📦 *{category}* is empty!\n\nScan some items to add them.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back to Pantry", callback_data="menu:pantry")],
            ]),
            parse_mode="Markdown",
        )
        return

    # Group by barcode, sum quantities
    grouped: dict[str, dict] = {}
    for item in items:
        bc = item["barcode"]
        if bc not in grouped:
            grouped[bc] = {
                "barcode": bc,
                "product_name": item["product_name"],
                "quantity": 0,
                "verified": item.get("verified", False),
                "oldest_id": item["id"],
                "added_at": item.get("added_at", ""),
            }
        grouped[bc]["quantity"] += item.get("quantity", 1)

    lines = []
    rows: list[list[InlineKeyboardButton]] = []
    for bc, info in grouped.items():
        verified_mark = "✅" if info["verified"] else "❓"
        name = info["product_name"] or bc
        lines.append(f"{verified_mark} *{name}* × {info['quantity']}")
        rows.append([
            InlineKeyboardButton(
                f"➕ {name[:20]}",
                callback_data=f"pantry:add:{bc}:{category}",
            ),
            InlineKeyboardButton(
                f"🗑️ {name[:20]}",
                callback_data=f"pantry:del:{bc}:{category}",
            ),
        ])

    rows.append([InlineKeyboardButton("⬅️ Back to Pantry", callback_data="menu:pantry")])

    text = f"📦 *{category}* ({len(grouped)} product{'s' if len(grouped) != 1 else ''}):\n\n"
    text += "\n".join(lines)
    text += "\n\nUse ➕ to add one unit or 🗑️ to remove one."

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode="Markdown",
    )


async def pantry_delete_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete one unit of an item by barcode."""
    query = update.callback_query
    assert query is not None

    # callback_data: "pantry:del:<barcode>:<category>"
    parts = query.data.split(":")  # type: ignore[union-attr]
    barcode = parts[2]
    category = ":".join(parts[3:]) if len(parts) > 3 else None

    owner = _owner_id(update)
    deleted = _os(context).delete_items_by_barcode(owner, barcode, category=category, limit=1)

    if deleted:
        await query.answer("🗑️ Removed one unit", show_alert=False)
    else:
        await query.answer("❌ Item not found", show_alert=True)

    # Refresh the category view — skip answer since we already answered above
    context.user_data["_skip_answer"] = True
    query.data = f"pantry:cat:{category}" if category else "menu:pantry"
    await pantry_category_cb(update, context)


async def pantry_add_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add one more unit of an existing item by barcode."""
    query = update.callback_query
    assert query is not None

    # callback_data: "pantry:add:<barcode>:<category>"
    parts = query.data.split(":")  # type: ignore[union-attr]
    barcode = parts[2]
    category = ":".join(parts[3:]) if len(parts) > 3 else "Pantry"

    owner = _owner_id(update)
    # Find existing item to copy its product_name / verified status
    existing = _os(context).find_items_by_barcode(owner, barcode, category=category)
    if existing:
        product_name = existing[0].get("product_name", f"Unknown ({barcode})")
        verified = existing[0].get("verified", False)
    else:
        product_name = f"Unknown ({barcode})"
        verified = False

    _os(context).add_item(
        owner_id=owner,
        barcode=barcode,
        product_name=product_name,
        category=category,
        quantity=1,
        verified=verified,
    )
    await query.answer("➕ Added one unit", show_alert=False)

    # Refresh the category view — skip answer since we already answered above
    context.user_data["_skip_answer"] = True
    query.data = f"pantry:cat:{category}"
    await pantry_category_cb(update, context)
