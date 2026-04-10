import os
import sqlite3
import logging
import json
from datetime import datetime
from typing import Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ================== ቅንብሮች ==================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # አስተዳዳሪ የተጠቃሚ መታወቂያ
PRIVATE_CHANNEL_ID = os.getenv("PRIVATE_CHANNEL_ID")  # ለምሳሌ -1001234567890
BOT_REFERRAL_LINK = os.getenv("EXNESS_REFERRAL_LINK")  # የእርስዎ Exness ማጣቀሻ ሊንክ

# ሎግ
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ================== የውሂብ ጎታ ==================
def init_db():
    conn = sqlite3.connect("ms_trading.db")
    c = conn.cursor()
    # ተጠቃሚዎች
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            created_at TIMESTAMP
        )
    """)
    # ጥያቄዎች (requests)
    c.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            request_type TEXT,
            payment_method TEXT,
            data TEXT,
            status TEXT,
            admin_reason TEXT,
            created_at TIMESTAMP,
            approved_at TIMESTAMP
        )
    """)
    # ቻናል ኢንቫይት ሊንክ ለማስታወስ (አድሚን ሊያዘምነው ይችላል)
    c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('channel_invite_link', '')")
    conn.commit()
    conn.close()

def add_user(user_id, username, full_name):
    conn = sqlite3.connect("ms_trading.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, full_name, created_at) VALUES (?, ?, ?, ?)",
              (user_id, username, full_name, datetime.now()))
    conn.commit()
    conn.close()

def save_request(user_id, request_type, payment_method, data):
    conn = sqlite3.connect("ms_trading.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO requests (user_id, request_type, payment_method, data, status, created_at)
        VALUES (?, ?, ?, ?, 'pending', ?)
    """, (user_id, request_type, payment_method, json.dumps(data), datetime.now()))
    request_id = c.lastrowid
    conn.commit()
    conn.close()
    return request_id

def update_request_status(request_id, status, reason=None):
    conn = sqlite3.connect("ms_trading.db")
    c = conn.cursor()
    if status == "approved":
        c.execute("UPDATE requests SET status = ?, admin_reason = ?, approved_at = ? WHERE id = ?",
                  (status, reason, datetime.now(), request_id))
    else:
        c.execute("UPDATE requests SET status = ?, admin_reason = ? WHERE id = ?",
                  (status, reason, request_id))
    conn.commit()
    conn.close()

def get_pending_requests():
    conn = sqlite3.connect("ms_trading.db")
    c = conn.cursor()
    c.execute("SELECT id, user_id, request_type, payment_method, data, created_at FROM requests WHERE status = 'pending' ORDER BY created_at")
    rows = c.fetchall()
    conn.close()
    return rows

def get_user_requests(user_id):
    conn = sqlite3.connect("ms_trading.db")
    c = conn.cursor()
    c.execute("SELECT id, request_type, status, admin_reason, created_at, approved_at FROM requests WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_channel_invite_link():
    conn = sqlite3.connect("ms_trading.db")
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = 'channel_invite_link'")
    row = c.fetchone()
    conn.close()
    return row[0] if row else ""

def set_channel_invite_link(link):
    conn = sqlite3.connect("ms_trading.db")
    c = conn.cursor()
    c.execute("UPDATE settings SET value = ? WHERE key = 'channel_invite_link'", (link,))
    conn.commit()
    conn.close()

# ================== ቦት መገልገያ ተግባራት ==================
async def generate_invite_link(context: ContextTypes.DEFAULT_TYPE) -> str:
    """በቻናሉ ላይ አዲስ ጊዜያዊ የግብዣ አገናኝ ይፍጠሩ (ከ30 ቀን ጊዜ ጋር)"""
    try:
        invite_link = await context.bot.create_chat_invite_link(
            chat_id=PRIVATE_CHANNEL_ID,
            member_limit=1,  # ለአንድ ተጠቃሚ ብቻ
            expire_date=int((datetime.now().timestamp() + 30 * 24 * 3600))
        )
        return invite_link.invite_link
    except Exception as e:
        logger.error(f"Failed to create invite link: {e}")
        return None

async def send_admin_notification(context: ContextTypes.DEFAULT_TYPE, request_id: int, user_id: int, request_type: str, payment_method: str, data: dict):
    """ለአስተዳዳሪ አዲስ ጥያቄ ማሳወቂያ ይላካል"""
    user = await context.bot.get_chat(user_id)
    user_name = user.full_name or user.username or str(user_id)
    text = (
        f"🆕 **አዲስ ጥያቄ #{request_id}**\n\n"
        f"👤 ተጠቃሚ: {user_name} (ID: `{user_id}`)\n"
        f"📦 ዓይነት: {request_type}\n"
        f"💳 የክፍያ ዘዴ: {payment_method}\n"
        f"📝 ዝርዝር:\n```json\n{json.dumps(data, indent=2, ensure_ascii=False)}\n```\n"
        f"✅ ለማጽደቅ: `/approve {request_id}`\n"
        f"❌ ለመውደቅ: `/reject {request_id} [ምክንያት]`"
    )
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, parse_mode="Markdown")

async def notify_user_approved(context: ContextTypes.DEFAULT_TYPE, user_id: int, request_id: int, invite_link: str):
    """ጥያቄ ሲጸደቅ ለተጠቃሚ ማሳወቂያ እና ሊንክ መላክ"""
    text = (
        f"✅ **በሚገባ ተረጋግጧል!**\n\n"
        f"እንኳን ደስ አለዎት! የ Ms Trading ኮርስ ማግኘት ችለዋል።\n\n"
        f"🔐 የግል ቻናላችንን ለመቀላቀል ከታች ያለውን አገናኝ ይጫኑ፦\n"
        f"{invite_link}\n\n"
        f"📚 መልካም ትምህርት!"
    )
    await context.bot.send_message(chat_id=user_id, text=text)

async def notify_user_rejected(context: ContextTypes.DEFAULT_TYPE, user_id: int, request_id: int, reason: str):
    """ጥያቄ ሲውድቅ ለተጠቃሚ ማሳወቂያ"""
    text = f"❌ **ጥያቄዎ #{request_id} ውድቅ ተደርጓል**\n\nምክንያት: {reason if reason else 'አልተገለጸም'}\n\nእባክዎ እንደገና ለማመልከት ይሞክሩ።"
    await context.bot.send_message(chat_id=user_id, text=text)

# ================== የማያቋርጥ ቁልፍ ሰሌዳዎች ==================
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ዋና ምናሌ"""
    keyboard = [
        [InlineKeyboardButton("📚 Ms Trading Full Course - 500 Birr", callback_data="course_500")],
        [InlineKeyboardButton("🔄 Ms Trading Full Course - IB Change", callback_data="course_ib")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = (
        "🌟 **Welcome to Ms Trading!** 🌟\n\n"
        "Choose your preferred method to get the full course:\n\n"
        "💵 **500 Birr** – Payment via Telebirr\n"
        "🔄 **IB Change** – Exness IB change (free but requires action)\n\n"
        "Select an option below:"
    )
    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        await update.callback_query.answer()
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

# ================== የኮርስ ግዢ በ500 ብር ==================
async def course_500_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    # ማስገቢያ ውሂብ ማከማቸት
    context.user_data['payment_method'] = 'telebirr'
    context.user_data['request_type'] = 'course_500'
    await query.message.edit_text(
        "💵 **የ500 ብር ክፍያ**\n\n"
        "እባክዎ 500 ብር በTeleBirr ወደ ቁጥር **09XXXXXXXX** ይላኩ።\n"
        "ከዚያ የክፍያ ማስረጃ (screenshot) ይላኩልኝ።\n\n"
        "በቀጥታ ስክሪንሾቱን ይላኩ።"
    )

async def handle_telebirr_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ተጠቃሚ የሚልከውን ፎቶ ይቀበላል"""
    user_id = update.effective_user.id
    if context.user_data.get('payment_method') != 'telebirr':
        await update.message.reply_text("❌ እባክዎ መጀመሪያ ከምናሌው ይምረጡ። /start ይጫኑ።")
        return
    
    photo = update.message.photo[-1] if update.message.photo else None
    if not photo:
        await update.message.reply_text("❌ እባክዎ የክፍያ ማስረጃ ፎቶ ይላኩ።")
        return
    
    # ፎቶውን ማውረድ እንችላለን ግን ለአስተዳዳሪ ማሳወቂያ በቂ ነው
    data = {
        "proof_photo_id": photo.file_id,
        "caption": update.message.caption or ""
    }
    request_id = save_request(user_id, "course_500", "telebirr", data)
    await send_admin_notification(context, request_id, user_id, "Ms Trading Course (500 Birr)", "TeleBirr", data)
    await update.message.reply_text(
        "✅ የክፍያ ማስረጃዎ ለአስተዳዳሪ ተልኳል።\n"
        "እባክዎ ማጽደቂያ ይጠብቁ። ከተጸደቀ የቻናል አገናኝ ይላክልዎታል።"
    )
    # ንጹህ ማድረግ
    context.user_data.clear()

# ================== የIB Change ሂደት ==================
async def course_ib_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['request_type'] = 'course_ib'
    keyboard = [
        [InlineKeyboardButton("✅ አሁን ነባር Exness አካውንት አለኝ", callback_data="ib_existing")],
        [InlineKeyboardButton("🆕 አዲስ አካውንት መፍጠር እፈልጋለሁ", callback_data="ib_new")],
        [InlineKeyboardButton("🔙 ተመለስ", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text(
        "🔄 **Exness IB Change**\n\n"
        "እባክዎ ሁኔታዎን ይምረጡ፦",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def ib_existing_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['ib_type'] = 'existing'
    # ደረጃ በደረጃ መመሪያ
    steps = (
        "📌 **የIB Change መመሪያ (ለነባር ተጠቃሚ)**\n\n"
        "1️⃣ ወደ Exness ድረ-ገጽ ይግቡ ወይም አፕ ይክፈቱ።\n"
        "2️⃣ ከSupport ጋር ቻት ይክፈቱ።\n"
        "3️⃣ ይህን መልእክት ይላኩላቸው: *\"I want to change my IB\"*\n"
        "4️⃣ እነሱ ለእርስዎ ሊንክ ይልካሉ።\n"
        "5️⃣ ሊንኩን ጠቅ አድርገው የሚቀጥሉትን ደረጃዎች ይከተሉ።\n"
        "6️⃣ ሂደቱን ካጠናቀቁ በኋላ *ከታች* የስክሪን ሾት ይላኩልኝ።\n\n"
        "📎 የእኔ IB መታወቂያ ለመጠቀም ከላይ በሂደቱ ውስጥ ይህን ይጠቀሙ: **[የእርስዎ IB ኮድ እዚህ ይግቡ]**\n\n"
        "✅ ሂደቱን ከጨረሱ በኋላ 'ሂደቱን ጨረስኩ' የሚል አዝራር ይጫኑ።"
    )
    keyboard = [[InlineKeyboardButton("✅ ሂደቱን ጨረስኩ - ማስረጃ ላክ", callback_data="ib_existing_proof")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text(steps, reply_markup=reply_markup, parse_mode="Markdown")

async def ib_existing_proof_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['awaiting_proof'] = 'ib_existing'
    await query.message.edit_text(
        "📸 እባክዎ የተጠናቀቀውን የIB Change ማስረጃ ስክሪንሾት ይላኩልኝ።\n"
        "(ማሳያ: ስኬታማ መሆኑን የሚያሳይ ገጽ)"
    )

async def ib_new_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['ib_type'] = 'new'
    steps = (
        "🆕 **አዲስ Exness አካውንት መፍጠሪያ**\n\n"
        f"1️⃣ ከዚህ በታች ባለው ሊንክ ይመዝገቡ:\n{BOT_REFERRAL_LINK}\n\n"
        "2️⃣ ሙሉ መረጃዎን ይሙሉ እና አካውንትዎን ያረጋግጡ (verify).\n"
        "3️⃣ አካውንት ቁጥርዎን እና የተረጋገጠ ማስረጃ ስክሪንሾት ይላኩልኝ።\n\n"
        "✅ ከተመዘገቡ በኋላ 'ማስረጃ ላክ' የሚለውን ይጫኑ።"
    )
    keyboard = [[InlineKeyboardButton("✅ ተመዝግቤያለሁ - ማስረጃ ላክ", callback_data="ib_new_proof")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text(steps, reply_markup=reply_markup, parse_mode="Markdown")

async def ib_new_proof_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['awaiting_proof'] = 'ib_new'
    await query.message.edit_text(
        "📸 እባክዎ የአካውንት ቁጥርዎን እና የተረጋገጠ ማስረጃ ስክሪንሾት ይላኩልኝ።\n"
        "ማሳያ: የተመዘገቡበት ገጽ ወይም የአካውንት ውሂብ ገጽ።"
    )

async def handle_ib_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """የIB change ማስረጃ ፎቶ ሲላክ"""
    user_id = update.effective_user.id
    if 'awaiting_proof' not in context.user_data:
        await update.message.reply_text("❌ እባክዎ መጀመሪያ ከምናሌው ይምረጡ። /start ይጫኑ።")
        return
    
    photo = update.message.photo[-1] if update.message.photo else None
    if not photo:
        await update.message.reply_text("❌ እባክዎ ስክሪንሾት (ፎቶ) ይላኩ።")
        return
    
    caption = update.message.caption or ""
    proof_type = context.user_data['awaiting_proof']
    data = {
        "type": proof_type,
        "photo_id": photo.file_id,
        "caption": caption
    }
    # ተጨማሪ መረጃ ከሆነ ከcaption ማውጣት ይቻላል
    if proof_type == 'ib_new' and caption:
        data["account_number"] = caption.strip()
    
    request_id = save_request(user_id, "course_ib", "ib_change", data)
    await send_admin_notification(context, request_id, user_id, "Ms Trading Course (IB Change)", "IB Change", data)
    await update.message.reply_text(
        "✅ ማስረጃዎ ለአስተዳዳሪ ተልኳል። እባክዎ ማጽደቂያ ይጠብቁ።"
    )
    context.user_data.clear()

# ================== የአስተዳዳሪ ትዕዛዞች ==================
async def admin_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ ያልተፈቀደ።")
        return
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("❗ አጠቃቀም: /approve <request_id> [ምክንያት]")
        return
    request_id = int(args[0])
    reason = " ".join(args[1:]) if len(args) > 1 else "Approved by admin"
    
    # ጥያቄውን አግኝ
    conn = sqlite3.connect("ms_trading.db")
    c = conn.cursor()
    c.execute("SELECT user_id, request_type FROM requests WHERE id = ? AND status = 'pending'", (request_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        await update.message.reply_text("❌ ጥያቄው አልተገኘም ወይም አስቀድሞ ተፈቷል።")
        return
    user_id = row[0]
    
    # አዲስ የቻናል ግብዣ አገናኝ ፍጠር
    invite_link = await generate_invite_link(context)
    if not invite_link:
        await update.message.reply_text("⚠️ የቻናል አገናኝ መፍጠር አልተቻለም። ቦቱ በቻናሉ አስተዳዳሪ መሆኑን ያረጋግጡ።")
        return
    
    update_request_status(request_id, "approved", reason)
    await notify_user_approved(context, user_id, request_id, invite_link)
    await update.message.reply_text(f"✅ ጥያቄ #{request_id} ጸድቋል። ለተጠቃሚ ቻናል አገናኝ ተልኳል።")
    
    # አማራጭ: ማስረጃ ፎቶውን ማስቀመጥ ከፈለጉ እዚህ ማከል ይችላሉ

async def admin_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ ያልተፈቀደ።")
        return
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("❗ አጠቃቀም: /reject <request_id> [ምክንያት]")
        return
    request_id = int(args[0])
    reason = " ".join(args[1:]) if len(args) > 1 else "No reason provided"
    
    conn = sqlite3.connect("ms_trading.db")
    c = conn.cursor()
    c.execute("SELECT user_id FROM requests WHERE id = ? AND status = 'pending'", (request_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        await update.message.reply_text("❌ ጥያቄው አልተገኘም ወይም አስቀድሞ ተፈቷል።")
        return
    user_id = row[0]
    
    update_request_status(request_id, "rejected", reason)
    await notify_user_rejected(context, user_id, request_id, reason)
    await update.message.reply_text(f"❌ ጥያቄ #{request_id} ውድቅ ተደርጓል። ምክንያት: {reason}")

async def admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ ያልተፈቀደ።")
        return
    pending = get_pending_requests()
    if not pending:
        await update.message.reply_text("📭 ምንም በመጠባበቅ ላይ ያለ ጥያቄ የለም።")
        return
    text = "⏳ **በመጠባበቅ ላይ ያሉ ጥያቄዎች:**\n\n"
    for req in pending:
        req_id, uid, rtype, pmethod, data_json, created = req
        data = json.loads(data_json)
        text += f"🆔 #{req_id} | {rtype} | {pmethod}\n   ተጠቃሚ: `{uid}`\n   ጊዜ: {created}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def admin_set_channel_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """አስተዳዳሪ ቋሚ የቻናል አገናኝ ማዘጋጀት ከፈለገ (አማራጭ)"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ ያልተፈቀደ።")
        return
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("❗ /setlink <invite_link>")
        return
    link = " ".join(args)
    set_channel_invite_link(link)
    await update.message.reply_text(f"✅ ቻናል አገናኝ ተቀምጧል።")

# ================== ሌሎች ትዕዛዞች ==================
async def my_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    requests = get_user_requests(user_id)
    if not requests:
        await update.message.reply_text("📭 እስካሁን ምንም ጥያቄ አላቀረቡም።")
        return
    text = "📋 **የእርስዎ ጥያቄዎች**\n\n"
    for req in requests:
        req_id, rtype, status, reason, created, approved_at = req
        status_emoji = "✅" if status == "approved" else "❌" if status == "rejected" else "⏳"
        text += f"{status_emoji} #{req_id} - {rtype}\n   ሁኔታ: {status}\n"
        if status == "rejected" and reason:
            text += f"   ምክንያት: {reason}\n"
        text += "\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await main_menu(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ ተሰርዟል። እንደገና ለመጀመር /start ይጫኑ።")

# ================== የመጀመሪያ መግቢያ ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id, user.username or "", user.full_name)
    await main_menu(update, context)

# ================== ዋና አሰራር ==================
def main():
    if not TOKEN or not ADMIN_CHAT_ID or not PRIVATE_CHANNEL_ID:
        logger.error("ማዋቀሪያ ተለዋዋጮች አልተዋቀሩም! TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID, PRIVATE_CHANNEL_ID ያስፈልጋሉ።")
        return
    init_db()
    app = Application.builder().token(TOKEN).build()
    
    # ትዕዛዞች
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myrequests", my_requests))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("approve", admin_approve))
    app.add_handler(CommandHandler("reject", admin_reject))
    app.add_handler(CommandHandler("listrequests", admin_list))
    app.add_handler(CommandHandler("setlink", admin_set_channel_link))
    
    # ጥያቄዎች (callback queries)
    app.add_handler(CallbackQueryHandler(main_menu, pattern="^back_main$"))
    app.add_handler(CallbackQueryHandler(course_500_start, pattern="^course_500$"))
    app.add_handler(CallbackQueryHandler(course_ib_start, pattern="^course_ib$"))
    app.add_handler(CallbackQueryHandler(ib_existing_start, pattern="^ib_existing$"))
    app.add_handler(CallbackQueryHandler(ib_new_start, pattern="^ib_new$"))
    app.add_handler(CallbackQueryHandler(ib_existing_proof_request, pattern="^ib_existing_proof$"))
    app.add_handler(CallbackQueryHandler(ib_new_proof_request, pattern="^ib_new_proof$"))
    app.add_handler(CallbackQueryHandler(back_to_main, pattern="^back_main$"))
    
    # የፎቶ አያያዝ
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_telebirr_proof))
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_ib_proof))
    
    logger.info("Bot started polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
