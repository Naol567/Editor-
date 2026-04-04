import os
import subprocess
import logging
import yt_dlp
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# Logging setup
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")

def process_video(input_path, output_path):
    """
    ቪዲዮውን 480p በማድረግ የሰርቨሩን ጫና መቀነስ።
    ቀለሙን እና ጥራቱን ግን ማሳመር።
    """
    # Railway እንዳይዘጋው መጠኑን እና ፍጥነቱን አስተካክለናል
    video_filters = (
        "scale='if(gt(iw,ih),854,-2)':'if(gt(iw,ih),-2,480)'," # 480p Scale
        "unsharp=3:3:0.8:3:3:0.0,"    # Sharpness
        "eq=saturation=1.5:contrast=1.2:brightness=0.03" # Color Glow
    )
    
    command = [
        'ffmpeg', '-y', 
        '-i', input_path,
        '-vf', video_filters,
        '-c:v', 'libx264', 
        '-pix_fmt', 'yuv420p',
        '-preset', 'ultrafast',   # በጣም ፈጣኑ መንገድ
        '-crf', '28',             # ፋይሉን ያቀልለዋል
        '-c:a', 'aac', 
        '-map', '0:v:0', '-map', '0:a:0', # የመጀመሪያውን ቪዲዮ እና ኦዲዮ ብቻ መውሰድ
        output_path
    ]
    
    try:
        # ለ FFmpeg 90 ሰከንድ እንስጠው
        result = subprocess.run(command, capture_output=True, text=True, timeout=90)
        if result.returncode != 0:
            logging.error(f"FFmpeg Error: {result.stderr}")
            return False
        return True
    except Exception as e:
        logging.error(f"Execution Error: {e}")
        return False

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    
    if any(site in url for site in ["tiktok.com", "instagram.com", "youtube.com", "shorts", "reels"]):
        status_msg = await update.message.reply_text("🎬 ቪዲዮውን እያወረድኩ ነው... ⏳")
        
        chat_id = update.message.chat_id
        input_file = f"in_{chat_id}.mp4"
        output_file = f"out_{chat_id}.mp4"
        
        ydl_opts = {
            'outtmpl': input_file,
            'format': 'mp4', # ቀጥታ mp4 እንዲያወርድ (RAM ለመቆጠብ)
            'overwrites': True,
            'quiet': True
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            await status_msg.edit_text("✨ ጥራቱን በመጨመር ላይ ነኝ (Edit Mode)... 🚀")
            
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, process_video, input_file, output_file)
            
            if success and os.path.exists(output_file):
                await status_msg.edit_text("✅ ተጠናቀቀ! በመላክ ላይ...")
                with open(output_file, 'rb') as video:
                    await update.message.reply_video(video=video, caption="High Quality Edit 🔥")
            else:
                # ኤዲቲንግ ካልሰራ ኦሪጅናሉን ይልካል
                await status_msg.edit_text("⚠️ ኤዲቲንግ አልተሳካም (RAM እጥረት)። ኦሪጅናሉን በመላክ ላይ...")
                with open(input_file, 'rb') as video:
                    await update.message.reply_video(video=video, caption="Original Video")
            
        except Exception as e:
            logging.error(f"Error: {e}")
            await update.message.reply_text(f"❌ ስህተት ተከስቷል፦ {str(e)[:50]}")
        
        finally:
            if os.path.exists(input_file): os.remove(input_file)
            if os.path.exists(output_file): os.remove(output_file)
    else:
        await update.message.reply_text("እባክህ የቲክቶክ ወይም የኢንስታግራም ሊንክ ላክልኝ።")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("ቦቱ ስራ ጀምሯል...")
    app.run_polling()
