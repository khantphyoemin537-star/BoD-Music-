FROM python:3.10-slim

# Linux System ထဲမှာ VC အတွက် မရှိမဖြစ်လိုအပ်တဲ့ ffmpeg နဲ့ git ကို သွင်းတာပါ
RUN apt-get update && apt-get install -y ffmpeg git curl && apt-get clean

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]
