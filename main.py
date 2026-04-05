import os
import subprocess
import logging
import yt_dlp
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- ያንተ Token ---
TOKEN = "8721985752:AAGRKd_vhMq2K_iW5SKxcxZooxlEHWznkeQ"

# Render እንዳይዘጋው የሚያደርግ ትንሿ የዌብ ሰርቨር
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Running")

def run_health_check():
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

def process_video(input_path, output_path):
    # Glow, Sharpness እና Color Saturation የሚጨምር ፊልተር
    video_filters = (
        "scale=720:-2:flags=lanczos,"
        "split[main][blur];"
        "[blur]boxblur=15:3,scale=iw:ih[glow];"
        "[main][glow]blend=all_mode='screen':all_opacity=0.35,"
        "unsharp=5:5:1.5:5:5:0.0,"
        "eq=saturation=1.8:contrast=1.2"
    )
    command = [
        'ffmpeg', '-y', '-i', input_path,
        '-vf', video_filters,
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-preset', 'ultrafast', '-crf', '20',
        '-c:a', 'copy', output_path
    ]
    try:
        subprocess.run(command, check=True, timeout=300)
        return True
    except:
        return False

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if any(p in url for p in ["tiktok.com", "instagram.com", "youtube.com", "shorts", "reels"]):
        status = await update.message.reply_text("🎬 በማውረድ ላይ... ⏳")
        input_f, output_f = f"in_{update.message.chat_id}.mp4", f"out_{update.message.chat_id}.mp4"
        try:
            ydl_opts = {'outtmpl': input_f, 'format': 'best', 'quiet': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                await asyncio.to_thread(ydl.download, [url])
            
            await status.edit_text("✨ ጥራት እና Glow እየጨመርኩ ነው... 🚀")
            success = await asyncio.get_event_loop().run_in_executor(None, process_video, input_f, output_f)
            
            if success and os.path.exists(output_f):
                await status.edit_text("✅ ተጠናቀቀ! በመላክ ላይ...")
                with open(output_f, 'rb') as v:
                    await update.message.reply_video(video=v, caption="🔥 Premium Quality Edit")
            else:
                with open(input_f, 'rb') as v:
                    await update.message.reply_video(video=v, caption="Original Video (Edit Failed)")
        except Exception as e:
            await update.message.reply_text(f"❌ ስህተት፦ {str(e)[:50]}")
        finally:
            for f in [input_f, output_f]:
                if os.path.exists(f): os.remove(f)

if __name__ == '__main__':
    # የጤና ምርመራ ሰርቨሩን በሌላ Thread ማስጀመር (ለ Render)
    Thread(target=run_health_check, daemon=True).start()
    
    # ቦቱን ማስጀመር
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("🚀 ቦቱ በ Render ላይ ስራ ጀምሯል...")
    app.run_polling(drop_pending_updates=True)
