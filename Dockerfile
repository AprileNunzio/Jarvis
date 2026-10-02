FROM python:3.11-slim

# Imposta la cartella di lavoro
WORKDIR /app

# Installa dipendenze di sistema utili
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copia i file dei requisiti e installa le librerie Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia tutto il codice sorgente
COPY . .

# Esponi le porte necessarie
# 80 per il widget frontend ologramma
# 8080 per il pannello di controllo admin
EXPOSE 80 8080

# Comando di avvio del server
CMD ["python", "server/cmd/main.py"]
