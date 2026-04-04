import os
import subprocess
import logging
import yt_dlp
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# Logging
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")

def process_video(input_path, output_path):
    """
    Railway RAM እንዳይሞላ በጣም የቀለለ ኤዲቲንግ።
    """
    # ቪዲዮውን ወደ 480p ዝቅ በማድረግ እና ፍጥነቱን በመጨመር RAM እንቆጥባለን
    video_filters = (
        "scale=-2:480," # ቁመቱን 480p ማድረግ
        "eq=saturation=1.4:contrast=1.1" # የቀለም ማሳመሪያ ብቻ
    )
    
    command = [
        'ffmpeg', '-y', 
        '-i', input_path,
        '-vf', video_filters,
        '-c:v', 'libx264', 
        '-preset', 'ultrafast', # በጣም ፈጣኑ (RAM አይበላም)
        '-crf', '32',           # ፋይሉን በጣም ያቀልለዋል
        '-c:a', 'copy',         # ድምፁን ሳይቀይር ኮፒ ማድረግ (CPU ይቆጥባል)
        output_path
    ]
    
    try:
        # ለስራው 45 ሰከንድ ብቻ እንስጠው
        result = subprocess.run(command, capture_output=True, text=True, timeout=45)
        if result.returncode == 0:
            return True
        logging.error(f"FFmpeg Error: {result.stderr}")
        return False
    except Exception as e:
        logging.error(f"Error: {e}")
        return False

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    
    if any(site in url for site in ["tiktok.com", "instagram.com", "youtube.com", "shorts"]):
        status_msg = await update.message.reply_text("🎬 ቪዲዮውን እያወረድኩ ነው...")
        
        chat_id = update.message.chat_id
        input_file = f"in_{chat_id}.mp4"
        output_file = f"out_{chat_id}.mp4"
        
        # ትክክለኛ የyt-dlp አወራረድ (ለማቅለል)
        ydl_opts = {
            'outtmpl': input_file,
            'format': 'best[ext=mp4]/best',
            'overwrites': True,
            'quiet': True
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            await status_msg.edit_text("✨ ኤዲት እያደረግኩ ነው (Vibrant Mode)...")
            
            # ኤዲቲንግ መጀመር
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, process_video, input_file, output_file)
            
            if success and os.path.exists(output_file):
                await status_msg.edit_text("🚀 ተጠናቀቀ! በመላክ ላይ...")
                with open(output_file, 'rb') as video:
                    await update.message.reply_video(video=video, caption="High Quality Edit 🔥")
            else:
                # ኤዲቲንግ ካልሰራ ኦሪጅናሉን ፋይል ይልካል
                await status_msg.edit_text("⚠️ RAM ስለሞላ ኤዲት ማድረግ አልተቻለም። ኦሪጅናሉን በመላክ ላይ...")
                with open(input_file, 'rb') as video:
                    await update.message.reply_video(video=video)
            
        except Exception as e:
            await update.message.reply_text(f"❌ ስህተት: {str(e)[:50]}")
        
        finally:
            if os.path.exists(input_file): os.remove(input_file)
            if os.path.exists(output_file): os.remove(output_file)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
