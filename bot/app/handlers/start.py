"""Start command and top-level menu navigation."""

from __future__ import annotations

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.ext import ContextTypes

from app.config import WEBAPP_URL


def main_menu_keyboard(
    *,
    is_private: bool = True,
    bot_username: str = "",
    chat_id: int = 0,
) -> InlineKeyboardMarkup:
    """Build the main-menu inline keyboard."""
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton("🗄️ My Pantry", callback_data="menu:pantry")],
        [InlineKeyboardButton("📂 Categories", callback_data="menu:categories")],
        [InlineKeyboardButton("🔍 Review Products", callback_data="menu:review")],
    ]

    # Webapp scanner button (works differently in groups vs private)
    if WEBAPP_URL and not is_private and bot_username:
        rows.append([
            InlineKeyboardButton(
                "📷 Scan Items",
                url=f"https://t.me/{bot_username}?start=scan_{chat_id}",
            )
        ])
    elif not WEBAPP_URL:
        rows.append([
            InlineKeyboardButton(
                "📷 Scan Items (send photo)",
                callback_data="menu:scan_info",
            )
        ])

    rows.append([
        InlineKeyboardButton("❓ Help", callback_data="menu:help"),
    ])
    return InlineKeyboardMarkup(rows)


def scanner_reply_keyboard(mode: str = "add") -> ReplyKeyboardMarkup | None:
    """Build a persistent reply keyboard with the webapp scanner button.

    ``sendData()`` only works when the Mini App is opened from a KeyboardButton.
    """
    if not WEBAPP_URL:
        return None
    url = f"{WEBAPP_URL}?mode={mode}" if "?" not in WEBAPP_URL else f"{WEBAPP_URL}&mode={mode}"
    return ReplyKeyboardMarkup(
        [
            [
                KeyboardButton("🗄️ Pantry"),
                KeyboardButton("📂 Categories"),
                KeyboardButton("🔍 Review"),
            ],
            [
                KeyboardButton(f"📷 Scan to {'Add' if mode == 'add' else 'Remove'}", web_app=WebAppInfo(url=url)),
            ],
        ],
        resize_keyboard=True,
    )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle ``/start`` and ``/help``."""
    is_private = update.effective_chat.type == "private"  # type: ignore[union-attr]
    bot_username = context.bot.username or ""

    # Ensure default categories exist for this owner
    from app.handlers.pantry import _ensure_owner_categories
    await _ensure_owner_categories(update, context)

    # Deep-link: /start scan  or  /start scan_<group_chat_id>
    if is_private and context.args and context.args[0].startswith("scan"):
        payload = context.args[0]
        if "_" in payload:
            try:
                group_chat_id = int(payload.split("_", 1)[1])
                context.user_data["scan_target_chat"] = group_chat_id
            except (ValueError, IndexError):
                pass

        reply_kb = scanner_reply_keyboard("add")
        if reply_kb:
            await update.message.reply_text(  # type: ignore[union-attr]
                "📷 Tap the *Scan Items* button below to open the scanner:",
                reply_markup=reply_kb,
                parse_mode="Markdown",
            )
            return

    text = (
        "👋 Welcome to *Pantry Bot*!\n\n"
        "I help you keep track of what's in your pantry.\n"
        "Scan barcodes when you come back from groceries to add items, "
        "and scan again when you use them up to remove them.\n\n"
        "Choose an option below:"
    )
    if is_private:
        reply_kb = scanner_reply_keyboard("add")
        if reply_kb:
            await update.message.reply_text(  # type: ignore[union-attr]
                text,
                reply_markup=reply_kb,
                parse_mode="Markdown",
            )
            return
    await update.message.reply_text(  # type: ignore[union-attr]
        text,
        reply_markup=main_menu_keyboard(
            is_private=is_private,
            bot_username=bot_username,
            chat_id=update.effective_chat.id,  # type: ignore[union-attr]
        ),
        parse_mode="Markdown",
    )


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle generic ``menu:*`` callbacks (help, back, scan_info)."""
    query = update.callback_query
    assert query is not None
    await query.answer()

    action = query.data.split(":")[1]  # type: ignore[union-attr]

    if action == "help":
        await query.edit_message_text(
            "📖 *How to use Pantry Bot:*\n\n"
            "1️⃣ *Scan to add* — Scan barcodes of items you bought\n"
            "2️⃣ *Scan to remove* — Scan barcodes of items you used up\n"
            "3️⃣ *View pantry* — /pantry to see what\'s in stock\n"
            "4️⃣ *Categories* — Organize items into Pantry, Fridge, Freezer, etc.\n"
            "5️⃣ *Review* — Confirm auto-detected product names\n\n"
            "Product names are automatically looked up from Open Food Facts.\n"
            "The bot works in private chats and groups.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="menu:back")],
            ]),
            parse_mode="Markdown",
        )
    elif action == "scan_info":
        await query.edit_message_text(
            "📷 *Scan items*\n\n"
            "Use the scanner button in the keyboard to scan barcodes continuously.\n"
            "You can scan multiple items in one session!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="menu:back")],
            ]),
            parse_mode="Markdown",
        )
    elif action == "back":
        is_private = update.effective_chat.type == "private"  # type: ignore[union-attr]
        bot_username = context.bot.username or ""
        await query.edit_message_text(
            "Choose an option:",
            reply_markup=main_menu_keyboard(
                is_private=is_private,
                bot_username=bot_username,
                chat_id=update.effective_chat.id,  # type: ignore[union-attr]
            ),
        )
