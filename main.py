import os
import sqlite3
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ================== ቅንብሮች ==================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # የአድሚኑ የቴሌግራም መታወቂያ (user id)
MAX_PARTICIPANTS = 5

# ሎግ ማቀናበር
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ================== የውሂብ ጎታ ማቀናበር ==================
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

# ================== ለአድሚን መልእክት መላኪያ ==================
async def notify_admin(context: ContextTypes.DEFAULT_TYPE, user_id, username, full_name, current_count):
    if not ADMIN_CHAT_ID:
        logger.warning("ADMIN_CHAT_ID አልተዋቀረም! ማሳወቂያ አልተላከም።")
        return
    message = (
        f"🎉 **አዲስ ተሳታፊ ተመዝግቧል!**\n\n"
        f"👤 ሙሉ ስም: {full_name}\n"
        f"🆔 የተጠቃሚ መታወቂያ: `{user_id}`\n"
        f"📛 የተጠቃሚ ስም: @{username if username else 'የለም'}\n"
        f"🔢 ተራ ቁጥር: {current_count}/{MAX_PARTICIPANTS}\n"
        f"📅 የተመዘገበበት ጊዜ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message, parse_mode="Markdown")
        logger.info(f"አድሚን ለ {user_id} መመዝገብ ታውቋል")
    except Exception as e:
        logger.error(f"አድሚን ማሳወቅ አልተቻለም: {e}")

# ================== የቦት ትዕዛዞች ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    full_name = update.effective_user.full_name

    # 1. ተጠቃሚው ቀድሞ ተመዝግቧል?
    if is_already_registered(user_id):
        await update.message.reply_text("✅ ቀድመው በሽልማቱ ውድድር ተመዝግበዋል! መልካም እድል ይሁንልዎት።")
        return

    # 2. ሽልማቱ አልቋል? (5 ሰዎች)
    current_count = get_participant_count()
    if current_count >= MAX_PARTICIPANTS:
        await update.message.reply_text("⚠️ እንደ አለመታደል ሆኖ 100$ ሽልማቱ አልቋል! ደንበኛ በመሆን ለቀጣይ ዝግጅታችን ይጠብቁን።")
        return

    # 3. የPrivate Channel አባልነት ማረጋገጥ
    try:
        chat_member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if chat_member.status in ["member", "administrator", "creator"]:
            # ተመዝግብ!
            register_user(user_id, username, full_name)
            new_count = get_participant_count()
            await update.message.reply_text(
                f"🎉 እንኳን ደስ አለዎት! በቻናላችን ውስጥ በመገኘትዎ 100$ ሽልማት አግኝተዋል!\n"
                f"✅ ተመዝግበዋል - {new_count}/{MAX_PARTICIPANTS}"
            )
            # ✨ ለአድሚን ማሳወቅ
            await notify_admin(context, user_id, username, full_name, new_count)
        else:
            await update.message.reply_text("❌ fail! እባክዎ በመጀመሪያ ቻናላችንን ይቀላቀሉና ከዚያ /start ይጫኑ።")
    except Exception as e:
        logger.error(f"Error checking membership for {user_id}: {e}")
        await update.message.reply_text("❌ ቴክኒካል ችግር አጋጥሟል። እባክዎ ቆይተው ይሞክሩ።")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = get_participant_count()
    remaining = MAX_PARTICIPANTS - count
    await update.message.reply_text(
        f"📊 የሽልማት ሁኔታ\n"
        f"👥 ተመዝጋቢዎች፦ {count}/{MAX_PARTICIPANTS}\n"
        f"✨ የቀረ፦ {remaining}"
    )

async def list_participants(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ይህን ትዕዛዝ ማየት የሚችለው አድሚኑ ብቻ ነው
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ ይህ ትዕዛዝ ለአድሚኑ ብቻ ነው።")
        return

    participants = get_all_participants()
    if not participants:
        await update.message.reply_text("📭 እስካሁን ምንም ተመዝጋቢ የለም።")
        return

    message = "📋 **የተመዘገቡ ተሳታፊዎች**\n\n"
    for idx, (uid, uname, fname, reg_time) in enumerate(participants, 1):
        reg_time_str = reg_time.split('.')[0]  # ሚሊሰከንዶችን አስወግድ
        message += (
            f"{idx}. **{fname}**\n"
            f"   🆔 `{uid}`\n"
            f"   📛 @{uname if uname else 'የለም'}\n"
            f"   🕒 {reg_time_str}\n\n"
        )
    # መልእክቱ በጣም ረጅም ከሆነ በርካታ ክፍሎች ማድረግ ያስፈልጋል (ግን 5 ብቻ ስለሆነ ይህ በቂ ነው)
    await update.message.reply_text(message, parse_mode="Markdown")

# ================== ቦቱን ማስነሳት ==================
def main():
    if not TOKEN or not CHANNEL_ID:
        logger.error("TELEGRAM_BOT_TOKEN ወይም CHANNEL_ID አልተዋቀረም!")
        return
    if not ADMIN_CHAT_ID:
        logger.warning("ADMIN_CHAT_ID አልተዋቀረም - ለአድሚን ማሳወቂያ አይላክም።")

    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("list", list_participants))  # አዲስ
    logger.info("Bot is polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
