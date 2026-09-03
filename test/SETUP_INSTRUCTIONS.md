# Инструкция по настройке n8n Workflow «Классификация сообщений»

## Архитектура workflow

```
Webhook (GET) → Prepare LLM Request → Ollama LLM Analysis → Parse LLM Response → Category Switch
                                                                                      ├─ price →       Save to File → /home/vagrant/price.txt
                                                                                      ├─ consultation → Save to File → /home/vagrant/consultation.txt
                                                                                      └─ other →       Save to File → /home/vagrant/other.txt
```

**Тригер:** Webhook (GET-запрос на `/webhook/message-classification`)
**LLM:** Локальный Ollama (`glm-5.2:cloud`) по адресу `http://10.0.2.2:11434`
**Хранилище:** Текстовые файлы на сервере VM (один файл на категорию)

---

## Шаг 0. Включение узла Execute Command (обязательно)

> ⚠️ **Критично:** В n8n v2+ узел `Execute Command` (тип `n8n-nodes-base.executeCommand`)
> **отключён по умолчанию** из соображений безопасности. Без этой настройки импорт
> workflow завершится с ошибкой `Unrecognized node type: n8n-nodes-base.executeCommand`.

1. Подключитесь к VM: `vagrant ssh` (из директории `C:/Users/MIXA/vmbitrix-vm`)
2. Проверьте, что в `~/.bashrc` есть строка `export NODES_EXCLUDE=[]`:
   ```bash
   grep NODES_EXCLUDE ~/.bashrc
   ```
   Если её нет — добавьте: `echo 'export NODES_EXCLUDE=[]' >> ~/.bashrc`
3. Перезапустите n8n (загружается с переменной `NODES_EXCLUDE=[]`):
   ```bash
   # найти и завершить текущий процесс n8n
   ps aux | grep 'n8n start' | grep -v grep   # узнать PID
   kill <PID>
   # запустить заново через startup-скрипт
   setsid bash ~/start_n8n.sh < /dev/null >&1
   ```
4. Дождитесь сообщения `n8n ready on ::, port 5678` в логе:
   ```bash
   tail -f ~/n8n_output.log
   ```

---

## Шаг 1. Импорт workflow в n8n

1. Откройте n8n UI: `http://192.168.56.50:5678`
2. Нажмите **Add Workflow** (создать новый workflow)
3. Нажмите **⋮** (три точки) в правом верхнем углу → **Import from File**
4. Выберите файл `n8n-workflow-message-classification.json`
5. На холсте должны появиться **6 узлов**:
   - Webhook
   - Prepare LLM Request
   - Ollama LLM Analysis
   - Parse LLM Response
   - Category Switch
   - Save to File
6. Нажмите **Save** (Ctrl+S)

> ⚠️ **Важно:** Никаких внешних credentials не требуется — все данные
> записываются в локальные текстовые файлы на сервере VM.

---

## Шаг 2. Тестирование workflow

### Вариант A — Тест через n8n UI (без активации)

1. В n8n откройте workflow
2. Нажмите **Listen for Test Event** на узле Webhook
3. n8n покажет **Test URL** вида:
   `http://192.168.56.50:5678/webhook-test/message-classification`
4. Откройте URL в браузере или отправьте GET-запрос с сообщением в query-параметре:

```bash
# Тест 1 — категория "price" (вопрос о ценах)
curl -G "http://192.168.56.50:5678/webhook-test/message-classification" \
  --data-urlencode "message=Сколько стоит подписка на ваш сервис?"

# Тест 2 — категория "consultation" (вопрос-консультация)
curl -G "http://192.168.56.50:5678/webhook-test/message-classification" \
  --data-urlencode "message=Подскажите, как интегрировать вашу систему с нашим CRM?"

# Тест 3 — категория "other" (прочее)
curl -G "http://192.168.56.50:5678/webhook-test/message-classification" \
  --data-urlencode "message=Здравствуйте, спасибо за помощь!"
```

Или прямо в браузере (скопируйте в адресную строку):

```
http://192.168.56.50:5678/webhook-test/message-classification?message=Сколько стоит подписка?
```

5. После каждого запроса n8n должен показать выполнение цепочки узлов
6. Проверьте текстовые файлы на сервере VM — должна появиться новая строка:

```bash
# На VM (через SSH: vagrant ssh)
cat /home/vagrant/price.txt
cat /home/vagrant/consultation.txt
cat /home/vagrant/other.txt
```

   Каждая строка содержит: `[дата] message=... | summary=... | reply_draft=... | status=...`

### Вариант B — Активированный webhook (production)

1. Нажмите переключатель **Active** в правом верхнем углу n8n
2. Production URL: `http://192.168.56.50:5678/webhook/message-classification`
3. Отправляйте те же curl-запросы, заменив `/webhook-test/` на `/webhook/`

---

## Шаг 3. Диагностика

### Проверка Ollama (на VM)

```bash
curl http://10.0.2.2:11434/api/tags
# Должен вернуть список моделей, включая glm-5.2:cloud
```

### Проверка webhook (на VM)

```bash
curl -G "http://localhost:5678/webhook-test/message-classification" \
  --data-urlencode "message=test"
# Должен вернуть: Message received - processing started
```

### Частые проблемы

| Проблема | Решение |
|---|---|
| Webhook не отвечает | Убедитесь что n8n запущен: `pgrep -f n8n`. Проверьте `N8N_SECURE_COOKIE=false` |
| Ollama: connection refused | Проверьте `curl http://10.0.2.2:11434/api/tags` на VM. Ollama должна быть запущена на хосте |
| Файл не создаётся | Проверьте права пользователя n8n на запись в `/home/vagrant/`. Выполните `ls -la /home/vagrant/*.txt` |
| LLM вернул не JSON | Узел Parse LLM Response имеет fallback: извлечение JSON через regex + нормализация категории |
| Пустая категория | Если LLM не распознал категорию, она автоматически устанавливается в `other` |

---

## Структура файлов

| Файл | Описание |
|---|---|
| `n8n-workflow-message-classification.json` | JSON workflow для импорта в n8n (6 узлов) |
| `SETUP_INSTRUCTIONS.md` | Данная инструкция |