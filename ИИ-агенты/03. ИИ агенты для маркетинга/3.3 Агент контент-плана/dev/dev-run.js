// Локальный прогон агента без n8n.
// Эмулирует окружение Code-узла ($json, $('имя узла'), helpers.prepareBinaryData)
// и вызывает ту же модель Ollama напрямую, чтобы отладить логику до деплоя.
//
// Запуск:  node dev/dev-run.js

const fs = require('fs');
const path = require('path');

const DIR = path.resolve(__dirname, '..');
const TOOLS = path.join(DIR, 'tools');
const DATA = path.join(DIR, 'data');
const OUT = path.join(__dirname, 'out');
const OLLAMA = 'http://localhost:11434';
const MODEL = 'deepseek-v4.1-flash:cloud';

if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true });

const store = {};

function ctx(json) {
  return {
    $json: json,
    $: function (name) {
      if (!(name in store)) throw new Error('Узел не найден: ' + name);
      return { first: function () { return { json: store[name] }; } };
    },
    helpers: {
      prepareBinaryData: async function (buf, fileName, mimeType) {
        return { data: buf.toString('base64'), fileName: fileName, mimeType: mimeType };
      },
    },
  };
}

async function runNode(file, json) {
  const code = fs.readFileSync(path.join(TOOLS, file), 'utf8');
  const c = ctx(json);
  const fn = new Function('$json', '$', 'helpers',
    'return (async () => {\n' + code + '\n})();');
  const res = await fn(c.$json, c.$, c.helpers);
  return res;
}

const FRESH = process.argv.indexOf('--fresh') >= 0;

async function llm(systemFile, user, temperature) {
  // REPLAY_<промпт>=<файл> — прогнать парсер на сохранённом ответе модели
  const replay = process.env['REPLAY_' + (systemFile.indexOf('strategist') >= 0 ? 'PLAN' : 'COPY')];
  if (replay) {
    console.log('     (повтор сохранённого ответа) ' + replay);
    return fs.readFileSync(replay, 'utf8');
  }
  const cacheFile = path.join(OUT, systemFile.replace('.md', '') + '-raw.txt');
  if (!FRESH && fs.existsSync(cacheFile)) {
    console.log('     (из кэша) ' + systemFile);
    return fs.readFileSync(cacheFile, 'utf8');
  }
  const system = fs.readFileSync(path.join(TOOLS, systemFile), 'utf8').trim();
  const res = await fetch(OLLAMA + '/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: MODEL,
      stream: false,
      options: { temperature: temperature },
      messages: [
        { role: 'system', content: system },
        { role: 'user', content: user },
      ],
    }),
  });
  if (!res.ok) throw new Error('Ollama ' + res.status + ': ' + (await res.text()).slice(0, 300));
  const j = await res.json();
  fs.writeFileSync(path.join(OUT, systemFile.replace('.md', '') + '-raw.txt'),
    j.message.content, 'utf8');
  return j.message.content;
}

async function step(title, fn) {
  const t0 = Date.now();
  const r = await fn();
  console.log('[ok] ' + title + ' (' + ((Date.now() - t0) / 1000).toFixed(1) + 's)');
  return r;
}

(async () => {
  store['1. Бриф бренда (текст)'] = { data: fs.readFileSync(path.join(DATA, 'brand-brief.md'), 'utf8') };
  store['2. Правила контента (текст)'] = { data: fs.readFileSync(path.join(DATA, 'content-rules.md'), 'utf8') };
  store['3. Журнал публикаций (текст)'] = { data: fs.readFileSync(path.join(DATA, 'content-log.csv'), 'utf8') };

  // 01
  const prep = await step('01 prepare-input', async () => (await runNode('01-prepare-input.js', {}))[0].json);
  store['Подготовка входных данных'] = prep;
  fs.writeFileSync(path.join(OUT, '01-strategist-pack.txt'), prep.strategist_pack, 'utf8');

  // LLM: стратег
  const planRaw = await step('LLM strategist', () => llm('02-strategist-prompt.md', prep.strategist_pack, 0.2));
  store['Контент-стратег (LLM)'] = { text: planRaw };

  // 03
  const parsed = await step('03 parse-plan', async () => (await runNode('03-parse-plan.js', store['Контент-стратег (LLM)']))[0].json);
  store['Разбор контент-плана'] = parsed;
  console.log('     checks: ' + parsed.checks_passed + '/' + parsed.checks_total +
    (parsed.checks_total !== parsed.checks_passed ? ' FAILED: ' + parsed.checks.filter(function (c) { return !c.ok; }).map(function (c) { return c.name; }).join(' | ') : ''));

  // LLM: копирайтер
  const textRaw = await step('LLM copywriter', () => llm('04-copywriter-prompt.md', parsed.copywriter_task, 0.4));
  store['Копирайтер (LLM)'] = { text: textRaw };

  // 05
  const content = await step('05 parse-content', async () => (await runNode('05-parse-content.js', store['Копирайтер (LLM)']))[0].json);
  store['Разбор контента'] = content;
  console.log('     checks: ' + content.checks_passed + '/' + content.checks_total +
    (content.checks_total !== content.checks_passed ? ' FAILED: ' + content.checks.filter(function (c) { return !c.ok; }).map(function (c) { return c.name; }).join(' | ') : ''));

  // 06
  const check = await step('06 self-check', async () => (await runNode('06-self-check.js', store['Разбор контента']))[0].json);
  store['Самопроверка качества'] = check;

  // 07
  const demo = await step('07 build-demo', async () => (await runNode('07-build-demo.js', store['Самопроверка качества']))[0].json);
  store['Сборка демо-публикации'] = demo;

  // 08
  const doc = await step('08 build-document', async () => (await runNode('08-build-document.js', store['Сборка демо-публикации']))[0].json);
  store['Сборка итогового документа'] = doc;

  // 09 + 10 (пишем реальные файлы в dev/out)
  const mdItem = await step('09 prepare-md', async () => (await runNode('09-prepare-md.js', store['Сборка итогового документа']))[0]);
  fs.writeFileSync(path.join(OUT, mdItem.json.file_name), Buffer.from(mdItem.binary.data.data, 'base64'));
  console.log('     file: ' + mdItem.json.file_name);

  const csvItem = await step('10 prepare-csv', async () => (await runNode('10-prepare-csv.js', {}))[0]);
  fs.writeFileSync(path.join(OUT, csvItem.json.file_name), Buffer.from(csvItem.binary.data.data, 'base64'));
  console.log('     file: ' + csvItem.json.file_name + ' rows=' + csvItem.json.demo_rows);

  fs.writeFileSync(path.join(OUT, 'run-summary.json'), JSON.stringify({
    plan_start: doc.plan_start,
    plan_end: doc.plan_end,
    verdict: doc.verdict,
    checks_passed: doc.checks_passed,
    checks_total: doc.checks_total,
    checklist: doc.checklist,
    plan: doc.plan,
    failed_checks: doc.failed_checks,
  }, null, 2), 'utf8');

  console.log('DONE -> dev/out');
})().catch(function (e) {
  console.error('ERROR: ' + e.message);
  process.exit(1);
});
