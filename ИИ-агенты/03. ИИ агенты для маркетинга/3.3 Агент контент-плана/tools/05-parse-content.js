// Узел «Разбор контента».
// Разбирает ответ копирайтера по маркерам на три материала, проверяет площадочные
// лимиты, различимость версий и запрещённые формулировки.

const raw = String($json.text || $json.output || '');
// last(), а не first(): если план перегенерировался после провала проверок,
// материалы написаны по последней версии плана.
const parsed = $('Разбор контент-плана').last().json;

function between(text, start, end) {
  const s = text.indexOf(start);
  if (s < 0) return '';
  const from = s + start.length;
  const e = text.indexOf(end, from);
  return (e < 0 ? text.slice(from) : text.slice(from, e)).trim();
}

function after(text, marker) {
  const s = text.indexOf(marker);
  return s < 0 ? '' : text.slice(s + marker.length).trim();
}

function countChars(t) {
  return t.replace(/\s+/g, ' ').trim().length;
}

// --- два поста --------------------------------------------------------------
// Модель иногда «проговаривает» ход мысли и набрасывает черновик прямо в ответе,
// поэтому блок берём по ПОСЛЕДНЕМУ вхождению закрывающего маркера: черновик
// остаётся левее и в материал не попадает. Если открывающий маркер потерян —
// отступаем к последнему маркеру площадки, а не к началу ответа.
function readPost(n) {
  const openTag = '###ПОСТ_' + n + '###';
  const closeTag = '###КОНЕЦ_ПОСТА_' + n + '###';
  const e = raw.lastIndexOf(closeTag);
  if (e < 0) return { telegram: '', vk: '', recovered: true };

  const s = raw.lastIndexOf(openTag, e);
  let block;
  let recovered = false;
  if (s >= 0) {
    block = raw.slice(s + openTag.length, e);
  } else {
    recovered = true;
    const t = raw.lastIndexOf('###TELEGRAM###', e);
    const v = raw.lastIndexOf('###ВКОНТАКТЕ###', e);
    const from = (t >= 0 && t < v) ? t : (v >= 0 ? v : 0);
    block = raw.slice(from, e);
  }

  return {
    telegram: between(block, '###TELEGRAM###', '###ВКОНТАКТЕ###'),
    vk: after(block, '###ВКОНТАКТЕ###'),
    recovered: recovered,
  };
}

const p1 = readPost(1);
const p2 = readPost(2);

// --- рилс -------------------------------------------------------------------
const reelsBlock = between(raw, '###РИЛС###', '###КОНЕЦ_РИЛС###');
const rec = {
  hook: between(reelsBlock, '###ХУК###', '###ОСНОВНАЯ_ЧАСТЬ###'),
  body: between(reelsBlock, '###ОСНОВНАЯ_ЧАСТЬ###', '###ФИНАЛ###'),
  ending: between(reelsBlock, '###ФИНАЛ###', '###ВИЗУАЛЬНЫЙ_РЯД###'),
  visual: between(reelsBlock, '###ВИЗУАЛЬНЫЙ_РЯД###', '###КОНЕЦ_РИЛС###'),
};

// --- проверки качества текста ----------------------------------------------
// Корни и словосочетания: ищем подстрокой.
const BANNED_STEMS = [
  'гарантир', 'гарантия', 'гарантируем',
  'только сегодня', 'вы теряете', 'последний шанс',
  'избавит от депрессии', 'медицинск',
  'уникальн', 'инновационн', 'лучший на рынке', 'лучше конкурент',
  'в рамках данного', 'осуществляется предоставление',
];

// Отдельные слова: ищем по границам слова, иначе «срочность» ловится как «срочно»,
// а «лечит» — как часть «лечит» внутри других слов.
const BANNED_WORDS = ['срочно', 'лечит', 'вылечит', 'гарантия', 'депрессия', 'депрессии'];

function bannedHits(text) {
  const low = text.toLowerCase();
  const hits = BANNED_STEMS.filter(function (w) { return low.indexOf(w) >= 0; });
  BANNED_WORDS.forEach(function (w) {
    const re = new RegExp('(^|[^а-яёa-z])' + w + '([^а-яёa-z]|$)', 'i');
    if (re.test(low) && hits.indexOf(w) < 0) hits.push(w);
  });
  return hits;
}

const posts = [
  { slot: 1, data: p1, meta: (parsed.selected || []).filter(function (s) { return s.slot === 1; })[0] || {} },
  { slot: 2, data: p2, meta: (parsed.selected || []).filter(function (s) { return s.slot === 2; })[0] || {} },
];

const content = posts.map(function (p) {
  const tg = p.data.telegram;
  const vk = p.data.vk;
  return {
    slot: p.slot,
    kind: 'post',
    topic: p.meta.topic || '',
    rubric: p.meta.rubric || '',
    task: p.meta.task || '',
    format: p.meta.format || 'пост',
    date: p.meta.date || '',
    weekday: p.meta.weekday || '',
    telegram: tg,
    vk: vk,
    telegram_chars: countChars(tg),
    vk_chars: countChars(vk),
    telegram_limit: 900,
    vk_limit: 1400,
    vk_hashtags: (vk.match(/#[^\s#]+/g) || []),
    vk_has_question: /\?/.test(vk),
    banned: bannedHits(tg + ' ' + vk),
    versions_differ: tg.length > 0 && vk.length > 0 &&
      countChars(tg) !== countChars(vk) &&
      tg.slice(0, 60) !== vk.slice(0, 60),
  };
});

const checks = [];
function check(name, ok, detail) { checks.push({ name: name, ok: !!ok, detail: detail }); }

// Проверяем суть, а не оформление: важно, что ответ разобран на три материала.
// Если модель потеряла открывающий маркер, но текст на месте и блок восстановлен
// по закрывающему маркеру и метке площадки — материал рабочий, это примечание.
const MARKERS = ['###ПОСТ_1###', '###ПОСТ_2###', '###РИЛС###',
  '###КОНЕЦ_ПОСТА_1###', '###КОНЕЦ_ПОСТА_2###', '###КОНЕЦ_РИЛС###'];
const missingMarkers = MARKERS.filter(function (m) { return raw.indexOf(m) < 0; });

check('Ответ модели разобран в три материала: два поста и сценарий рилса',
  content.every(function (c) { return c.telegram.length > 0 && c.vk.length > 0; }) &&
  rec.hook.length > 0 && rec.body.length > 0 && rec.ending.length > 0,
  missingMarkers.length
    ? 'не найдены маркеры: ' + missingMarkers.join(', ') +
      ' — блоки восстановлены по закрывающим маркерам и меткам площадок'
    : 'по маркерам ###ПОСТ_1###, ###ПОСТ_2###, ###РИЛС###');

check('Оба поста разобраны и содержат обе версии',
  content.every(function (c) { return c.telegram.length > 60 && c.vk.length > 60; }),
  content.map(function (c) { return 'пост ' + c.slot + ': Telegram ' + c.telegram_chars + ' симв., ВК ' + c.vk_chars + ' симв.'; }).join('; '));

check('Пост для Telegram укладывается в 900 символов',
  content.every(function (c) { return c.telegram_chars <= c.telegram_limit; }),
  content.map(function (c) { return 'пост ' + c.slot + ': ' + c.telegram_chars; }).join(', '));

check('Пост для ВКонтакте укладывается в 1400 символов',
  content.every(function (c) { return c.vk_chars <= c.vk_limit; }),
  content.map(function (c) { return 'пост ' + c.slot + ': ' + c.vk_chars; }).join(', '));

check('Версии для Telegram и ВКонтакте различаются, а не скопированы',
  content.every(function (c) { return c.versions_differ; }),
  content.map(function (c) { return 'пост ' + c.slot + ': ' + (c.versions_differ ? 'различаются' : 'ПОХОЖИ'); }).join('; '));

check('ВКонтакте: не больше 3 хэштегов и есть вопрос к читателю',
  content.every(function (c) { return c.vk_hashtags.length <= 3 && c.vk_has_question; }),
  content.map(function (c) { return 'пост ' + c.slot + ': хэштегов ' + c.vk_hashtags.length + ', вопрос ' + (c.vk_has_question ? 'есть' : 'НЕТ'); }).join('; '));

check('В Telegram нет хэштегов',
  content.every(function (c) { return !/#[^\s#]+/.test(c.telegram); }),
  content.map(function (c) { return 'пост ' + c.slot + ': ' + ((c.telegram.match(/#[^\s#]+/g) || []).join(' ') || 'чисто'); }).join('; '));

check('Нет запрещённых формулировок',
  content.every(function (c) { return c.banned.length === 0; }),
  content.map(function (c) { return 'пост ' + c.slot + ': ' + (c.banned.join(', ') || 'чисто'); }).join('; '));

check('Сценарий рилса содержит хук, основную часть и финальную мысль',
  rec.hook.length > 10 && rec.body.length > 40 && rec.ending.length > 10,
  'хук ' + countChars(rec.hook) + ' симв., основная часть ' + countChars(rec.body) +
  ' симв., финал ' + countChars(rec.ending) + ' симв.');

check('В рилсе нет запрещённых формулировок',
  bannedHits(rec.hook + ' ' + rec.body + ' ' + rec.ending).length === 0,
  bannedHits(rec.hook + ' ' + rec.body + ' ' + rec.ending).join(', ') || 'чисто');

const reels = {
  kind: 'reels',
  topic: ((parsed.selected || []).filter(function (s) { return s.slot === 3; })[0] || {}).topic || '',
  rubric: ((parsed.selected || []).filter(function (s) { return s.slot === 3; })[0] || {}).rubric || '',
  task: ((parsed.selected || []).filter(function (s) { return s.slot === 3; })[0] || {}).task || '',
  format: 'короткое видео',
  date: ((parsed.selected || []).filter(function (s) { return s.slot === 3; })[0] || {}).date || '',
  weekday: ((parsed.selected || []).filter(function (s) { return s.slot === 3; })[0] || {}).weekday || '',
  hook: rec.hook,
  body: rec.body,
  ending: rec.ending,
  visual: rec.visual,
};

// --- повторная генерация при браке -------------------------------------------
// Модель нестабильна: изредка она всё равно «расплывается» и нарушает лимиты.
// Тогда материалы уходят на перегенерацию — не больше двух попыток, чтобы
// цикл гарантированно завершился.
//
// Счётчик берём из $runIndex: это номер прогона текущего узла, который n8n
// ведёт сам. Через $('Копирайтер (LLM)').all().length считать нельзя — в цикле
// узел отдаёт данные с накоплением, и лимит попыток не срабатывает.
const attempt = $runIndex + 1;
const contentOk = checks.every(function (c) { return c.ok; });
const needRetry = !contentOk && attempt < 2;

const failedNow = checks.filter(function (c) { return !c.ok; })
  .map(function (c) { return '- ' + c.name + ' → ' + c.detail; }).join('\n');

const notice = [
  'ВАЖНО: предыдущая попытка забракована проверкой. Что исправить:',
  failedNow,
  '',
  'Перепиши материалы заново, строго по маркерам и с соблюдением лимитов площадок.',
].join('\n');

const retryTask = needRetry
  ? [parsed.copywriter_task_input || parsed.copywriter_task, '', notice].join('\n')
  : '';

return [{
  json: {
    content: content,
    reels: reels,
    checks: parsed.checks.concat(checks),
    checks_passed: parsed.checks_passed + checks.filter(function (c) { return c.ok; }).length,
    checks_total: parsed.checks_total + checks.length,
    plan: parsed.plan,
    selected: parsed.selected,
    log_insights: parsed.log_insights,
    balance_comment: parsed.balance_comment,
    plan_start: parsed.plan_start,
    plan_end: parsed.plan_end,
    plan_days: parsed.plan_days,
    copywriter_task: parsed.copywriter_task,
    copywriter_task_input: retryTask || parsed.copywriter_task_input || parsed.copywriter_task,
    attempt: attempt,
    need_retry: needRetry,
    content_ok: contentOk,
  },
}];
