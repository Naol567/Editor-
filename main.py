import os
import asyncio
import subprocess
import threading
import cv2
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from dotenv import load_dotenv

load_dotenv()

# Environment Variables
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))

# 'session' ፋይል Login መረጃህን እንዲይዝ ያደርጋል
client = TelegramClient('session', API_ID, API_HASH)

# --- Render Health Check ---
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"4K Pro Bot with 2FA is Active")

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

async def processing_animation(event, stop_event):
    frames = ["🎬 ቪዲዮው እየተቀነባበረ ነው .", "🎬 ቪዲዮው እየተቀነባበረ ነው ..", "🎬 ቪዲዮው እየተቀነባበረ ነው ..."]
    i = 0
    while not stop_event.is_set():
        try:
            await event.edit(frames[i % 3]); await asyncio.sleep(1.5); i += 1
        except: break

def generate_thumbnail(video_path, thumb_path):
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_MSEC, 1000)
    success, image = cap.read()
    if success: cv2.imwrite(thumb_path, image)
    cap.release()

def process_video_4k(input_path, output_path):
    filters = (
        "scale=3840:2160:flags=lanczos,unsharp=5:5:1.5:5:5:0.0,"
        "split[main][blur];[blur]boxblur=20:5[glow];"
        "[main][glow]blend=all_mode='screen':all_opacity=0.35,"
        "eq=saturation=1.9:contrast=1.4:brightness=-0.02"
    )
    cmd = ['ffmpeg', '-y', '-i', input_path, '-vf', filters, '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18', '-c:a', 'copy', output_path]
    try:
        subprocess.run(cmd, check=True)
        return True
    except: return False

# --- Login & OTP Handlers ---

@client.on(events.NewMessage(pattern='/login'))
async def login_start(event):
    if event.sender_id != ADMIN_ID: return
    await event.respond("📱 እባክህ ስልክ ቁጥርህን በ +251... መልክ ላክልኝ።")

@client.on(events.NewMessage(func=lambda e: e.sender_id == ADMIN_ID))
async def handle_login(event):
    if event.text.startswith('+'):
        phone = event.text.strip()
        await client.send_code_request(phone)
        await event.respond("📩 የ 5 ድጅት ኮድ (OTP) ተልኮልሃል። እባክህ ኮዱን ብቻ ላክልኝ።")
    
    elif event.text.isdigit() and len(event.text) == 5:
        try:
            await client.sign_in(code=event.text)
            await event.respond("✅ በትክክል ገብተሃል!")
        except SessionPasswordNeededError:
            await event.respond("🔐 አካውንትህ 2FA (Two-Factor) አለው። እባክህ ፓስወርድህን ላክልኝ።")
        except Exception as e:
            await event.respond(f"❌ ስህተት: {e}")

    elif not event.text.startswith('/') and not event.video:
        # ይህ ክፍል 2FA ፓስወርድን ለመቀበል ነው
        try:
            await client.sign_in(password=event.text)
            await event.respond("✅ በፓስወርድህ በትክክል ገብተሃል!")
        except Exception as e:
            await event.respond(f"❌ የመግቢያ ስህተት: {e}")

# --- Video Processing Handler ---

@client.on(events.NewMessage)
async def handle_video(event):
    if event.sender_id != ADMIN_ID or not event.video: return
    if not await client.is_user_authorized():
        await event.respond("❌ መጀመሪያ /login በማለት ስልክህንና ኮድህን አስገባ።")
        return

    status = await event.respond("📥 ቪዲዮውን በማውረድ ላይ: 0%")
    in_f, out_f, thumb_f = "in.mp4", "out_4k.mp4", "thumb.jpg"

    await client.download_media(event.video, in_f, progress_callback=lambda c, t: client.loop.create_task(progress_bar(c, t, status, "📥 በማውረድ ላይ")))

    stop_anim = asyncio.Event()
    anim_task = client.loop.create_task(processing_animation(status, stop_anim))
    success = await asyncio.to_thread(process_video_4k, in_f, out_f)
    stop_anim.set(); await anim_task

    if success:
        generate_thumbnail(out_f, thumb_f)
        await status.edit("📤 ቪዲዮው ወደ ቻናል እየተጫነ ነው: 0%")
        # ወደ ቻናል መጫን
        channel_msg = await client.send_file(CHANNEL_ID, out_f, thumb=thumb_f, caption="✨ 4K Ultra HQ Glow Edit", supports_streaming=True, progress_callback=lambda c, t: client.loop.create_task(progress_bar(c, t, status, "📤 በመጫን ላይ")))
        # ለተጠቃሚው ኮፒ መላክ (የቻናሉ ስም ሳይታይ)
        await client.send_message(event.chat_id, channel_msg)
        await status.delete()
    else:
        await status.edit("❌ ስህተት ተፈጥሯል። ምናልባት ቪዲዮው ከባድ ሊሆን ይችላል።")

    for f in [in_f, out_f, thumb_f]: 
        if os.path.exists(f): os.remove(f)

async def main():
    threading.Thread(target=run_render_server, daemon=True).start()
    await client.start(bot_token=BOT_TOKEN)
    print("🚀 ቦቱ ስራ ጀምሯል...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
