import os
import asyncio
import subprocess
import threading
import cv2
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from telethon import TelegramClient, events
from dotenv import load_dotenv

load_dotenv()

# Environment Variables
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))

client = TelegramClient('session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# --- Render Health Check ---
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"4K Pro Bot with Animation is Active")

def run_render_server():
    port = int(os.environ.get("PORT", 8000))
    httpd = HTTPServer(('0.0.0.0', port), HealthHandler)
    httpd.serve_forever()

# --- Live Progress & Animation ---
async def progress_bar(current, total, event, msg_prefix):
    percentage = current * 100 / total
    if not hasattr(progress_bar, "last_edit"): progress_bar.last_edit = 0
    if time.time() - progress_bar.last_edit > 5 or percentage == 100:
        text = f"{msg_prefix}: {percentage:.1f}% ..."
        try:
            await event.edit(text)
            progress_bar.last_edit = time.time()
        except: pass

async def processing_animation(event, stop_event):
    frames = ["🎬 ቪዲዮው እየተቀነባበረ ነው .", "🎬 ቪዲዮው እየተቀነባበረ ነው ..", "🎬 ቪዲዮው እየተቀነባበረ ነው ..."]
    i = 0
    while not stop_event.is_set():
        try:
            await event.edit(frames[i % 3])
            await asyncio.sleep(1.5)
            i += 1
        except: break

# --- Video Processing Functions ---
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

# --- Bot Events ---
@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.respond("ሰላም! ቪዲዮ ላክልኝና በ 4K Ultra HQ Glow አቀነባብሬ እልክልሃለሁ።")

@client.on(events.NewMessage)
async def handle_video(event):
    if event.sender_id != ADMIN_ID or not event.video:
        return

    status = await event.respond("📥 በማውረድ ላይ: 0%")
    input_file, output_file, thumb_file = "in.mp4", "out_4k.mp4", "thumb.jpg"

    # 1. Download with Progress
    await client.download_media(
        event.video, input_file,
        progress_callback=lambda c, t: client.loop.create_task(progress_bar(c, t, status, "📥 በማውረድ ላይ"))
    )

    # 2. Processing with Animation
    stop_anim = asyncio.Event()
    anim_task = client.loop.create_task(processing_animation(status, stop_anim))
    
    # FFmpeg ስራውን እስኪጨርስ በሌላ thread ማስኬድ
    success = await asyncio.to_thread(process_video_4k, input_file, output_file)
    
    stop_anim.set()
    await anim_task

    if success:
        generate_thumbnail(output_file, thumb_file)
        await status.edit("📤 በመጫን ላይ: 0%")
        
        # 3. Upload to Channel
        channel_msg = await client.send_file(
            CHANNEL_ID, output_file, thumb=thumb_file,
            caption="✨ 4K Ultra HQ Glow Edit",
            supports_streaming=True,
            progress_callback=lambda c, t: client.loop.create_task(progress_bar(c, t, status, "📤 በመጫን ላይ"))
        )

        # 4. Copy to User (No Channel Name)
        await client.send_message(event.chat_id, channel_msg)
        await status.delete()
    else:
        await status.edit("❌ ስህተት ተፈጥሯል። Render RAM መጠኑ አናሳ ሊሆን ይችላል።")

    for f in [input_file, output_file, thumb_file]:
        if os.path.exists(f): os.remove(f)

async def main():
    threading.Thread(target=run_render_server, daemon=True).start()
    print("🚀 ቦቱ በሙሉ አቅሙ ስራ ጀምሯል...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
