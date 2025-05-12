FROM python:3.11-slim

# Sistem bağımlılıkları (ffmpeg, git, vs.)
RUN apt-get update && \
    apt-get install -y ffmpeg git && \
    rm -rf /var/lib/apt/lists/*

# Çalışma dizini
WORKDIR /app

# Gereksiz dosyaları kopyalama
COPY requirements.txt ./

# Python bağımlılıklarını yükle
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama dosyalarını kopyala
COPY . .

# Port
EXPOSE 5000

# Başlatıcı komut
CMD ["python", "app.py"] 