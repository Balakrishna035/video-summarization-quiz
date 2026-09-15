FROM python:3.11-slim

# Install FFmpeg and Deno (required by yt-dlp for YouTube JS challenges)
RUN apt-get update && apt-get install -y ffmpeg curl unzip && \
    curl -fsSL https://deno.land/install.sh | sh && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

ENV DENO_INSTALL="/root/.deno"
ENV PATH="$DENO_INSTALL/bin:$PATH"

# Verify Deno is actually installed and on PATH
RUN deno --version

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 10000

CMD ["gunicorn", "--bind", "0.0.0.0:10000", "app:app"]
