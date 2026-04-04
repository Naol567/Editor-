import os
import subprocess
import logging
import yt_dlp
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# Logging setup
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# Token from Environment Variable
TOKEN = os.getenv("BOT_TOKEN")

def process_video(input_path, output_path):
    """
    ቪዲዮውን ጥራት የሚጨምር እና የሚያፀባርቅ (Glow) የሚያደርግ።
    Railway እንዳይዘጋው 'ultrafast' እና '720p' ተመራጭ ናቸው።
    """
    # High Quality & Glow Filter
    video_filters = (
        "scale=720:-2:flags=lanczos," # ጥራቱን ሳይቀንስ መጠኑን ያስተካክላል
        "unsharp=3:3:1.5:3:3:0.0,"    # Sharpness ይጨምራል
        "eq=saturation=1.6:contrast=1.2:brightness=0.03" # ከለሩን ያፀባርቃል
    )
    
    command = [
        'ffmpeg', '-y', '-i', input_path,
        '-vf', video_filters,
        '-c:v', 'libx264', 
        '-preset', 'ultrafast', # ለ Railway ፍጥነት በጣም ወሳኝ ነው
        '-crf', '20', 
        '-c:a', 'copy', 
        output_path
    ]
    
    try:
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            logging.error(f"FFmpeg Error Output: {result.stderr}")
            return False
        return True
    except Exception as e:
        logging.error(f"FFmpeg Execution Error: {e}")
        return False

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    
    # ሊንክ መሆኑን ማረጋገጥ
    valid_sites = ["tiktok.com", "instagram.com", "youtube.com", "shorts", "reels"]
    if any(site in url for site in valid_sites):
        status_msg = await update.message.reply_text("🎬 ቪዲዮውን እያወረድኩ ነው... ⏳")
        
        # ለእያንዳንዱ ተጠቃሚ የተለያየ ፋይል ስም (ግጭት እንዳይፈጠር)
        chat_id = update.message.chat_id
        input_file = f"in_{chat_id}.mp4"
        output_file = f"out_{chat_id}.mp4"
        
        ydl_opts = {
            'outtmpl': input_file,
            'format': 'best[ext=mp4]/best',
            'overwrites': True,
            'quiet': True,
            'no_warnings': True
        }
        
        try:
            # 1. ማውረድ
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            await status_msg.edit_text("✨ ጥራቱን በመጨመር ላይ ነኝ (Color Edit)... 🚀")
            
            # 2. ማቀነባበር (FFmpeg)
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, process_video, input_file, output_file)
            
            if success and os.path.exists(output_file):
                await status_msg.edit_text("✅ ተጠናቀቀ! በመላክ ላይ...")
                with open(output_file, 'rb') as video:
                    await update.message.reply_video(video=video, caption="High Quality Edit By Your Bot 🔥")
            else:
                await update.message.reply_text("❌ ይቅርታ ቪዲዮውን ማቀነባበር አልተቻለም። (FFmpeg Error)")
            
        except Exception as e:
            logging.error(f"General Error: {e}")
            await update.message.reply_text(f"❌ ስህተት ተከስቷል፦ {str(e)[:50]}")
        
        finally:
            # ፋይሎችን ማጽዳት (Railway Storage እንዳይሞላ)
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
