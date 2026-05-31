FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y default-mysql-client p7zip-full && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY src/ ./src/

# Копируем пример конфига как дефолтный (на случай, если не примонтировали свой)
COPY config.example.yaml config.yaml

CMD ["python", "main.py"]
