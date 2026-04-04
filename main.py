import os
import subprocess
import logging
import yt_dlp
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# Logging setup - ስህተቶችን በRailway Logs ላይ ለማየት
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")

def process_video(input_path, output_path):
    """
    ቪዲዮውን 720p HD የሚያደርግ እና ከለሩን የሚያፀባርቅ (Glow) ትዕዛዝ።
    'ultrafast' መጠቀም Railway እንዳይዘጋው ያደርጋል።
    """
    # ቪዲዮው ለቴሌግራም እና ለRailway እንዲመች የተደረገ ማጣሪያ
    video_filters = (
        "scale='if(gt(iw,ih),1280,-2)':'if(gt(iw,ih),-2,720)'," # 720p HD Scale
        "unsharp=3:3:1.2:3:3:0.0,"    # ጥራቱን ማጉያ
        "eq=saturation=1.6:contrast=1.2:brightness=0.03" # ከለር ማሳመሪያ
    )
    
    command = [
        'ffmpeg', '-y', 
        '-i', input_path,
        '-vf', video_filters,
        '-c:v', 'libx264', 
        '-pix_fmt', 'yuv420p',    # ለሁሉም ስልኮች እንዲከፍት
        '-preset', 'ultrafast',   # ለRailway ፍጥነት
        '-crf', '24',             # የፋይል መጠኑን ለመቀነስ
        '-c:a', 'aac',            # ድምፁ እንዳይጠፋ
        '-shortest',
        output_path
    ]
    
    try:
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            logging.error(f"FFmpeg Error: {result.stderr}")
            return False
        return True
    except Exception as e:
        logging.error(f"Execution Error: {e}")
        return False

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    
    # ተቀባይነት ያላቸው ሊንኮች
    if any(site in url for site in ["tiktok.com", "instagram.com", "youtube.com", "shorts", "reels"]):
        status_msg = await update.message.reply_text("🎬 ቪዲዮውን በማውረድ ላይ ነኝ... ⏳")
        
        chat_id = update.message.chat_id
        input_file = f"in_{chat_id}.mp4"
        output_file = f"out_{chat_id}.mp4"
        
        ydl_opts = {
            'outtmpl': input_file,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'overwrites': True,
            'quiet': True
        }
        
        try:
            # 1. ቪዲዮውን ማውረድ
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            await status_msg.edit_text("✨ ጥራቱን በመጨመር ላይ ነኝ (HD Edit)... 🚀")
            
            # 2. ጥራቱን መጨመር (FFmpeg)
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, process_video, input_file, output_file)
            
            if success and os.path.exists(output_file):
                await status_msg.edit_text("✅ ተጠናቀቀ! በመላክ ላይ...")
                with open(output_file, 'rb') as video:
                    await update.message.reply_video(video=video, caption="High Quality Edit By Your Bot 🔥")
            else:
                await status_msg.edit_text("❌ ይቅርታ፣ ቪዲዮውን ኤዲት ማድረግ አልተቻለም። ኦሪጅናሉን ፋይል በመላክ ላይ...")
                with open(input_file, 'rb') as video:
                    await update.message.reply_video(video=video, caption="Original Video (Edit Failed)")
            
        except Exception as e:
            logging.error(f"Error: {e}")
            await update.message.reply_text(f"❌ ስህተት ተከስቷል፦ {str(e)[:100]}")
        
        finally:
            # ፋይሎችን ማጥፋት (Storage እንዳይሞላ)
            if os.path.exists(input_file): os.remove(input_file)
            if os.path.exists(output_file): os.remove(output_file)
    else:
        await update.message.reply_text("እባክህ የቲክቶክ ወይም የኢንስታግራም ሊንክ ላክልኝ።")

if __name__ == '__main__':
    if not TOKEN:
        print("BOT_TOKEN አልተገኘም! Railway Variables ላይ ጨምር።")
    else:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        print("ቦቱ ስራ ጀምሯል...")
        app.run_polling()
