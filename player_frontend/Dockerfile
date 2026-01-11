# player_frontend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Instalace systémových závislostí (pokud by byly potřeba pro kompilaci)
# RUN apt-get update && apt-get install -y gcc

# Kopírování a instalace Python závislostí
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopírování aplikačního kódu
COPY . .

# Expozice portu 8080 (interní port NiceGUI)
EXPOSE 8080

# Spuštění aplikaces
CMD ["python", "main.py"]