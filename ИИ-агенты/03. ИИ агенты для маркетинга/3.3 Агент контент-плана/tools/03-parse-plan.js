// Узел «Разбор контент-плана».
// Достаёт JSON из ответа модели, нормализует его и проверяет план на соблюдение правил
// заказчика. Проверки не выбрасывают исключение, а складываются в массив checks —
// их затем показывает узел самопроверки. Если JSON не разобран, план тоже не роняет
// сценарий: он помечается браком и уходит на перегенерацию, как и обычный брак.

const raw = $json.text || ($json.output || '');
const prepared = $('Подготовка входных данных').first().json;

// Номер прогона этого узла, который n8n ведёт сам при зацикливании. Нужен и на
// аварийном пути (неразобранный ответ), поэтому считается до всех return.
const attempt = $runIndex + 1;

// --- извлечение блока между маркерами ---------------------------------------
// Модель иногда «проговаривает» ход мысли перед ответом, а иногда отвечает
// не туда, и между маркерами оказывается не JSON. Поэтому кандидатов несколько
// и берём первый, который действительно разбирается: содержимое маркеров,
// затем самый внешний {...} во всём ответе.
const m = String(raw).match(/###ПЛАН###([\s\S]*?)###КОНЕЦ###/);
const candidates = [];
if (m) candidates.push({ text: m[1].trim(), recovered: false });

const a = String(raw).indexOf('{');
const b = String(raw).lastIndexOf('}');
if (a >= 0 && b > a) candidates.push({ text: String(raw).slice(a, b + 1), recovered: true });

let data = null;
let recovered = false;
for (let i = 0; i < candidates.length; i++) {
  try {
    data = JSON.parse(candidates[i].text);
    recovered = candidates[i].recovered;
    break;
  } catch (e) { /* пробуем следующего кандидата */ }
}
if (!data) {
  const head = String(raw).slice(0, 300);
  // Первая попытка: не роняем сценарий, а отправляем задание стратегу заново —
  // модель иногда отвечает не по формату, и повтор её обычно выправляет.
  if (attempt < 2) {
    const retry = [
      prepared.strategist_input || prepared.strategist_pack,
      '',
      'ВАЖНО: предыдущий ответ не удалось разобрать. Ты ответил обычным текстом вместо JSON:',
      head,
      '',
      'Ответь заново и верни ТОЛЬКО JSON контент-плана между маркерами ###ПЛАН### и ###КОНЕЦ###. '
        + 'Никаких пояснений, рассуждений и черновиков — только JSON.',
    ].join('\n');

    return [{
      json: {
        plan: [],
        selected: [],
        checks: [{
          name: 'Ответ модели разобран в структуру контент-плана',
          ok: false,
          detail: 'ответ не является JSON, план уходит на перегенерацию. Начало ответа: ' + head,
        }],
        checks_passed: 0,
        checks_total: 1,
        balance_comment: '',
        log_insights: [],
        plan_days: prepared.plan_days,
        plan_start: prepared.plan_start,
        plan_end: prepared.plan_end,
        copywriter_task: '',
        copywriter_task_input: '',
        strategist_pack: prepared.strategist_pack,
        strategist_input: retry,
        attempt: attempt,
        need_retry: true,
        plan_ok: false,
      },
    }];
  }

  // Вторая попытка тоже не удалась — дальше идти не с чем, это честная ошибка.
  throw new Error('Ответ модели не удалось разобрать как JSON контент-плана. Начало ответа: ' + head);
}

const plan = Array.isArray(data.plan) ? data.plan : [];
const selected = Array.isArray(data.selected_for_writing) ? data.selected_for_writing : [];

// --- нормализация -----------------------------------------------------------
const RUBRICS = ['Тишина как ресурс', 'Как здесь устроено', 'Истории гостей', 'Практики восстановления'];
const FORMATS = ['пост', 'карусель', 'короткое видео', 'подборка', 'опрос', 'карточка-практика'];
const TASKS = ['объяснить', 'показать продукт', 'кейс', 'вовлечь', 'подвести к бронированию', 'практика'];
const SELLING = 'подвести к бронированию';

const norm = plan.map(function (p, i) {
  const rub = String(p.rubric || '').trim();
  return {
    day: Number(p.day) || i + 1,
    date: String(p.date || '').trim(),
    weekday: String(p.weekday || '').trim(),
    rubric: RUBRICS.filter(function (r) { return r.toLowerCase() === rub.toLowerCase(); })[0] || rub,
    task: String(p.task || '').trim().toLowerCase(),
    topic: String(p.topic || '').trim(),
    format: String(p.format || '').trim().toLowerCase(),
    platforms: Array.isArray(p.platforms) && p.platforms.length ? p.platforms : ['Telegram', 'ВКонтакте'],
    goal: String(p.goal || '').trim(),
    idea: String(p.idea || '').trim(),
  };
}).sort(function (a, b) { return a.day - b.day; });

// выбранные темы дополняем данными из плана, чтобы копирайтер получил всё сразу
const sel = selected.map(function (s) {
  const slot = Number(s.slot) || 0;
  const day = Number(s.day) || 0;
  const fromPlan = norm.filter(function (p) { return p.day === day; })[0] || {};
  return {
    slot: slot,
    kind: String(s.kind || (slot === 3 ? 'reels' : 'post')).trim(),
    day: day,
    topic: String(s.topic || fromPlan.topic || '').trim(),
    rubric: String(s.rubric || fromPlan.rubric || '').trim(),
    task: String(s.task || fromPlan.task || '').trim(),
    format: String(s.format || fromPlan.format || '').trim(),
    date: fromPlan.date || '',
    weekday: fromPlan.weekday || '',
    idea: fromPlan.idea || '',
    why: String(s.why || '').trim(),
  };
}).sort(function (a, b) { return a.slot - b.slot; });

// --- проверки ---------------------------------------------------------------
const checks = [];
function check(name, ok, detail) { checks.push({ name: name, ok: !!ok, detail: detail }); }

// Проверяем суть, а не оформление: важно, что ответ разобран в структуру и она
// корректна. Если модель «проговорилась» и не поставила маркеры, но JSON на месте —
// план всё равно рабочий, поэтому это примечание, а не провал проверки.
check('Ответ модели разобран в структуру контент-плана', true,
  recovered
    ? 'маркеры ###ПЛАН### … ###КОНЕЦ### не найдены, JSON извлечён из текста ответа и проверен'
    : 'по маркерам ###ПЛАН### … ###КОНЕЦ###');
check('В плане 7 публикаций на 7 дней', norm.length === 7, 'получено: ' + norm.length);
check('Даты совпадают с календарём недели',
  norm.length === 7 && norm.every(function (p, i) { return p.date === prepared.plan_days[i].date; }),
  norm.map(function (p) { return p.date; }).join(', '));

const taskCount = {};
norm.forEach(function (p) { taskCount[p.task] = (taskCount[p.task] || 0) + 1; });
check('Задачи распределены по правилу (объяснить ×2, остальные по 1)',
  taskCount['объяснить'] === 2 &&
  ['показать продукт', 'кейс', 'вовлечь', 'подвести к бронированию', 'практика']
    .every(function (t) { return taskCount[t] === 1; }),
  Object.keys(taskCount).map(function (k) { return k + '=' + taskCount[k]; }).join(', '));

check('Нет посторонних рубрик и задач',
  norm.every(function (p) { return RUBRICS.indexOf(p.rubric) >= 0 && TASKS.indexOf(p.task) >= 0; }),
  norm.filter(function (p) { return RUBRICS.indexOf(p.rubric) < 0 || TASKS.indexOf(p.task) < 0; })
    .map(function (p) { return p.day + ': ' + p.rubric + '/' + p.task; }).join('; ') || 'ок');

check('Использованы все четыре рубрики',
  RUBRICS.every(function (r) { return norm.some(function (p) { return p.rubric === r; }); }),
  RUBRICS.filter(function (r) { return !norm.some(function (p) { return p.rubric === r; }); }).join(', ') || 'ок');

check('Форматы только из разрешённого списка',
  norm.every(function (p) { return FORMATS.indexOf(p.format) >= 0; }),
  norm.filter(function (p) { return FORMATS.indexOf(p.format) < 0; }).map(function (p) { return p.day + ': ' + p.format; }).join('; ') || 'ок');

const formatRepeats = [];
for (let i = 1; i < norm.length; i++) {
  if (norm[i].format === norm[i - 1].format) formatRepeats.push(norm[i].day);
}
check('Один формат не идёт два дня подряд', formatRepeats.length === 0,
  formatRepeats.length ? 'повтор в дни: ' + formatRepeats.join(', ') : 'ок');

check('Продающая публикация не первая в неделе',
  norm.length > 0 && norm[0].task !== SELLING,
  norm.length ? 'день 1: ' + norm[0].task : 'план пуст');

const taken = (prepared.topics_taken || []).map(function (t) { return t.toLowerCase(); });
const dupes = norm.filter(function (p) {
  const t = p.topic.toLowerCase();
  return taken.some(function (x) { return x === t || (x.length > 12 && t.indexOf(x) >= 0) || (t.length > 12 && x.indexOf(t) >= 0); });
});
check('Темы не повторяют публикации последних двух недель', dupes.length === 0,
  dupes.map(function (p) { return p.day + ': ' + p.topic; }).join('; ') || 'ок');

check('Для проработки выбраны 3 темы: 2 поста и рилс',
  sel.length === 3 &&
  sel.filter(function (s) { return s.kind === 'post'; }).length === 2 &&
  sel.some(function (s) { return s.kind === 'reels'; }),
  sel.map(function (s) { return s.slot + ':' + s.kind; }).join(', '));
check('Выбранные темы есть в плане',
  sel.every(function (s) { return norm.some(function (p) { return p.day === s.day && p.topic === s.topic; }); }),
  sel.filter(function (s) { return !norm.some(function (p) { return p.day === s.day && p.topic === s.topic; }); })
    .map(function (s) { return s.slot + ': ' + s.topic; }).join('; ') || 'ок');

// --- задание копирайтеру ----------------------------------------------------
const posts = sel.filter(function (s) { return s.kind === 'post'; });
const reels = sel.filter(function (s) { return s.kind === 'reels'; });

const task = [
  'БРИФ БРЕНДА:',
  $('1. Бриф бренда (текст)').first().json.data.trim(),
  '',
  'ПРАВИЛА КОНТЕНТА:',
  $('2. Правила контента (текст)').first().json.data.trim(),
  '',
  'ВЫВОДЫ ИЗ ЖУРНАЛА ПУБЛИКАЦИЙ:',
  (data.log_insights || []).map(function (x, i) { return (i + 1) + '. ' + x; }).join('\n'),
  '',
  'ТЕМЫ ДЛЯ ПОЛНОЙ ПРОРАБОТКИ:',
  posts.map(function (s, i) {
    return [
      'ПОСТ_' + (i + 1) + ':',
      '  дата: ' + s.date + ' (' + s.weekday + ')',
      '  рубрика: ' + s.rubric,
      '  задача: ' + s.task,
      '  формат: ' + s.format,
      '  тема: ' + s.topic,
      '  идея: ' + s.idea,
      '  зачем: ' + s.why,
    ].join('\n');
  }).join('\n\n'),
  '',
  reels.map(function (s) {
    return [
      'РИЛС:',
      '  дата: ' + s.date + ' (' + s.weekday + ')',
      '  рубрика: ' + s.rubric,
      '  задача: ' + s.task,
      '  тема: ' + s.topic,
      '  идея: ' + s.idea,
      '  зачем: ' + s.why,
    ].join('\n');
  }).join('\n'),
].join('\n');

// --- повторная генерация при браке -------------------------------------------
// План иногда не проходит проверки с первого раза. Тогда стратег пересобирает
// его заново — не больше двух попыток, чтобы цикл завершился.
const planOk = checks.every(function (c) { return c.ok; });
const needRetry = !planOk && attempt < 2;

const failedNow = checks.filter(function (c) { return !c.ok; })
  .map(function (c) { return '- ' + c.name + ' → ' + c.detail; }).join('\n');

const notice = [
  'ВАЖНО: предыдущий план забракован проверкой. Что исправить:',
  failedNow,
  '',
  'Собери план заново с нуля, строго по правилам. Не повторяй прежний вариант.',
].join('\n');

const retryPack = needRetry
  ? [prepared.strategist_input || prepared.strategist_pack, '', notice].join('\n')
  : '';

return [{
  json: {
    plan: norm,
    selected: sel,
    checks: checks,
    checks_passed: checks.filter(function (c) { return c.ok; }).length,
    checks_total: checks.length,
    balance_comment: String(data.balance_comment || '').trim(),
    log_insights: data.log_insights || [],
    plan_days: prepared.plan_days,
    plan_start: prepared.plan_start,
    plan_end: prepared.plan_end,
    copywriter_task: task,
    // Задание для узла-копирайтера: при повторе — с перечнем замечаний,
    // иначе исходное. Лежит в одном поле, чтобы выражение узла было простым.
    copywriter_task_input: needRetry ? task + '\n\n' + notice : task,
    strategist_pack: prepared.strategist_pack,
    // Задание для узла-стратега: на первом прогоне — исходный пакет,
    // при повторе — пакет с перечнем замечаний проверки.
    strategist_input: retryPack || prepared.strategist_input || prepared.strategist_pack,
    attempt: attempt,
    need_retry: needRetry,
    plan_ok: planOk,
  },
}];
