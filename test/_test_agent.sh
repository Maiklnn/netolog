#!/bin/bash
# Тестирование ИИ-агента: 3 поручения с разными формулировками (GET)

echo "=== Тест 1: Точная дата (к пятнице до 15:00) ==="
echo "Сообщение: Напомни подготовить отчёт по продажам к пятнице до 15:00"
echo ""
curl -s -G http://localhost:5678/webhook/task-agent \
  --data-urlencode 'message=Напомни подготовить отчёт по продажам к пятнице до 15:00' \
  --max-time 90
echo ""
echo ""

echo "=== Тест 2: Относительный срок (завтра утром) ==="
echo "Сообщение: Позвонить клиенту Иванову завтра утром"
echo ""
curl -s -G http://localhost:5678/webhook/task-agent \
  --data-urlencode 'message=Позвонить клиенту Иванову завтра утром' \
  --max-time 90
echo ""
echo ""

echo "=== Тест 3: Свободная формулировка (без явного срока) ==="
echo "Сообщение: Надо обновить презентацию для встречи с партнёрами"
echo ""
curl -s -G http://localhost:5678/webhook/task-agent \
  --data-urlencode 'message=Надо обновить презентацию для встречи с партнёрами' \
  --max-time 90
echo ""
echo ""
echo "=== Тесты завершены ==="