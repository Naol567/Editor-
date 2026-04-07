import os
import sqlite3
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ================== ቅንብሮች (ከ Railway Variables) ==================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID_INPUT = os.getenv("CHANNEL_ID")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # የአስተዳዳሪው የተጠቃሚ መታወቂያ

# የቻናል መታወቂያ አስተካክል
CHANNEL_ID = CHANNEL_ID_INPUT.strip()
if CHANNEL_ID.isdigit():
    CHANNEL_ID = int(CHANNEL_ID)
elif CHANNEL_ID.startswith('-') and CHANNEL_ID[1:].isdigit():
    CHANNEL_ID = int(CHANNEL_ID)

# ሎግ ማቀናበር
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================== የውሂብ ጎታ ተግባራት ==================
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
    """ሁሉንም ተሳታፊዎች ለማጥፋት (አስተዳዳሪ ብቻ)"""
    conn = sqlite3.connect("giveaway.db")
    c = conn.cursor()
    c.execute("DELETE FROM participants")
    c.execute("UPDATE bot_state SET value = '0' WHERE key = 'participant_count'")
    conn.commit()
    conn.close()
    logger.info("All participants have been reset.")

# ================== ለአስተዳዳሪ ማሳወቂያ ==================
async def notify_admin(context: ContextTypes.DEFAULT_TYPE, user_id, username, full_name, current_count, max_limit):
    """አዲስ ተሳታፊ ሲመዘገብ ለአስተዳዳሪ ማሳወቂያ ይላካል (ሽልማቱን ጨምሮ)"""
    if not ADMIN_CHAT_ID:
        return
    message = (
        f"🆕 **አዲስ ተሳታፊ ተመዝግቧል**\n\n"
        f"👤 ሙሉ ስም: `{full_name}`\n"
        f"🆔 የተጠቃሚ መታወቂያ: `{user_id}`\n"
        f"📛 የተጠቃሚ ስም: @{username if username else 'የለም'}\n"
        f"🔢 ተራ ቁጥር: `{current_count}` ከ `{max_limit}`\n"
        f"📅 የተመዘገበበት ጊዜ: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n\n"
        f"💰 confirmed ።"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message, parse_mode="Markdown")
        logger.info(f"Admin notified for new participant {user_id}")
    except Exception as e:
        logger.error(f"Failed to notify admin: {e}")

# ================== የቦት ትዕዛዞች ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    full_name = update.effective_user.full_name

    # ቀድሞ ተመዝግቧል?
    if is_already_registered(user_id):
        await update.message.reply_text(
            "ℹ️ ቀድመው በዚህ ፕሮግራም ተመዝግበዋል።\n"
            "ለተጨማሪ መረጃ እባክዎ ድጋፍ ያግኙ።"
        )
        return

    # ገደቡ አልቋል?
    max_limit = get_max_limit()
    current_count = get_participant_count()
    if current_count >= max_limit:
        await update.message.reply_text(
            "📭 እንደ አለመታደል ሆኖ በአሁኑ ጊዜ የተሳትፎ ቦታዎች አልቀዋል።\n"
            "ለቀጣይ ዝግጅቶቻችን እባክዎ ይጠብቁን።"
        )
        return

    # የPrivate Channel አባልነት ማረጋገጥ
    try:
        await update.message.reply_text("🔍 እባክዎ ይጠብቁ፣ መረጃዎ እየተረጋገጠ ነው...")
        chat_member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if chat_member.status in ["member", "administrator", "creator"]:
            # ተመዝግብ!
            register_user(user_id, username, full_name)
            new_count = get_participant_count()
            # ለተጠቃሚው ግልጽ ያልሆነ ስኬት መልእክት (ሽልማት አይጠቅስም)
            await update.message.reply_text(
                "✅ ተሳትፎዎ በሚገባ ተመዝግቧል።\n"
                "እናመሰግናለን!"
            )
            # ለአስተዳዳሪ ማሳወቂያ (ሽልማቱን ጨምሮ)
            await notify_admin(context, user_id, username, full_name, new_count, max_limit)
        else:
            await update.message.reply_text(
                "❌ ይቅርታ፣ M/s Trading private channel አልተቀላቀሉም።\n"
                "እባክዎ ለቀጣይ giveaway official ቻናላችን ላይ የተገለፀውን መስፈርት በሟሟላት ዝግጁ ይሁኑ 🔥።"
            )
    except Exception as e:
        error_message = str(e)
        logger.error(f"Membership check error for {user_id}: {error_message}")
        if "Chat not found" in error_message or "USER_ID_INVALID" in error_message:
            await update.message.reply_text(
                "⚠️ ቴክኒካል ችግር ተፈጥሯል። እባክዎ ቆይተው እንደገና ይሞክሩ ወይም ድጋፍ ያግኙ።"
            )
            if ADMIN_CHAT_ID:
                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=f"⚠️ የቻናል ማረጋገጫ ስህተት\nUser: {user_id}\nError: {error_message[:200]}"
                )
        else:
            await update.message.reply_text(
                "❌ ያልተጠበቀ ስህተት ተፈጥሯል። እባክዎ ቆይተው እንደገና ይሞክሩ።"
            )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """የአሁኑን የተሳትፎ ሁኔታ ለማሳየት (ለማንኛውም ተጠቃሚ)"""
    count = get_participant_count()
    max_limit = get_max_limit()
    remaining = max_limit - count
    await update.message.reply_text(
        f"📊 **የተሳትፎ ሁኔታ**\n\n"
        f"👥 የተመዘገቡት ቁጥር: `{count}`\n"
        f"🎯 ከፍተኛ ገደብ: `{max_limit}`\n"
        f"✨ የቀሩ ቦታዎች: `{remaining}`",
        parse_mode="Markdown"
    )

async def list_participants(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """የተመዘገቡ ተሳታፊዎችን ዝርዝር ለማሳየት (አስተዳዳሪ ብቻ)"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ ይህ ትዕዛዝ የማይገኝ ነው።")
        return
    participants = get_all_participants()
    if not participants:
        await update.message.reply_text("📭 እስካሁን ምንም ተሳታፊ አልተመዘገበም።")
        return
    message = "📋 **የተመዘገቡ ተሳታፊዎች**\n\n"
    for idx, (uid, uname, fname, reg_time) in enumerate(participants, 1):
        reg_time_str = reg_time.split('.')[0]
        message += (
            f"**{idx}.** {fname}\n"
            f"   🆔 `{uid}`\n"
            f"   📛 @{uname if uname else 'የለም'}\n"
            f"   🕒 {reg_time_str}\n\n"
        )
    await update.message.reply_text(message, parse_mode="Markdown")

async def set_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """የከፍተኛ ተሳታፊዎችን ገደብ ለማስቀመጥ (አስተዳዳሪ ብቻ)"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ ይህ ትዕዛዝ የማይገኝ ነው።")
        return
    try:
        new_limit = int(context.args[0])
        if new_limit < 1:
            raise ValueError
        current_count = get_participant_count()
        if new_limit < current_count:
            await update.message.reply_text(
                f"⚠️ አዲሱ ገደብ (`{new_limit}`) ከአሁኑ ተሳታፊዎች ቁጥር (`{current_count}`) ያነሰ ነው።\n"
                f"ከፈለጉ በመጀመሪያ `/reset` በማድረግ ዝርዝሩን ያጥፉ።"
            )
            return
        set_max_limit(new_limit)
        await update.message.reply_text(f"✅ ከፍተኛ ተሳታፊዎች ገደብ በሚገባ ተቀይሯል። አዲሱ ገደብ: `{new_limit}`", parse_mode="Markdown")
    except (IndexError, ValueError):
        await update.message.reply_text("❗ እባክዎ ትክክለኛ ቁጥር ያስገቡ። ለምሳሌ: `/setlimit 10`")

async def get_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """አሁን ያለውን ገደብ ለማሳየት"""
    max_limit = get_max_limit()
    await update.message.reply_text(f"📏 አሁን ያለው ከፍተኛ ተሳታፊዎች ቁጥር: `{max_limit}`", parse_mode="Markdown")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ሁሉንም ተሳታፊዎች ለማጥፋት (አስተዳዳሪ ብቻ)"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ ይህ ትዕዛዝ የማይገኝ ነው።")
        return
    reset_participants()
    await update.message.reply_text("🗑️ ሁሉም ተሳታፊዎች በይፋ ተወግደዋል። ቆጣሪው ወደ ዜሮ ተመልሷል።")

async def test_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """የቻናል መታወቂያ ለመፈተሽ (አስተዳዳሪ ብቻ)"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ ይህ ትዕዛዝ የማይገኝ ነው።")
        return
    try:
        chat = await context.bot.get_chat(chat_id=CHANNEL_ID)
        await update.message.reply_text(
            f"✅ ቻናሉ ተገኝቷል!\n"
            f"📛 ርዕስ: `{chat.title}`\n"
            f"🆔 መታወቂያ: `{chat.id}`\n"
            f"🔒 የግል ነው? `{'አዎ' if chat.username is None else 'አይ'}`",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ ቻናሉ አልተገኘም። ስህተት: `{e}`", parse_mode="Markdown")

# ================== ቦቱን ማስነሳት ==================
def main():
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN አልተዋቀረም!")
        return
    if not CHANNEL_ID:
        logger.error("CHANNEL_ID አልተዋቀረም!")
        return

    init_db()
    app = Application.builder().token(TOKEN).build()
    
    # ለሁሉም ተጠቃሚ የሚገኙ ትዕዛዞች
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("getlimit", get_limit))
    
    # ለአስተዳዳሪ ብቻ የሚገኙ ትዕዛዞች (እነዚህ ለሌሎች እንደሌሉ ይታያሉ)
    app.add_handler(CommandHandler("list", list_participants))
    app.add_handler(CommandHandler("setlimit", set_limit))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("testchannel", test_channel))
    
    logger.info("Bot is polling...")
    logger.info(f"Configured for channel: {CHANNEL_ID}")
    app.run_polling()

if __name__ == "__main__":
    main()
