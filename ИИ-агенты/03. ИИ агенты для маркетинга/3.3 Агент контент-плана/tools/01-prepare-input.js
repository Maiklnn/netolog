// Узел «Подготовка входных данных».
// Собирает три источника (бриф бренда, правила контента, журнал публикаций) в один
// «пакет для контент-стратега»: считает частоты, результативность рубрик и форматов,
// вычисляет даты планируемой недели и список тем, которые повторять нельзя.

const brief = $('1. Бриф бренда (текст)').first().json.data || '';
const rules = $('2. Правила контента (текст)').first().json.data || '';
const logRaw = $('3. Журнал публикаций (текст)').first().json.data || '';

// --- разбор журнала публикаций (CSV с разделителем «;») ---------------------
function parseCsv(text) {
  const lines = text.split(/\r?\n/).filter(function (l) { return l.trim(); });
  const rows = [];
  for (let i = 1; i < lines.length; i++) {           // первая строка — заголовок
    const c = lines[i].split(';');
    rows.push({
      id: (c[0] || '').trim(),
      date: (c[1] || '').trim(),
      platform: (c[2] || '').trim(),
      rubric: (c[3] || '').trim(),
      task: (c[4] || '').trim(),
      topic: (c[5] || '').trim(),
      format: (c[6] || '').trim(),
      status: (c[7] || '').trim(),
      views: Number(c[8]) || 0,
      reactions: Number(c[9]) || 0,
      comments: Number(c[10]) || 0,
      saves: Number(c[11]) || 0,
      er: Number(String(c[12] || '').replace(',', '.')) || 0,
    });
  }
  return rows;
}

const log = parseCsv(logRaw).filter(function (r) { return r.date && r.topic; });

// --- даты планируемой недели: ближайший понедельник + 6 дней ---------------
function iso(d) {
  return d.toISOString().slice(0, 10);
}
const WEEKDAYS = ['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье'];

const today = new Date();
const runDate = iso(today);
const start = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate()));
const dow = start.getUTCDay();                        // 0 = вс
const shift = dow === 1 ? 0 : (8 - dow) % 7;         // до ближайшего понедельника
start.setUTCDate(start.getUTCDate() + shift);

const planDays = [];
for (let i = 0; i < 7; i++) {
  const d = new Date(start);
  d.setUTCDate(d.getUTCDate() + i);
  planDays.push({ date: iso(d), weekday: WEEKDAYS[i] });
}

// --- агрегаты по журналу ----------------------------------------------------
function avg(rows, field) {
  if (!rows.length) return 0;
  return Math.round(rows.reduce(function (s, r) { return s + r[field]; }, 0) / rows.length * 10) / 10;
}

function groupBy(rows, key) {
  const map = {};
  rows.forEach(function (r) { (map[r[key]] = map[r[key]] || []).push(r); });
  return map;
}

const byRubric = groupBy(log, 'rubric');
const byFormat = groupBy(log, 'format');
const byTask = groupBy(log, 'task');

function summary(rows, field) {
  return Object.keys(rows).map(function (k) {
    return { name: k, count: rows[k].length, er: avg(rows[k], 'er'), comments: avg(rows[k], 'comments') };
  }).sort(function (a, b) { return b.er - a.er; });
}

const rubricStats = summary(byRubric);
const formatStats = summary(byFormat);
const taskStats = summary(byTask);

// --- что сработало и что не сработало (возврат выводов в следующий цикл) ----
const published = log.slice().sort(function (a, b) { return b.date.localeCompare(a.date); });
const topPosts = published.slice().sort(function (a, b) { return b.er - a.er; }).slice(0, 4);
const weakPosts = published.slice().sort(function (a, b) { return a.er - b.er; }).slice(0, 3);

// темы за последние 14 дней — их повторять нельзя
const last14 = published.filter(function (r) {
  const diff = (start - new Date(r.date + 'T00:00:00Z')) / 86400000;
  return diff >= 0 && diff <= 14;
});

// --- сборка текстового пакета для модели -----------------------------------
function statLine(s) {
  return '- ' + s.name + ': публикаций ' + s.count + ', средний ER ' + s.er + '%, среднее число комментариев ' + s.comments;
}
function postLine(r) {
  return '- ' + r.date + ' [' + r.rubric + '] «' + r.topic + '» — ' + r.format + ', ' + r.platform +
    ', ER ' + r.er + '%, комментариев ' + r.comments + ', сохранений ' + r.saves;
}

const pack = [
  '### БРИФ БРЕНДА (вход агента)',
  brief.trim(),
  '',
  '### ПРАВИЛА КОНТЕНТА (заданы пользователем, обязательны к исполнению)',
  rules.trim(),
  '',
  '### ЖУРНАЛ ПРОШЛЫХ ПУБЛИКАЦИЙ: ВСЕГО ' + log.length + ' ЗАПИСЕЙ',
  'Период журнала: ' + (published.length ? published[published.length - 1].date + ' … ' + published[0].date : 'нет данных'),
  '',
  'Результативность по рубрикам (от лучшей к худшей):',
  rubricStats.map(statLine).join('\n'),
  '',
  'Результативность по форматам:',
  formatStats.map(statLine).join('\n'),
  '',
  'Результативность по задачам публикаций:',
  taskStats.map(statLine).join('\n'),
  '',
  'Лучшие публикации по вовлечённости:',
  topPosts.map(postLine).join('\n'),
  '',
  'Слабые публикации:',
  weakPosts.map(postLine).join('\n'),
  '',
  '### ТЕМЫ ЗА ПОСЛЕДНИЕ 14 ДНЕЙ — ПОВТОРЯТЬ НЕЛЬЗЯ',
  last14.length ? last14.map(function (r) { return '- ' + r.date + ' [' + r.rubric + '] «' + r.topic + '»'; }).join('\n') : '- нет',
  '',
  '### КАЛЕНДАРЬ ПЛАНИРУЕМОЙ НЕДЕЛИ',
  'Дата запуска агента: ' + runDate,
  'Планируемая неделя: ' + planDays[0].date + ' — ' + planDays[6].date,
  planDays.map(function (d) { return '- ' + d.date + ' (' + d.weekday + ')'; }).join('\n'),
].join('\n');

return [{
  json: {
    strategist_pack: pack,
    // Готовое задание для узла-стратега. Отдельное поле, а не логика с «||»
    // в выражении узла: так задание лежит ровно в одном месте и на первом
    // прогоне оно гарантированно непустое.
    strategist_input: pack,
    plan_days: planDays,
    plan_start: planDays[0].date,
    plan_end: planDays[6].date,
    run_date: runDate,
    log_size: log.length,
    rubric_stats: rubricStats,
    format_stats: formatStats,
    top_topics: topPosts.map(function (r) { return r.topic; }),
    topics_taken: last14.map(function (r) { return r.topic; }),
  },
}];
