import os
import subprocess
import logging
import yt_dlp
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# FFmpeg-ን በራሱ እንዲጭን (Path ችግር እንዳይመጣ)
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except ImportError:
    pass

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")

def process_video(input_path, output_path):
    """
    ቪዲዮውን 720p HD የሚያደርግ እና ቀለሙን የሚያፀባርቅ (High Glow)።
    """
    # ጥራቱን የሚጨምሩ ማጣሪያዎች (Filters)
    video_filters = (
        "scale='if(gt(iw,ih),1280,-2)':'if(gt(iw,ih),-2,720)'," # 720p HD Scale
        "unsharp=5:5:1.5:5:5:0.0,"    # Sharpness (ጥራቱን ያጎላል)
        "eq=saturation=1.7:contrast=1.3:brightness=0.04" # Glow እና Vibrant Colors
    )
    
    command = [
        'ffmpeg', '-y', 
        '-i', input_path,
        '-vf', video_filters,
        '-c:v', 'libx264', 
        '-pix_fmt', 'yuv420p',
        '-preset', 'ultrafast',   # ለፍጥነት (Railway RAM እንዳይሞላ)
        '-crf', '20',             # ጥራት (ከ 18-22 መካከል ምርጥ ነው)
        '-c:a', 'copy',           # ድምፁን ሳይነካ ኮፒ ያደርጋል
        output_path
    ]
    
    try:
        # ለኤዲቲንግ 120 ሰከንድ እንስጠው
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            return True
        logging.error(f"FFmpeg Error: {result.stderr}")
        return False
    except Exception as e:
        logging.error(f"Error: {e}")
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
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'overwrites': True,
            'quiet': True
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            await status_msg.edit_text("✨ ጥራቱን በመጨመር ላይ ነኝ (High Quality Edit)... 🚀")
            
            # ኤዲቲንግ መጀመር
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, process_video, input_file, output_file)
            
            if success and os.path.exists(output_file):
                await status_msg.edit_text("✅ ተጠናቀቀ! በመላክ ላይ...")
                with open(output_file, 'rb') as video:
                    await update.message.reply_video(video=video, caption="High Quality Edit By Your Bot 🔥")
            else:
                await status_msg.edit_text("⚠️ RAM እጥረት ስላለ ኤዲት ማድረግ አልተቻለም። ኦሪጅናሉን በመላክ ላይ...")
                with open(input_file, 'rb') as video:
                    await update.message.reply_video(video=video, caption="Original Video (Edit Failed)")
            
        except Exception as e:
            await update.message.reply_text(f"❌ ስህተት: {str(e)[:100]}")
        
        finally:
            if os.path.exists(input_file): os.remove(input_file)
            if os.path.exists(output_file): os.remove(output_file)

if __name__ == '__main__':
    if not TOKEN:
        print("BOT_TOKEN አልተገኘም!")
    else:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        print("ቦቱ ስራ ጀምሯል...")
        app.run_polling()
