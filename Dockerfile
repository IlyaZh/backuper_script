FROM python:3.11-slim

# Устанавливаем клиент MySQL (для mysqldump)
RUN apt-get update && \
    apt-get install -y default-mysql-client && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY config.py backup.py notifier.py ./

# Копируем пример конфига как дефолтный (на случай, если не примонтировали свой)
COPY config.example.yaml config.yaml

CMD ["python", "backup.py"]