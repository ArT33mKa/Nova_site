# Dockerfile

# 1. Використовуємо офіційний, легкий образ Python
FROM python:3.11-slim

# 2. Встановлюємо робочу директорію всередині контейнера
WORKDIR /app

# 3. Встановлюємо змінні середовища для кращої роботи Python в Docker
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 4. Встановлюємо системні залежності, якщо вони потрібні
# (може знадобитись для деяких бібліотек, але почнемо без них)
# RUN apt-get update && apt-get install -y build-essential

# 5. Копіюємо файл залежностей і встановлюємо їх
# Це робиться окремо для кешування. Якщо requirements.txt не змінився,
# цей крок не буде виконуватися знову, що прискорює деплой.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Копіюємо решту файлів нашого додатку в контейнер
COPY . .

# 7. Вказуємо команду для запуску нашого сайту через Gunicorn
# Fly.io очікує, що додаток буде працювати на порті 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "app:app"]