/**
 * Генератор workflow JSON для ИИ-агента:
 * Telegram (Webhook) → Ollama LLM → Яндекс.Календарь
 *
 * Запуск: node _generate_task_agent_workflow.js
 * Результат: n8n-workflow-task-agent.json
 */
const fs = require('fs');
const path = require('path');

// Читаем jsCode из отдельных файлов (raw JS, без JSON-экранирования)
function readCode(filename) {
  let content = fs.readFileSync(path.join(__dirname, filename), 'utf8');
  if (content.charCodeAt(0) === 0xFEFF) content = content.slice(1);
  return content.trim();
}

const prepareLLMCode = readCode('_code_prepare_llm.js');
const parseBuildCode = readCode('_code_parse_build.js');
const caldavPutCode = readCode('_code_caldav_put.js');
const prepareResponseCode = readCode('_code_prepare_response.js');

// ─── Узлы workflow ────────────────────────────────────────────────
const nodes = [
  {
    parameters: {
      httpMethod: 'GET',
      path: 'task-agent',
      responseMode: 'responseNode',
      options: {}
    },
    id: 'webhook-trigger',
    name: 'Webhook Telegram',
    type: 'n8n-nodes-base.webhook',
    typeVersion: 2,
    position: [0, 300],
    webhookId: 'task-agent-webhook'
  },
  {
    parameters: { mode: 'runOnceForAllItems', jsCode: prepareLLMCode },
    id: 'prepare-llm',
    name: 'Prepare LLM Request',
    type: 'n8n-nodes-base.code',
    typeVersion: 2,
    position: [220, 300]
  },
  {
    parameters: {
      method: 'POST',
      url: 'http://10.0.2.2:11434/api/chat',
      sendBody: true,
      specifyBody: 'json',
      jsonBody: '={{ JSON.stringify($json.requestBody) }}',
      options: {}
    },
    id: 'ollama-llm',
    name: 'Ollama LLM Analysis',
    type: 'n8n-nodes-base.httpRequest',
    typeVersion: 4.2,
    position: [440, 300]
  },
  {
    parameters: { mode: 'runOnceForAllItems', jsCode: parseBuildCode },
    id: 'parse-build',
    name: 'Parse and Build Event',
    type: 'n8n-nodes-base.code',
    typeVersion: 2,
    position: [660, 300]
  },
  {
    parameters: { mode: 'runOnceForAllItems', jsCode: caldavPutCode },
    id: 'yandex-calendar',
    name: 'Create Yandex Calendar Event',
    type: 'n8n-nodes-base.code',
    typeVersion: 2,
    position: [880, 300],
    continueOnFail: true
  },
  {
    parameters: { mode: 'runOnceForAllItems', jsCode: prepareResponseCode },
    id: 'prepare-response',
    name: 'Prepare Response',
    type: 'n8n-nodes-base.code',
    typeVersion: 2,
    position: [1100, 300]
  },
  {
    parameters: {
      respondWith: 'json',
      responseCode: 200,
      responseBody: '={{ $json }}'
    },
    id: 'respond-webhook',
    name: 'Respond to Webhook',
    type: 'n8n-nodes-base.respondToWebhook',
    typeVersion: 1,
    position: [1320, 300]
  }
];

// ─── Соединения ───────────────────────────────────────────────────
const connections = {
  'Webhook Telegram': {
    main: [[{ node: 'Prepare LLM Request', type: 'main', index: 0 }]]
  },
  'Prepare LLM Request': {
    main: [[{ node: 'Ollama LLM Analysis', type: 'main', index: 0 }]]
  },
  'Ollama LLM Analysis': {
    main: [[{ node: 'Parse and Build Event', type: 'main', index: 0 }]]
  },
  'Parse and Build Event': {
    main: [[{ node: 'Create Yandex Calendar Event', type: 'main', index: 0 }]]
  },
  'Create Yandex Calendar Event': {
    main: [[{ node: 'Prepare Response', type: 'main', index: 0 }]]
  },
  'Prepare Response': {
    main: [[{ node: 'Respond to Webhook', type: 'main', index: 0 }]]
  }
};

// ─── Сборка и запись ──────────────────────────────────────────────
const workflow = {
  id: require('crypto').randomUUID(),
  name: 'ИИ-агент: Telegram → LLM → Яндекс.Календарь',
  nodes: nodes,
  connections: connections,
  active: false,
  settings: { executionOrder: 'v1' }
};

const outputPath = path.join(__dirname, 'n8n-workflow-task-agent.json');
fs.writeFileSync(outputPath, JSON.stringify(workflow, null, 2), 'utf8');

console.log('✅ Workflow JSON создан: ' + outputPath);
console.log('   Узлов: ' + workflow.nodes.length);
console.log('   Соединений: ' + Object.keys(connections).length);
console.log('   jsCode Prepare LLM: ' + prepareLLMCode.length + ' символов');
console.log('   jsCode Parse Build: ' + parseBuildCode.length + ' символов');
console.log('   jsCode CalDAV PUT:  ' + caldavPutCode.length + ' символов');
console.log('   jsCode Response:    ' + prepareResponseCode.length + ' символов');