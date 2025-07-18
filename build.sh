#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Запускаємо наш скрипт для створення/оновлення БД та імпорту товарів
python init_db.py