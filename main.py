import os
import asyncio
import subprocess
import threading
import cv2
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from dotenv import load_dotenv

load_dotenv()

# Environment Variables
# API_ID ን ወደ Integer መቀየር ወሳኝ ነው
try:
    API_ID = int(os.getenv("API_ID", 0))
except:
    API_ID = 0
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))

client = TelegramClient('session', API_ID, API_HASH)

# --- Render Health Check ---
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"Bot is Running")

def run_render_server():
    port = int(os.environ.get("PORT", 8000))
    HTTPServer(('0.0.0.0', port), HealthHandler).serve_forever()

# --- Helpers ---
async def progress_bar(current, total, event, msg_prefix):
    percentage = current * 100 / total
    if not hasattr(progress_bar, "last_edit"): progress_bar.last_edit = 0
    if time.time() - progress_bar.last_edit > 5 or percentage == 100:
        try:
            await event.edit(f"{msg_prefix}: {percentage:.1f}% ...")
            progress_bar.last_edit = time.time()
        except: pass

def process_video_4k(input_path, output_path):
    # - High Quality Filter
    filters = (
        "scale=3840:2160:flags=lanczos,unsharp=5:5:1.5:5:5:0.0,"
        "split[main][blur];[blur]boxblur=20:5[glow];"
        "[main][glow]blend=all_mode='screen':all_opacity=0.35,"
        "eq=saturation=1.9:contrast=1.4:brightness=-0.02"
    )
    cmd = ['ffmpeg', '-y', '-i', input_path, '-vf', filters, '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18', '-c:a', 'copy', output_path]
    return subprocess.run(cmd, check=True).returncode == 0

# --- Login & Step-by-Step Handling ---

@client.on(events.NewMessage(pattern='/login'))
async def login_start(event):
    if event.sender_id != ADMIN_ID: return
    await event.respond("📱 እባክህ ስልክ ቁጥርህን በ **+251...** መልክ ላክልኝ። (ለምሳሌ፡ +251912345678)")

@client.on(events.NewMessage(func=lambda e: e.sender_id == ADMIN_ID))
async def handle_all_steps(event):
    # 1. ስልክ ቁጥር ከሆነ
    if event.text.startswith('+'):
        phone = event.text.strip()
        try:
            await client.send_code_request(phone)
            await event.respond("📩 የ 5 ድጅት ኮድ (OTP) ተልኮልሃል። እባክህ ኮዱን ብቻ ላክልኝ።")
        except FloodWaitError as e:
            await event.respond(f"⏳ ብዙ ሙከራ አድርገሃል። እባክህ ለ {e.seconds} ሰከንዶች ጠብቅ።")
        except Exception as e:
            await event.respond(f"❌ ስህተት (API ID/Hash አረጋግጥ): {e}")

    # 2. OTP ኮድ ከሆነ (5 ድጅት ቁጥር)
    elif event.text.isdigit() and len(event.text) == 5:
        try:
            await client.sign_in(code=event.text)
            await event.respond("✅ በትክክል ገብተሃል! አሁን ቪዲዮ መላክ ትችላለህ።")
        except SessionPasswordNeededError:
            await event.respond("🔐 አካውንትህ 2FA (Two-Factor) አለው። እባክህ ፓስወርድህን ላክልኝ።")
        except Exception as e:
            await event.respond(f"❌ የኮድ ስህተት: {e}")

    # 3. 2FA ፓስወርድ ከሆነ
    elif not event.text.startswith('/') and not event.video:
        try:
            await client.sign_in(password=event.text)
            await event.respond("✅ በፓስወርድህ በትክክል ገብተሃል!")
        except:
            pass # ሌሎች ሜሴጆችን ችላ እንዲል

# --- Video Processing ---
@client.on(events.NewMessage(func=lambda e: e.video))
async def handle_video(event):
    if event.sender_id != ADMIN_ID: return
    if not await client.is_user_authorized():
        await event.respond("❌ መጀመሪያ /login በማለት ስልክህን አስገባ።")
        return

    status = await event.respond("📥 በማውረድ ላይ...")
    in_f, out_f = "in.mp4", "out_4k.mp4"

    await client.download_media(event.video, in_f, progress_callback=lambda c, t: client.loop.create_task(progress_bar(c, t, status, "📥 በማውረድ ላይ")))
    
    await status.edit("🎬 ቪዲዮው እየተቀነባበረ ነው (4K Glow)...")
    success = await asyncio.to_thread(process_video_4k, in_f, out_f)

    if success:
        await status.edit("📤 ወደ ቻናል እየተጫነ ነው...")
        # - ወደ ቻናል መላክ
        channel_msg = await client.send_file(CHANNEL_ID, out_f, caption="✨ 4K Edit", supports_streaming=True)
        await client.send_message(event.chat_id, channel_msg)
        await status.delete()
    else:
        await status.edit("❌ ስህተት ተፈጥሯል።")

    for f in [in_f, out_f]:
        if os.path.exists(f): os.remove(f)

async def main():
    threading.Thread(target=run_render_server, daemon=True).start()
    # መጀመሪያ በቦት ቶክን ይጀምራል
    await client.start(bot_token=BOT_TOKEN)
    print("🚀 ቦቱ ተነስቷል!")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
