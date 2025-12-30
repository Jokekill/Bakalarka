# r-chess-prototype/Dockerfile
FROM python:3.11-slim-bookworm

# Instalace Stockfishe (engine) do systému kontejneru
RUN apt-get update && apt-get install -y \
    stockfish \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalace python knihoven
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopírování aplikace
COPY main.py .

# Port pro NiceGUI
EXPOSE 8080

CMD ["python", "main.py"]