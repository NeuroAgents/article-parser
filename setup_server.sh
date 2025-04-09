#!/bin/bash

# Скрипт для настройки парсера статей на сервере
# Запустите его на сервере командой: bash setup_server.sh

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Начинаю настройку парсера статей...${NC}"

# Обновление системы
echo "Обновление системы..."
apt update && apt upgrade -y

# Установка необходимых пакетов
echo "Установка Python и зависимостей..."
apt install -y python3 python3-pip python3-venv git

# Создание рабочего каталога
echo "Создание рабочего каталога..."
mkdir -p /opt/article_parser
cd /opt/article_parser

# Создание виртуального окружения
echo "Настройка Python-окружения..."
python3 -m venv venv
source venv/bin/activate

# Создание файла requirements.txt
echo "Создание файлов проекта..."
cat > requirements.txt << 'EOF'
requests==2.31.0
feedparser==6.0.10
python-dotenv==1.0.0
schedule==1.2.1
supabase==2.3.0
python-dateutil==2.8.2
beautifulsoup4==4.12.2
EOF

# Установка зависимостей
echo "Установка Python-зависимостей..."
pip install -r requirements.txt

# Создание .env файла-примера
cat > .env.example << 'EOF'
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
EOF

# Создание файла службы systemd для запуска в фоне
echo "Создание службы systemd..."
cat > /etc/systemd/system/article-parser.service << 'EOF'
[Unit]
Description=Article Parser Service
After=network.target

[Service]
User=root
WorkingDirectory=/opt/article_parser
ExecStart=/opt/article_parser/venv/bin/python3 /opt/article_parser/article_parser.py
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=article-parser

[Install]
WantedBy=multi-user.target
EOF

# Перезагрузка systemd
systemctl daemon-reload

# Настройка логирования syslog
echo "Настройка логирования..."
cat > /etc/rsyslog.d/article-parser.conf << 'EOF'
if $programname == 'article-parser' then /var/log/article-parser.log
& stop
EOF

# Перезапуск rsyslog
systemctl restart rsyslog

# Создание файла логов и настройка прав
touch /var/log/article-parser.log
chmod 644 /var/log/article-parser.log

# Настройка ротации логов
cat > /etc/logrotate.d/article-parser << 'EOF'
/var/log/article-parser.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 root root
}
EOF

echo -e "${GREEN}Основная настройка завершена.${NC}"
echo "Пожалуйста, создайте файл .env с настройками Supabase:"
echo "cp .env.example .env"
echo "nano .env"

echo -e "${GREEN}Чтобы запустить парсер как службу, выполните:${NC}"
echo "systemctl enable article-parser"
echo "systemctl start article-parser"

echo -e "${GREEN}Для проверки статуса службы:${NC}"
echo "systemctl status article-parser"

echo -e "${GREEN}Для просмотра логов:${NC}"
echo "tail -f /var/log/article-parser.log"