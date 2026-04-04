import os
import subprocess
import logging
import yt_dlp
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Token from Environment Variable
TOKEN = os.getenv("BOT_TOKEN")

def process_video(input_path, output_path):
    """
    ቪዲዮውን ጥራት የሚጨምር እና ከለር Grading የሚሰራ FFmpeg ትዕዛዝ
    Railway RAM እንዳይጨርስ 'ultrafast' እና '720p' ተመራጭ ነው
    """
    # High Quality & Glow Filter
    filters = (
        "scale=720:-2:flags=lanczos,"
        "unsharp=3:3:1.0:3:3:0.0,"
        "eq=saturation=1.5:contrast=1.1:brightness=0.02"
    )
    
    command = [
        'ffmpeg', '-y', '-i', input_path,
        '-vf', filters,
        '-c:v', 'libx264', 
        '-preset', 'ultrafast', # ለፍጥነት
        '-crf', '20',           # ለጥራት (ዝቅተኛ ቁጥር = ከፍተኛ ጥራት)
        '-c:a', 'copy', 
        output_path
    ]
    
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        logging.error(f"FFmpeg Error: {result.stderr}")
        return False
    return True

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    
    if any(site in url for site in ["tiktok.com", "instagram.com", "youtube.com", "shorts"]):
        status_msg = await update.message.reply_text("🎬 ቪዲዮውን እያወረድኩ ነው... ⏳")
        
        input_file = f"in_{update.message.chat_id}.mp4"
        output_file = f"out_{update.message.chat_id}.mp4"
        
        ydl_opts = {
            'outtmpl': input_file,
            'format': 'best[ext=mp4]/best',
            'overwrites': True,
            'quiet': True
        }
        
        try:
            # 1. Download
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            await status_msg.edit_text("✨ ጥራቱን በመጨመር ላይ ነኝ (4K Edit)... 🚀")
            
            # 2. Process (FFmpeg)
            # አድካሚ ስራ ስለሆነ በ thread እናስኪደው
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, process_video, input_file, output_file)
            
            if success and os.path.exists(output_file):
                await status_msg.edit_text("✅ ተጠናቀቀ! በመላክ ላይ...")
                with open(output_file, 'rb') as video:
                    await update.message.reply_video(video=video, caption="High Quality Edit By Your Bot 🔥")
            else:
                await update.message.reply_text("❌ ይቅርታ ቪዲዮውን ማቀነባበር አልተቻለም።")
            
        except Exception as e:
            logging.error(f"Error: {e}")
            await update.message.reply_text(f"❌ ስህተት ተከስቷል፦ {str(e)[:50]}")
        
        finally:
            # Cleanup
            await status_msg.delete()
            if os.path.exists(input_file): os.remove(input_file)
            if os.path.exists(output_file): os.remove(output_file)
    else:
        await update.message.reply_text("እባክህ የቲክቶክ ወይም የኢንስታግራም ሊንክ ላክልኝ።")

if __name__ == '__main__':
    if not TOKEN:
        print("BOT_TOKEN አልተገኘም! እባክህ Railway Variables ላይ ጨምር።")
    else:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        print("ቦቱ ስራ ጀምሯል... ሊንክ መላክ ትችላለህ")
        app.run_polling()
