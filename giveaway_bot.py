import os
import sqlite3
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ================== CONFIGURATION (from Railway Variables) ==================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID_INPUT = os.getenv("CHANNEL_ID")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # Admin's Telegram user ID

# Normalize channel ID
CHANNEL_ID = CHANNEL_ID_INPUT.strip()
if CHANNEL_ID.isdigit():
    CHANNEL_ID = int(CHANNEL_ID)
elif CHANNEL_ID.startswith('-') and CHANNEL_ID[1:].isdigit():
    CHANNEL_ID = int(CHANNEL_ID)

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================== DATABASE FUNCTIONS ==================
def init_db():
    conn = sqlite3.connect("giveaway.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            registered_at TIMESTAMP
        )
    """)
    c.execute("CREATE TABLE IF NOT EXISTS bot_state (key TEXT PRIMARY KEY, value TEXT)")
    c.execute("INSERT OR IGNORE INTO bot_state (key, value) VALUES ('participant_count', '0')")
    c.execute("INSERT OR IGNORE INTO bot_state (key, value) VALUES ('max_limit', '5')")
    conn.commit()
    conn.close()

def get_participant_count():
    conn = sqlite3.connect("giveaway.db")
    c = conn.cursor()
    c.execute("SELECT value FROM bot_state WHERE key = 'participant_count'")
    count = int(c.fetchone()[0])
    conn.close()
    return count

def increment_participant_count():
    conn = sqlite3.connect("giveaway.db")
    c = conn.cursor()
    c.execute("UPDATE bot_state SET value = value + 1 WHERE key = 'participant_count'")
    conn.commit()
    conn.close()

def get_max_limit():
    conn = sqlite3.connect("giveaway.db")
    c = conn.cursor()
    c.execute("SELECT value FROM bot_state WHERE key = 'max_limit'")
    limit = int(c.fetchone()[0])
    conn.close()
    return limit

def set_max_limit(new_limit):
    if new_limit < 1:
        new_limit = 1
    conn = sqlite3.connect("giveaway.db")
    c = conn.cursor()
    c.execute("UPDATE bot_state SET value = ? WHERE key = 'max_limit'", (str(new_limit),))
    conn.commit()
    conn.close()
    logger.info(f"Max limit updated to {new_limit}")

def is_already_registered(user_id):
    conn = sqlite3.connect("giveaway.db")
    c = conn.cursor()
    c.execute("SELECT 1 FROM participants WHERE user_id = ?", (user_id,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

def register_user(user_id, username, full_name):
    conn = sqlite3.connect("giveaway.db")
    c = conn.cursor()
    c.execute("INSERT INTO participants (user_id, username, full_name, registered_at) VALUES (?, ?, ?, ?)",
              (user_id, username, full_name, datetime.now()))
    conn.commit()
    conn.close()
    increment_participant_count()

def get_all_participants():
    conn = sqlite3.connect("giveaway.db")
    c = conn.cursor()
    c.execute("SELECT user_id, username, full_name, registered_at FROM participants ORDER BY registered_at")
    rows = c.fetchall()
    conn.close()
    return rows

def reset_participants():
    conn = sqlite3.connect("giveaway.db")
    c = conn.cursor()
    c.execute("DELETE FROM participants")
    c.execute("UPDATE bot_state SET value = '0' WHERE key = 'participant_count'")
    conn.commit()
    conn.close()
    logger.info("All participants have been reset.")

# ================== ADMIN NOTIFICATION ==================
async def notify_admin(context: ContextTypes.DEFAULT_TYPE, user_id, username, full_name, current_count, max_limit):
    if not ADMIN_CHAT_ID:
        return
    message = (
        f"🆕 **New participant registered**\n\n"
        f"👤 Full name: `{full_name}`\n"
        f"🆔 User ID: `{user_id}`\n"
        f"📛 Username: @{username if username else 'None'}\n"
        f"🔢 Count: `{current_count}` of `{max_limit}`\n"
        f"📅 Registered at: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
        f"💰 This participant has won the $100 giveaway."
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message, parse_mode="Markdown")
        logger.info(f"Admin notified for new participant {user_id}")
    except Exception as e:
        logger.error(f"Failed to notify admin: {e}")

# ================== BOT COMMANDS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    full_name = update.effective_user.full_name

    if is_already_registered(user_id):
        await update.message.reply_text(
            "ℹ️ You have already registered for this program.\n"
            "For more information, please contact support."
        )
        return

    max_limit = get_max_limit()
    current_count = get_participant_count()
    if current_count >= max_limit:
        await update.message.reply_text(
            "📭 Unfortunately, all participation slots are now full.\n"
            "Please stay tuned for future opportunities."
        )
        return

    try:
        await update.message.reply_text("🔍 Please wait, verifying your information...")
        chat_member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if chat_member.status in ["member", "administrator", "creator"]:
            register_user(user_id, username, full_name)
            new_count = get_participant_count()
            await update.message.reply_text(
                "✅ Your participation has been successfully recorded.\n"
                "Thank you!"
            )
            await notify_admin(context, user_id, username, full_name, new_count, max_limit)
        else:
            await update.message.reply_text(
                "❌ Sorry, your eligibility could not be confirmed.\n"
                "Please ensure you have joined the required channel and try again."
            )
    except Exception as e:
        error_message = str(e)
        logger.error(f"Membership check error for {user_id}: {error_message}")
        if "Chat not found" in error_message or "USER_ID_INVALID" in error_message:
            await update.message.reply_text(
                "⚠️ A technical issue occurred. Please try again later or contact support."
            )
            if ADMIN_CHAT_ID:
                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=f"⚠️ Channel verification error\nUser: {user_id}\nError: {error_message[:200]}"
                )
        else:
            await update.message.reply_text(
                "❌ An unexpected error occurred. Please try again later."
            )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = get_participant_count()
    max_limit = get_max_limit()
    remaining = max_limit - count
    await update.message.reply_text(
        f"📊 **Participation Status**\n\n"
        f"👥 Registered participants: `{count}`\n"
        f"🎯 Maximum limit: `{max_limit}`\n"
        f"✨ Slots remaining: `{remaining}`",
        parse_mode="Markdown"
    )

async def list_participants(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Command not found.")
        return
    participants = get_all_participants()
    if not participants:
        await update.message.reply_text("📭 No participants have registered yet.")
        return
    message = "📋 **Registered Participants**\n\n"
    for idx, (uid, uname, fname, reg_time) in enumerate(participants, 1):
        reg_time_str = reg_time.split('.')[0]
        message += (
            f"**{idx}.** {fname}\n"
            f"   🆔 `{uid}`\n"
            f"   📛 @{uname if uname else 'None'}\n"
            f"   🕒 {reg_time_str}\n\n"
        )
    await update.message.reply_text(message, parse_mode="Markdown")

async def set_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Command not found.")
        return
    try:
        new_limit = int(context.args[0])
        if new_limit < 1:
            raise ValueError
        current_count = get_participant_count()
        if new_limit < current_count:
            await update.message.reply_text(
                f"⚠️ The new limit (`{new_limit}`) is less than the current participant count (`{current_count}`).\n"
                f"If you wish to proceed, first use `/reset` to clear the list."
            )
            return
        set_max_limit(new_limit)
        await update.message.reply_text(f"✅ Maximum participant limit has been updated. New limit: `{new_limit}`", parse_mode="Markdown")
    except (IndexError, ValueError):
        await update.message.reply_text("❗ Please provide a valid number. Example: `/setlimit 10`")

async def get_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    max_limit = get_max_limit()
    await update.message.reply_text(f"📏 Current maximum participant limit: `{max_limit}`", parse_mode="Markdown")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Command not found.")
        return
    reset_participants()
    await update.message.reply_text("🗑️ All participants have been cleared. The counter has been reset to zero.")

async def test_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Command not found.")
        return
    try:
        chat = await context.bot.get_chat(chat_id=CHANNEL_ID)
        await update.message.reply_text(
            f"✅ Channel found!\n"
            f"📛 Title: `{chat.title}`\n"
            f"🆔 ID: `{chat.id}`\n"
            f"🔒 Private: `{'Yes' if chat.username is None else 'No'}`",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Channel not found. Error: `{e}`", parse_mode="Markdown")

# ================== START BOT ==================
def main():
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set!")
        return
    if not CHANNEL_ID:
        logger.error("CHANNEL_ID not set!")
        return

    init_db()
    app = Application.builder().token(TOKEN).build()
    
    # Public commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("getlimit", get_limit))
    
    # Admin-only commands (hidden from regular users)
    app.add_handler(CommandHandler("list", list_participants))
    app.add_handler(CommandHandler("setlimit", set_limit))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("testchannel", test_channel))
    
    logger.info("Bot is polling...")
    logger.info(f"Configured for channel: {CHANNEL_ID}")
    app.run_polling()

if __name__ == "__main__":
    main()
