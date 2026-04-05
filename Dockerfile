FROM python:3.10-slim

# FFmpeg እና አስፈላጊ የሆኑ ነገሮችን መጫን
RUN apt-get update && apt-get install -y ffmpeg build-essential python3-dev && apt-get clean

WORKDIR /app

# Requirements መጫን
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# ፖርት መክፈት
EXPOSE 8000

# የ gunicorn ስህተትን ለማስቀረት ቀጥታ የፓይዘን ፋይሉን ማስጀመር
CMD ["python", "main.py"]
