import os
import subprocess
import logging
import yt_dlp
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# FFmpeg-ን በራሱ እንዲጭን የሚያደርግ ላይብረሪ
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except ImportError:
    pass

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")

def process_video(input_path, output_path):
    # በጣም የቀለለ ኤዲቲንግ (RAM ለመቆጠብ)
    # ቪዲዮውን ወደ 360p ዝቅ እናደርገዋለን (ለሙከራ)
    video_filters = "scale=-2:360,eq=saturation=1.4:contrast=1.1"
    
    command = [
        'ffmpeg', '-y', 
        '-i', input_path,
        '-vf', video_filters,
        '-c:v', 'libx264', 
        '-preset', 'ultrafast', 
        '-crf', '35', 
        '-c:a', 'copy',
        output_path
    ]
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True
        logging.error(f"FFmpeg Error: {result.stderr}")
        return False
    except Exception as e:
        logging.error(f"Error: {e}")
        return False

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if any(site in url for site in ["tiktok.com", "instagram.com", "youtube.com"]):
        status_msg = await update.message.reply_text("🎬 ቪዲዮውን በማዘጋጀት ላይ ነኝ...")
        
        chat_id = update.message.chat_id
        input_file = f"in_{chat_id}.mp4"
        output_file = f"out_{chat_id}.mp4"
        
        ydl_opts = {'outtmpl': input_file, 'format': 'mp4', 'overwrites': True, 'quiet': True}
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            await status_msg.edit_text("✨ ጥራቱን ለመጨመር እየሞከርኩ ነው...")
            
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, process_video, input_file, output_file)
            
            if success and os.path.exists(output_file):
                await status_msg.edit_text("✅ ኤዲቲንግ ተሳክቷል! በመላክ ላይ...")
                with open(output_file, 'rb') as video:
                    await update.message.reply_video(video=video)
            else:
                await status_msg.edit_text("⚠️ RAM እጥረት ስላለ ኤዲት ማድረግ አልተቻለም። ኦሪጅናሉን ፋይል በመላክ ላይ...")
                with open(input_file, 'rb') as video:
                    await update.message.reply_video(video=video)
            
        except Exception as e:
            await update.message.reply_text(f"❌ ስህተት: {e}")
        finally:
            if os.path.exists(input_file): os.remove(input_file)
            if os.path.exists(output_file): os.remove(output_file)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
