import os
import asyncio
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from dotenv import load_dotenv

# --- የቦቱ መነሻ ምልክት (Logs ላይ ለማየት) ---
print("---------------------------------")
print("🔥 ቦቱ አሁን መነሳት ጀምሯል...")
print("---------------------------------")

load_dotenv()

# --- Configuration (Render Environment Variables) ---
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN")
SESSION_STRING = os.getenv("SESSION_STRING", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))

# በ StringSession አማካኝነት በቀጥታ ይገባል
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# --- Render Port Fix (Health Check Server) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Running Perfectly")

def run_health_server():
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    print(f"📡 Health check server started on port {port}")
    server.serve_forever()

# --- Progress Bar Helper ---
async def progress_bar(current, total, event, msg_prefix):
    percentage = current * 100 / total
    if not hasattr(progress_bar, "last_edit"): progress_bar.last_edit = 0
    if time.time() - progress_bar.last_edit > 5 or percentage == 100:
        try:
            await event.edit(f"{msg_prefix}: {percentage:.1f}% ...")
            progress_bar.last_edit = time.time()
        except: pass

# --- Video Processing (4K Glow HQ) ---
def process_video_4k(input_path, output_path):
    # ከፍተኛ ጥራት ያለው 4K Glow ማጣሪያ
    filters = (
        "scale=3840:2160:flags=lanczos,unsharp=5:5:1.5:5:5:0.0,"
        "split[main][blur];[blur]boxblur=20:5[glow];"
        "[main][glow]blend=all_mode='screen':all_opacity=0.35,"
        "eq=saturation=1.9:contrast=1.4:brightness=-0.02"
    )
    cmd = [
        'ffmpeg', '-y', '-i', input_path, 
        '-vf', filters, 
        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18', 
        '-c:a', 'copy', output_path
    ]
    try:
        subprocess.run(cmd, check=True)
        return True
    except Exception as e:
        print(f"FFmpeg Error: {e}")
        return False

# --- Handlers ---

@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    # ADMIN_ID በትክክል መግባቱን ለማረጋገጥ
    print(f"📩 የገባው መልእክት ከ ID: {event.sender_id}")
    if event.sender_id == ADMIN_ID:
        await event.respond("✅ ሰላም ጌታዬ! ቦቱ ዝግጁ ነው። ቪዲዮ ላክልኝ።")
    else:
        await event.respond(f"⚠️ ይቅርታ፣ ይህ ቦት ለባለቤቱ ብቻ ነው። ያንተ ID: {event.sender_id}")

@client.on(events.NewMessage(func=lambda e: e.video))
async def handle_video(event):
    if event.sender_id != ADMIN_ID: return

    status = await event.respond("📥 ቪዲዮው እየወረደ ነው...")
    in_f, out_f = "input_video.mp4", "output_4k_glow.mp4"

    try:
        await client.download_media(
            event.video, in_f, 
            progress_callback=lambda c, t: client.loop.create_task(progress_bar(c, t, status, "📥 በማውረድ ላይ"))
        )

        await status.edit("🎬 4K Glow Edit እየተደረገ ነው... (ጥቂት ደቂቃ ይጠብቁ)")
        
        success = await asyncio.to_thread(process_video_4k, in_f, out_f)

        if success:
            await status.edit("📤 ወደ ቻናል እየተጫነ ነው...")
            channel_msg = await client.send_file(
                CHANNEL_ID, out_f, 
                caption="✨ 4K Ultra HQ Glow Edit", 
                supports_streaming=True,
                progress_callback=lambda c, t: client.loop.create_task(progress_bar(c, t, status, "📤 በመጫን ላይ"))
            )
            await client.send_message(event.chat_id, "✅ ተጠናቋል! ቪዲዮው ወደ ቻናል ተልኳል።")
            await status.delete()
        else:
            await status.edit("❌ ስህተት ተፈጥሯል። FFmpeg መኖሩን አረጋግጥ።")

    except Exception as e:
        await event.respond(f"❌ ስህተት ተፈጠረ: {e}")

    for f in [in_f, out_f]:
        if os.path.exists(f): os.remove(f)

# --- Main Run ---
async def start_bot():
    # Health Server (Render Port Fix)
    threading.Thread(target=run_health_server, daemon=True).start()
    
    # ቦቱን ያስጀምራል
    await client.start(bot_token=BOT_TOKEN)
    print("🚀 ቦቱ በትክክል ተነስቷል!")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(start_bot())
