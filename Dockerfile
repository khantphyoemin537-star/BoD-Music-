FROM python:3.10-slim-bullseye

# တကယ့် Linux စနစ်ထဲသို့ လိုအပ်သော Build Tools များနှင့် ffmpeg သွင်းခြင်း
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    gcc \
    g++ \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# No-cache ဖြင့် သန့်သန့်ရှင်းရှင်း သွင်းမည်
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
