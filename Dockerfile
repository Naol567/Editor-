FROM python:3.10-slim

RUN apt-get update && apt-get install -y ffmpeg libsm6 libxext6 build-essential && apt-get clean

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "main.py"]
