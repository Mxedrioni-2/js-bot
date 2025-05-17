FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY . .


RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY .env .
ENV $(cat .env | grep -v '^#' | xargs)

RUN pip install --no-cache-dir -r requirements.txt


CMD ["python", "-u", "main.py"]