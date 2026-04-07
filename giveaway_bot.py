import os
import sqlite3
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ================== ቅንብሮች (ከ Railway Variables) ==================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID_INPUT = os.getenv("CHANNEL_ID")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

# የቻናል መታወቂያ አስተካክል
CHANNEL_ID = CHANNEL_ID_INPUT.strip()
if CHANNEL_ID.isdigit():
    CHANNEL_ID = int(CHANNEL_ID)
elif CHANNEL_ID.startswith('-') and CHANNEL_ID[1:].isdigit():
    CHANNEL_ID = int(CHANNEL_ID)

# ሎግ
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ================== የውሂብ ጎታ ማቀናበር (ሊሚትን ጨምሮ) ==================
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
    # ነባሪ ሊሚት 5 እና ተሳታፊ ቆጣሪ
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
    """ሁሉንም ተሳታፊዎች ለማጥፋት (አስተዳዳሪ ብቻ)"""
    conn = sqlite3.connect("giveaway.db")
    c = conn.cursor()
    c.execute("DELETE FROM participants")
    c.execute("UPDATE bot_state SET value = '0' WHERE key = 'participant_count'")
    conn.commit()
    conn.close()

# ================== ለአድሚን ማሳወቂያ ==================
async def notify_admin(context: ContextTypes.DEFAULT_TYPE, user_id, username, full_name, current_count, max_limit):
    if not ADMIN_CHAT_ID:
        return
    message = (
        f"🎉 **አዲስ ተሳታፊ ተመዝግቧል!**\n\n"
        f"👤 ሙሉ ስም: {full_name}\n"
        f"🆔 መታወቂያ: `{user_id}`\n"
        f"📛 ስም: @{username if username else 'የለም'}\n"
        f"🔢 ተራ ቁጥር: {current_count}/{max_limit}\n"
        f"📅 ጊዜ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"አድሚን ማሳወቅ አልተቻለም: {e}")

# ================== የቦት ትዕዛዞች ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    full_name = update.effective_user.full_name

    if is_already_registered(user_id):
        await update.message.reply_text("✅ ቀድመው ተመዝግበዋል! መልካም እድል።")
        return

    max_limit = get_max_limit()
    current_count = get_participant_count()
    if current_count >= max_limit:
        await update.message.reply_text(f"⚠️ ሽልማቱ አልቋል! (ከፍተኛ {max_limit} ተሳታፊዎች)")
        return

    try:
        await update.message.reply_text(f"🔍 የቻናል አባልነት እየተረጋገጠ ነው...\n📌 የቻናል መታወቂያ: `{CHANNEL_ID}`")
        chat_member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if chat_member.status in ["member", "administrator", "creator"]:
            register_user(user_id, username, full_name)
            new_count = get_participant_count()
            await update.message.reply_text(
                f"🎉 እንኳን ደስ አለዎት! 100$ ሽልማት አግኝተዋል!\n"
                f"✅ ተመዝግበዋል - {new_count}/{max_limit}"
            )
            await notify_admin(context, user_id, username, full_name, new_count, max_limit)
        else:
            await update.message.reply_text("❌ fail! በመጀመሪያ ቻናላችንን ይቀላቀሉ።")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Membership error: {error_msg}")
        if "Chat not found" in error_msg or "USER_ID_INVALID" in error_msg:
            await update.message.reply_text(
                "❌ የቻናል መታወቂያ ስህተት ወይም ቦት አስተዳዳሪ አይደለም።\n"
                "እባክዎ አስተዳዳሪውን ያነጋግሩ።"
            )
        else:
            await update.message.reply_text(f"❌ ቴክኒካል ችግር: {error_msg[:150]}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = get_participant_count()
    max_limit = get_max_limit()
    remaining = max_limit - count
    await update.message.reply_text(
        f"📊 የሽልማት ሁኔታ\n"
        f"👥 ተመዝጋቢዎች: {count}/{max_limit}\n"
        f"✨ የቀረ: {remaining}"
    )

async def list_participants(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ ለአድሚን ብቻ።")
        return
    participants = get_all_participants()
    if not participants:
        await update.message.reply_text("📭 ምንም ተመዝጋቢ የለም።")
        return
    message = "📋 **የተመዘገቡ ተሳታፊዎች**\n\n"
    for idx, (uid, uname, fname, reg_time) in enumerate(participants, 1):
        reg_time_str = reg_time.split('.')[0]
        message += f"{idx}. **{fname}**\n   🆔 `{uid}`\n   📛 @{uname if uname else 'የለም'}\n   🕒 {reg_time_str}\n\n"
    await update.message.reply_text(message, parse_mode="Markdown")

async def set_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """አድሚን ሊሚት ለማስቀመጥ: /setlimit 10"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ ይህ ትዕዛዝ ለአድሚን ብቻ ነው።")
        return
    try:
        new_limit = int(context.args[0])
        if new_limit < 1:
            raise ValueError
        current_count = get_participant_count()
        if new_limit < current_count:
            await update.message.reply_text(
                f"⚠️ አዲሱ ገደብ {new_limit} ከአሁን ተሳታፊዎች ቁጥር ({current_count}) ያነሰ ነው። "
                f"ከፈለጉ በመጀመሪያ /reset በማድረግ ዝርዝሩን ያጥፉ።"
            )
            return
        set_max_limit(new_limit)
        await update.message.reply_text(f"✅ ከፍተኛ ተሳታፊዎች ገደብ ወደ {new_limit} ተቀይሯል።")
    except (IndexError, ValueError):
        await update.message.reply_text("❗ እባክዎ ትክክለኛ ቁጥር ይስጡ። ለምሳሌ: `/setlimit 10`")

async def get_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """አሁን ያለውን ሊሚት ለማየት"""
    max_limit = get_max_limit()
    await update.message.reply_text(f"📏 አሁን ያለው ከፍተኛ ተሳታፊዎች ቁጥር: **{max_limit}**", parse_mode="Markdown")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ሁሉንም ተሳታፊዎች ለማጥፋት (አድሚን ብቻ)"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ ለአድሚን ብቻ።")
        return
    reset_participants()
    await update.message.reply_text("🗑️ ሁሉም ተሳታፊዎች ተወግደዋል። ቆጣሪ ወደ 0 ተመልሷል።")

async def test_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """የቻናል መታወቂያ ለመሞከር"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ ለአድሚን ብቻ።")
        return
    try:
        chat = await context.bot.get_chat(chat_id=CHANNEL_ID)
        await update.message.reply_text(
            f"✅ ቻናሉ ተገኝቷል!\n"
            f"📛 ርዕስ: {chat.title}\n"
            f"🆔 መታወቂያ: `{chat.id}`\n"
            f"🔒 የግል ነው? {'አዎ' if chat.username is None else 'አይ'}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ ቻናሉ አልተገኘም። ስህተት: {e}")

# ================== ቦቱን ማስነሳት ==================
def main():
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN አልተዋቀረም!")
        return
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("list", list_participants))
    app.add_handler(CommandHandler("setlimit", set_limit))
    app.add_handler(CommandHandler("getlimit", get_limit))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("testchannel", test_channel))
    logger.info("Bot is polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
