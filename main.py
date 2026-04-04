import os
import subprocess
import logging
import yt_dlp
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# ለ Logs ክትትል እንዲመች
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Token-ን ከ Environment Variable ያነባል
TOKEN = os.getenv("BOT_TOKEN")

async def process_video(input_path, output_path):
    """
    ቪዲዮውን 4K Quality (Glow + Sharpness) የሚሰጠው የ FFmpeg ትዕዛዝ
    """
    prompt = (
        "scale=1080:-2:flags=lanczos,"  # ለ Railway ፍጥነት ሲባል 1080p ተመራጭ ነው
        "unsharp=5:5:1.5:5:5:0.0,"      # ጥራቱን በጣም ይጨምረዋል
        "eq=saturation=1.6:contrast=1.2:brightness=0.03" # ከለሩን ያፀባርቀዋል
    )
    
    command = [
        'ffmpeg', '-i', input_path,
        '-vf', prompt,
        '-c:v', 'libx264', '-crf', '18', '-preset', 'superfast', 
        '-c:a', 'copy', output_path
    ]
    
    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode != 0:
        raise Exception(f"FFmpeg Error: {process.stderr.decode()}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    
    # ሊንክ መሆኑን ማረጋገጥ
    if "tiktok.com" in url or "instagram.com" in url or "youtube.com" in url:
        status_msg = await update.message.reply_text("🎬 ቪዲዮውን እያወረድኩ ነው...")
        
        input_file = "input_video.mp4"
        output_file = "output_high_quality.mp4"
        
        ydl_opts = {
            'outtmpl': input_file,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'overwrites': True
        }
        
        try:
            # 1. ማውረድ
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            await status_msg.edit_text("✨ ጥራቱን በመጨመር ላይ ነኝ (Color Grading & Sharpening)...")
            
            # 2. ፕሮሰስ ማድረግ
            await process_video(input_file, output_file)
            
            # 3. መላክ
            await status_msg.edit_text("🚀 ጥራት ያለው ቪዲዮ ዝግጁ ነው! በመላክ ላይ...")
            with open(output_file, 'rb') as video:
                await update.message.reply_video(video=video, caption="Produced by Your 4K Bot 🔥")
            
            await status_msg.delete()
            
        except Exception as e:
            logging.error(f"Error: {e}")
            await update.message.reply_text(f"❌ ስህተት ተከስቷል፦ {str(e)[:100]}")
        
        finally:
            # ፋይሎችን ማጽዳት (Railway Storage እንዳይሞላ)
            if os.path.exists(input_file): os.remove(input_file)
            if os.path.exists(output_file): os.remove(output_file)
    else:
        await update.message.reply_text("እባክህ የቲክቶክ ወይም የኢንስታግራም ሊንክ ላክልኝ።")

if __name__ == '__main__':
    if not TOKEN:
        print("Error: BOT_TOKEN variable አልተገኘም!")
    else:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        print("ቦቱ ስራ ጀምሯል...")
        app.run_polling()
