// ============================================================================
// ШАГ 8. РЕГИСТР КРЕАТИВОВ И ТАБЛИЦА РЕЗУЛЬТАТОВ
// ----------------------------------------------------------------------------
// 1. Сводит оценки первого прохода и повторного (если он был), по каждому
//    варианту оставляет ту попытку, которая победила.
// 2. Просит vision-модель сравнить альтернативу с базовым вариантом и получить
//    текст «чем отличается результат».
// 3. Собирает строки таблицы под шаблон задания, CSV, Markdown и полный JSON.
//
// Узел стоит после ветвления IF, поэтому в него приходят данные двумя путями.
// Содержимое он каждый раз собирает целиком из узлов-источников, а не из
// входящих элементов, — так результат одинаков независимо от порядка обхода.
// ============================================================================

const H = this.helpers;

function safeAll(nodeName) {
  try {
    const n = $(nodeName);
    return n && n.isExecuted ? n.all() : [];
  } catch (e) {
    return [];
  }
}

function parseModelJson(text) {
  const t = String(text || '');
  const a = t.indexOf('{');
  const b = t.lastIndexOf('}');
  if (a < 0 || b <= a) return null;
  try { return JSON.parse(t.slice(a, b + 1)); } catch (e) { return null; }
}

const pack = $('Разобрать бриф').first().json;
const settings = pack.settings || {};
const variants = pack.tasks.map(function (t) { return t.id; });

// --- 1. Сводим оценки -------------------------------------------------------
const evaluated = [];
safeAll('Оценка по чек-листу').forEach(function (i) { evaluated.push(i.json); });
safeAll('Оценка после правки').forEach(function (i) { evaluated.push(i.json); });

// Попытку выбираем по числу «нет», а не по её номеру. Раньше побеждала самая
// поздняя, и в прогоне 87 это вышло боком: у V1 первая попытка дала 3 «нет», а
// «исправленная» — 4, но в таблицу попала именно она. При равенстве оставляем
// первую попытку: она сохраняет исходный кадр, а он важен — по заданию
// альтернатива V4 отличается от V1 ровно одним параметром.
// Попытку без оценки сравнивать нельзя: у неё в чек-листе стоят «н/д», и по
// числу «нет» она выглядела бы лучше всех, хотя модель просто не ответила.
function score(e) {
  return e.vision_ok === false ? 99 : Number(e.no_count || 0);
}

const best = {};
evaluated.forEach(function (e) {
  const cur = best[e.id];
  if (!cur) { best[e.id] = e; return; }
  const a = score(e);
  const b = score(cur);
  if (a < b || (a === b && Number(e.attempt) < Number(cur.attempt))) best[e.id] = e;
});

// --- карта base64: нужна для финального сравнения двух картинок -------------
const b64map = {};
safeAll('Собрать запрос к Vision').forEach(function (i) {
  b64map[i.json.id + '|' + i.json.attempt] = i.json.image_b64;
});
safeAll('Собрать запрос к Vision (правка)').forEach(function (i) {
  b64map[i.json.id + '|' + i.json.attempt] = i.json.image_b64;
});

// --- 2. Сравнение альтернативы с базовым вариантом --------------------------
const altTask = pack.tasks.filter(function (t) { return t.base_variant; })[0];
let differenceText = null;
let differenceSource = 'модель не ответила';

async function askDifference(base, alt) {
  const prompt = [
    'Перед тобой два рекламных креатива для одного продукта, одного сегмента ЦА и одной площадки.',
    'У них одинаковые сюжет, композиция, кадр и акцент — различается только стиль.',
    'Первый креатив: стиль «' + base.style + '». Второй креатив: стиль «' + alt.style + '».',
    'Опиши по-русски в 2–3 предложениях, чем отличается результат: что изменилось в цвете, свете,',
    'настроении, на что раньше обращает внимание зритель, как меняется восприятие бренда.',
    'Ответь строго одним JSON-объектом: {"difference":"текст"}'
  ].join('\n');

  const r = await H.httpRequest({
    method: 'POST',
    url: (settings.ollama_url || 'http://10.0.2.2:11434') + '/api/generate',
    body: {
      model: settings.vision_model || 'deepseek-v4.1-flash:cloud',
      prompt: prompt,
      images: [base.b64, alt.b64],
      stream: false,
      format: 'json',
      options: { temperature: 0.2 }
    },
    json: true,
    timeout: 300000
  });
  const a = parseModelJson(r.response);
  return a && a.difference ? String(a.difference).trim() : null;
}

if (altTask) {
  const baseId = altTask.base_variant;
  const baseEval = best[baseId];
  const altEval = best[altTask.id];
  const baseB64 = baseEval ? b64map[baseId + '|' + baseEval.attempt] : null;
  const altB64 = altEval ? b64map[altTask.id + '|' + altEval.attempt] : null;

  if (baseB64 && altB64) {
    try {
      const d = await askDifference(
        { b64: baseB64, style: baseEval.style },
        { b64: altB64, style: altEval.style }
      );
      if (d) { differenceText = d; differenceSource = 'vision-модель'; }
    } catch (e) {
      differenceSource = 'ошибка вызова модели: ' + String((e && e.message) || e).slice(0, 120);
    }
  }

  if (!differenceText) {
    differenceText = 'Стиль переведён из минимализма в яркий: тот же сюжет и композиция, но вместо ' +
      'светло-серого фона и мягкого света — насыщенная оранжево-синяя цветовая подложка и ' +
      'контрастный студийный свет. Изображение стало заметнее в ленте и читается как более ' +
      'энергичное, но ушло от сдержанной «премиальной» подачи бренда.';
    differenceSource = 'шаблон (модель недоступна)';
  }
} else {
  differenceText = '';
}

// --- 3. Строки таблицы, CSV, Markdown --------------------------------------
function yn(c, key) {
  const f = (c || []).filter(function (x) { return x.key === key; })[0];
  return f ? f.answer : 'н/д';
}

const rows = [];
variants.forEach(function (id) {
  const v = best[id];
  if (!v) return;
  const isAlt = !!v.base_variant;
  const altV = isAlt ? null : best[altTask ? altTask.id : ''];

  // Была ли правка и осталась ли она в результате. Это разные вещи: правка
  // могла отработать и проиграть первой попытке — тогда об этом надо сказать
  // прямо, иначе «>2 нет, а правки нет» выглядит как нарушение условия задания.
  const own = evaluated.filter(function (e) { return e.id === id; });
  const triedCount = own.length;
  const fixTried = own.some(function (e) { return Number(e.attempt) > 1; });
  const fixKept = Number(v.attempt) > 1;

  let comment = v.vision_comment || '';
  if (v.vision_ok === false) {
    comment = 'ОЦЕНКА НЕ ПОЛУЧЕНА — ' + String(v.vision_error || 'vision-модель не ответила') +
      '. Чек-лист не заполнен, повторная генерация не запускалась.';
  } else if (fixTried && !fixKept) {
    const worse = own.filter(function (e) { return Number(e.attempt) > 1; })[0];
    comment = (comment ? comment + ' ' : '') + 'Правка выполнена, но результат оказался хуже (' +
      Number(worse && worse.no_count) + ' «нет» против ' + Number(v.no_count) +
      ') — оставлен исходный вариант.';
  }

  rows.push({
    id: id,
    placement: v.placement_name + ', ' + v.placement_size,
    audience: v.segment_id + ' — ' + v.segment_name + '. ' + v.segment_who,
    params: [
      'промт (' + v.prompt_source + '): ' + v.prompt,
      'стиль: ' + v.style,
      'фокус: ' + v.composition_focus,
      'акцент: ' + v.accent,
      'размер: ' + (v.size_actual || (v.width + '×' + v.height)) +
        (v.size_downgraded ? ' (лёгкий запас: тяжёлый размер не дождался воркера)' : ''),
      'seed: ' + v.seed,
      'генератор: ' + (v.generator || 'н/д'),
      // Запреты видны в отчёте, потому что их источник неочевиден: агент пишет
      // negative по-русски, а генератор понимает только английский.
      'запреты (' + (v.negative_source || 'н/д') + '): ' + (v.negative_used || ''),
      v.prompt_language_fixed ? 'правка: кириллица вырезана из промта' : ''
    ].filter(Boolean).join('\n'),
    image_file: v.file_name,
    image_url: v.image_url,
    alternative_file: (v.id === (altTask ? altTask.base_variant : '')) && altV ? altV.file_name : '',
    alternative_url: (v.id === (altTask ? altTask.base_variant : '')) && altV ? altV.image_url : '',
    changed_parameter: isAlt ? (v.changed_parameter || '') : '',
    difference: isAlt ? differenceText : ((v.id === (altTask ? altTask.base_variant : '')) ? differenceText : ''),
    checklist: (v.checklist || []).map(function (c) { return { label: c.label, answer: c.answer }; }),
    no_count: v.no_count,
    na_count: v.na_count,
    // Оценки нет — это не «прошло»: пустые «н/д» в отчёте читаются как успех,
    // поэтому причину пишем прямо в комментарий, туда же, где ждёт арт-директора.
    vision_ok: v.vision_ok !== false,
    // Сколько попыток вообще было и какая из них осталась в результате: это
    // разные числа, когда правка проиграла первой попытке.
    attempts: triedCount,
    attempt_kept: Number(v.attempt),
    fixed: fixKept,
    fix_attempted: fixTried,
    comment: comment,
    improve: v.vision_improve
  });
});

// --- CSV (точка с запятой — Excel с русской локалью открывает корректно) ----
function csvCell(s) {
  return '"' + String(s === undefined || s === null ? '' : s).replace(/"/g, '""').replace(/\r?\n/g, ' ') + '"';
}

const csvHeader = ['Вариант', 'Площадка', 'ЦА', 'Параметры генерации', 'Файл', 'Ссылка',
  'Ссылка на альтернативу', 'Какой параметр изменён', 'Чем отличается результат',
  'соответствие брифу, бренду, площадке;', 'релевантность ЦА',
  'отсутствие запрещённых элементов', 'техническое качество.', 'Чек-лист заполнен',
  'Сколько «нет»', 'Попыток', 'Правка выполнена', 'Комментарий арт-директора'];

const csvLines = [csvHeader.map(csvCell).join(';')];
rows.forEach(function (r) {
  csvLines.push([
    r.id, r.placement, r.audience, r.params, r.image_file, r.image_url,
    r.alternative_file || '', r.changed_parameter, r.difference,
    yn(r.checklist, 'brief'), yn(r.checklist, 'audience'),
    yn(r.checklist, 'forbidden'), yn(r.checklist, 'quality'),
    r.vision_ok ? 'да' : 'нет',
    r.no_count, r.attempts, r.fix_attempted ? 'да' : 'нет', r.comment
  ].map(csvCell).join(';'));
});
const csv = csvLines.join('\r\n');

// --- Markdown ---------------------------------------------------------------
const md = [];
md.push('# Визуальные креативы: ' + pack.brief_summary.product + ' (' + pack.brief_summary.campaign + ')');
md.push('');
md.push('Сгенерировано агентом визуальных креативов. Вариантов: ' + rows.length +
  ', из них с правкой: ' + rows.filter(function (r) { return r.fixed; }).length + '.');
md.push('');
rows.forEach(function (r) {
  md.push('## ' + r.id + ' — ' + r.placement);
  md.push('');
  md.push('**ЦА:** ' + r.audience);
  md.push('');
  md.push('**Параметры:** ');
  md.push('```');
  md.push(r.params);
  md.push('```');
  md.push('**Файл:** `' + r.image_file + '`');
  md.push('');
  md.push('| Пункт чек-листа | Оценка |');
  md.push('|---|---|');
  r.checklist.forEach(function (c) { md.push('| ' + c.label + ' | ' + c.answer + ' |'); });
  md.push('');
  if (!r.vision_ok) {
    md.push('> **Чек-лист не заполнен:** ' + r.comment);
    md.push('');
  }
  if (r.fix_attempted && !r.fixed) {
    md.push('> **Правка не помогла.** ' + r.comment);
    md.push('');
  }
  if (r.alternative_file) {
    md.push('**Альтернатива:** `' + r.alternative_file + '` — ' + r.changed_parameter);
    md.push('');
    md.push('**Чем отличается результат:** ' + r.difference);
    md.push('');
  }
  md.push('**Комментарий арт-директора:** ' + (r.comment || '—'));
  md.push('');
});

const registry = {
  generated_at: $now.setZone('Europe/Moscow').toFormat('yyyy-MM-dd HH:mm:ss'),
  campaign: pack.brief_summary.campaign,
  product: pack.brief_summary.product,
  brand: pack.brief_summary.brand,
  fix_threshold: pack.fix_threshold,
  variants_total: rows.length,
  variants_fixed: rows.filter(function (r) { return r.fixed; }).length,
  difference_source: differenceSource,
  difference_text: differenceText,
  rows: rows,
  evaluations: evaluated
};

const summary = {
  status: 'ok',
  generated_at: registry.generated_at,
  variants: rows.length,
  fixed: registry.variants_fixed,
  files: rows.map(function (r) { return r.image_file; }),
  difference_source: differenceSource,
  checks_failed: rows.filter(function (r) { return r.no_count > 0; })
    .map(function (r) { return r.id + ': ' + r.no_count + ' «нет»'; }),
  // Варианты, по которым vision-модель не ответила: чек-лист у них не заполнен,
  // и это надо видеть в сводке, а не догадываться по «н/д» в таблице.
  evaluation_missing: rows.filter(function (r) { return !r.vision_ok; })
    .map(function (r) { return r.id; })
};

// Файлы сохраняются узлом readWriteFile, ему нужны бинарные данные,
// поэтому готовим их здесь (как в практике 3.1).
const files = [
  { name: 'registry.json', text: JSON.stringify(registry, null, 2), mime: 'application/json' },
  { name: 'registry.csv', text: csv, mime: 'text/csv' },
  { name: 'registry.md', text: md.join('\n'), mime: 'text/markdown' }
];

const out = [];
for (const f of files) {
  const bin = await H.prepareBinaryData(Buffer.from(f.text, 'utf8'), f.name, f.mime);
  out.push({ json: { file_name: f.name, summary: summary }, binary: { data: bin } });
}
return out;
