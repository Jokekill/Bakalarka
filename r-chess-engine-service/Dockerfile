# 1. Použijeme lehký Python image
FROM python:3.11-slim

# 2. Instalace základních nástrojů
RUN apt-get update && apt-get install -y \
    wget \
    tar \
    make \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 3. Stažení a instalace Stockfishe
WORKDIR /tmp

# Změna: Použijeme verzi 17 a opravíme cestu při přesouvání (mv)
RUN wget https://github.com/official-stockfish/Stockfish/releases/download/sf_17/stockfish-ubuntu-x86-64-avx2.tar -O stockfish.tar \
    && tar -xvf stockfish.tar \
    && mv stockfish/stockfish-ubuntu-x86-64-avx2 /usr/local/bin/stockfish \
    && chmod +x /usr/local/bin/stockfish

# Poznámka: Pokud by tvůj počítač neuměl instrukce AVX2 (velmi staré CPU), 
# změň v odkazu výše "avx2" na "modern" nebo "bmi2".

# 4. Nastavení pracovní složky aplikace
WORKDIR /app

# 5. Kopírování requirements a instalace Python knihoven
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Kopírování zdrojového kódu
COPY main.py .

# 7. Otevření portu 8000
EXPOSE 8000

# 8. Spuštění serveru
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]