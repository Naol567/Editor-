import os
import asyncio
import subprocess
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()

# Render Environment Variables
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN")
SESSION_STRING = os.getenv("SESSION_STRING", "") # ያወጣኸው ረጅሙ ቁልፍ
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))

# በ StringSession አማካኝነት በቀጥታ ይገባል
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

def process_video_4k(input_path, output_path):
    # 4K Glow Filter
    filters = (
        "scale=3840:2160:flags=lanczos,unsharp=5:5:1.5:5:5:0.0,"
        "split[main][blur];[blur]boxblur=20:5[glow];"
        "[main][glow]blend=all_mode='screen':all_opacity=0.35,"
        "eq=saturation=1.9:contrast=1.4:brightness=-0.02"
    )
    cmd = ['ffmpeg', '-y', '-i', input_path, '-vf', filters, 
           '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18', 
           '-c:a', 'copy', output_path]
    return subprocess.run(cmd, check=True).returncode == 0

@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.respond("✅ ቦቱ ዝግጁ ነው! አሁን ቪዲዮ መላክ ትችላለህ።")

@client.on(events.NewMessage(func=lambda e: e.video))
async def handle_video(event):
    if event.sender_id != ADMIN_ID: return

    status = await event.respond("📥 ቪዲዮው እየወረደ ነው...")
    in_f, out_f = "in.mp4", "out_4k.mp4"

    await client.download_media(event.video, in_f)
    await status.edit("🎬 4K Glow Edit እየተደረገ ነው...")
    
    if await asyncio.to_thread(process_video_4k, in_f, out_f):
        await status.edit("📤 ወደ ቻናል እየተጫነ ነው...")
        # በሰው አካውንት ስለሚጭን ትልቅ MB ይቻላል
        channel_msg = await client.send_file(CHANNEL_ID, out_f, caption="✨ 4K Glow Edit", supports_streaming=True)
        await client.send_message(event.chat_id, channel_msg)
        await status.delete()
    else:
        await status.edit("❌ ስህተት ተፈጥሯል።")

    for f in [in_f, out_f]:
        if os.path.exists(f): os.remove(f)

async def main():
    # ቦቱንም ስልኩንም በአንድ ላይ ያስጀምራል
    await client.start(bot_token=BOT_TOKEN)
    print("🚀 ቦቱ በትክክል ተነስቷል!")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
