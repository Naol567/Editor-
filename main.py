import os
import asyncio
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID  = int(os.getenv("ADMIN_ID", 0))

# --- Render Health Check ---
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"4K Edit Bot is Active")

def run_render_server():
    port = int(os.environ.get("PORT", 8000))
    httpd = HTTPServer(('0.0.0.0', port), HealthHandler)
    httpd.serve_forever()

# --- 4K High Quality Glow Filter ---
def process_video_4k(input_path, output_path):
    """
    ቪዲዮውን ወደ 4K የሚቀይር እና High Quality Glow የሚጨምር FFmpeg ትዕዛዝ
    """
    # 4K Resolution (3840x2160) እና የጥራት ማሻሻያ ፊልተሮች
    video_filters = (
        "scale=3840:2160:flags=lanczos," # ወደ 4K ከፍ ማድረጊያ
        "unsharp=5:5:1.5:5:5:0.0,"       # እጅግ በጣም እንዲጠራ (Sharpen)
        "split[main][blur];"
        "[blur]boxblur=20:5[glow];"      # ለ Glow ውጤቱ ማደብዘዣ
        "[main][glow]blend=all_mode='screen':all_opacity=0.35," # Glow መደራረቢያ
        "eq=saturation=1.9:contrast=1.4:brightness=-0.03" # ምስሉ ላይ እንዳለው ደማቅ ቀለም
    )

    command = [
        'ffmpeg', '-y', '-i', input_path,
        '-vf', video_filters,
        '-c:v', 'libx264', 
        '-preset', 'ultrafast', # Render ፍጥነት እንዲኖረው
        '-crf', '16',           # በጣም ከፍተኛ ጥራት (ዝቅተኛ ቁጥር = ከፍተኛ ጥራት)
        '-c:a', 'copy',         # ድምፁን እንዳለ መተው
        output_path
    ]
    
    try:
        subprocess.run(command, check=True)
        return True
    except Exception as e:
        print(f"FFmpeg Error: {e}")
        return False

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ሰላም! ቪዲዮ ላክልኝና ወደ **4K Ultra HQ Glow** እቀይርልሃለሁ።")

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    video = update.message.video
    status_msg = await update.message.reply_text("🎬 የ 4K Edit ስራ ተጀምሯል... ጥራቱ ከፍተኛ ስለሆነ ጥቂት ደቂቃ ሊወስድ ይችላል።")
    
    file = await context.bot.get_file(video.file_id)
    input_file = "in.mp4"
    output_file = "out_4k.mp4"
    
    await file.download_to_drive(input_file)
    
    # ፕሮሰስ ማድረግ
    success = process_video_4k(input_file, output_file)
    
    if success:
        # ለቴሌግራም ፋይሉ ትልቅ ሊሆን ስለሚችል እንደ ዶክመንት መላክ ይሻላል
        await update.message.reply_document(document=open(output_file, 'rb'), caption="✅ 4K Ultra HQ Edit ተጠናቋል!")
    else:
        await update.message.reply_text("❌ ስህተት ተፈጥሯል። ምናልባት የቪዲዮው መጠን ከባድ ሊሆን ይችላል።")
    
    if os.path.exists(input_file): os.remove(input_file)
    if os.path.exists(output_file): os.remove(output_file)
    await status_msg.delete()

async def main():
    threading.Thread(target=run_render_server, daemon=True).start()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
