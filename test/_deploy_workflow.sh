#!/bin/bash
# Обновление workflow: удалить старый, импортировать новый, активировать, запустить n8n

echo "1. Останавливаю n8n..."
pkill -f 'n8n start' 2>/dev/null
sleep 2

echo "2. Удаляю старые workflow из БД..."
sqlite3 /home/vagrant/.n8n/database.sqlite \
  "DELETE FROM webhook_entity WHERE workflowId IN (SELECT id FROM workflow_entity WHERE name LIKE '%ИИ-агент%');" \
  "DELETE FROM workflow_entity WHERE name LIKE '%ИИ-агент%';"
echo "   Готово"

echo "3. Импортирую новый workflow..."
export NODES_EXCLUDE=[]
export N8N_HOST=0.0.0.0
export N8N_PORT=5678
export N8N_PROTOCOL=http
export N8N_EDITOR_BASE_URL=http://192.168.56.50:5678
export N8N_LISTEN_ON=public
export N8N_SECURE_COOKIE=false
export WEBHOOK_URL=http://192.168.56.50:5678/
n8n import:workflow --input=/tmp/workflow.json 2>&1 | tail -3

echo "4. Получаю ID нового workflow..."
NEW_ID=$(sqlite3 /home/vagrant/.n8n/database.sqlite "SELECT id FROM workflow_entity WHERE name LIKE '%ИИ-агент%' ORDER BY id DESC LIMIT 1;")
echo "   New ID: $NEW_ID"

echo "5. Активирую workflow..."
n8n update:workflow --id=$NEW_ID --active=true 2>&1 | tail -3

echo "6. Запускаю n8n через setsid..."
setsid bash -c 'export NODES_EXCLUDE=[]; export N8N_HOST=0.0.0.0; export N8N_PORT=5678; export N8N_PROTOCOL=http; export N8N_EDITOR_BASE_URL=http://192.168.56.50:5678; export N8N_LISTEN_ON=public; export N8N_SECURE_COOKIE=false; export WEBHOOK_URL=http://192.168.56.50:5678/; n8n start > /home/vagrant/n8n_output.log 2>&1' &
sleep 8

echo "7. Проверяю здоровье n8n..."
HEALTH=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:5678/healthz)
echo "   healthz: $HEALTH"

echo "8. Проверяю регистрацию webhook..."
sqlite3 /home/vagrant/.n8n/database.sqlite "SELECT webhookPath, method FROM webhook_entity;"

echo "=== Готово ==="