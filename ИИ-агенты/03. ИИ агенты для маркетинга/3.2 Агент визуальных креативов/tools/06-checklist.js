// ============================================================================
// ШАГ 6. ОЦЕНКА ПО ЧЕК-ЛИСТУ
// ----------------------------------------------------------------------------
// Разбирает ответ vision-модели и превращает его в четыре пункта чек-листа —
// ровно те, что стоят в шаблоне задания:
//   • соответствие брифу, бренду, площадке;
//   • релевантность ЦА;
//   • отсутствие запрещённых элементов;
//   • техническое качество.
//
// Метаданные варианта берём из узла __SRC__: узел HTTP Request с ответом Ollama
// подменяет json целиком, поэтому «своих» полей в текущем элементе уже нет.
//
// Здесь же решается, нужна ли правка: по условию задания креатив уходит на
// повторную генерацию, только если ответов «нет» БОЛЬШЕ ДВУХ (то есть 3 или 4).
// ============================================================================

const SRC = $('__SRC__').all();
const items = $input.all();
const MAX_ATTEMPT = 2;

const CHECK = [
  { key: 'brief', label: 'соответствие брифу, бренду, площадке;' },
  { key: 'audience', label: 'релевантность ЦА' },
  { key: 'forbidden', label: 'отсутствие запрещённых элементов' },
  { key: 'quality', label: 'техническое качество.' }
];

function yesNo(value) {
  if (typeof value === 'boolean') return value ? 'да' : 'нет';
  const s = String(value === undefined || value === null ? '' : value).trim().toLowerCase();
  if (!s) return 'нет';
  if (/^(да|yes|true|1|ok|ок)/.test(s)) return 'да';
  return 'нет';
}

function parseModelJson(text) {
  const t = String(text || '');
  const a = t.indexOf('{');
  const b = t.lastIndexOf('}');
  if (a < 0 || b <= a) return null;
  try {
    return JSON.parse(t.slice(a, b + 1));
  } catch (e) {
    return null;
  }
}

const out = [];

for (let i = 0; i < items.length; i++) {
  const meta = (SRC[i] && SRC[i].json) ? SRC[i].json : {};
  const st = meta.settings || {};
  const threshold = (st.fix_threshold === undefined) ? 2 : Number(st.fix_threshold);
  const attempt = Number(meta.attempt || 1);

  const answer = parseModelJson(items[i].json.response);
  const visionError = items[i].json.error || null;

  const checklist = CHECK.map(function (c) {
    return {
      key: c.key,
      label: c.label,
      answer: answer ? yesNo(answer[c.key]) : 'н/д'
    };
  });

  const noCount = checklist.filter(function (c) { return c.answer === 'нет'; }).length;
  const naCount = checklist.filter(function (c) { return c.answer === 'н/д'; }).length;

  // Правка нужна, только если чек-лист реально заполнен, «нет» больше порога
  // и попытки ещё остались.
  const needsFix = !!answer && noCount > threshold && attempt < MAX_ATTEMPT;

  out.push({
    json: Object.assign({}, meta, {
      attempt: attempt,
      checklist: checklist,
      no_count: noCount,
      na_count: naCount,
      fix_threshold: threshold,
      needs_fix: needsFix,
      max_attempt: MAX_ATTEMPT,
      vision_ok: !!answer,
      vision_error: answer ? null : String(visionError || 'модель не вернула разбираемый JSON').slice(0, 200),
      vision_comment: answer ? String(answer.comment || '').trim() : '',
      vision_improve: answer ? String(answer.improve || '').trim() : '',
      vision_raw: answer ? null : String(items[i].json.response || '').slice(0, 400),
      vision_error_dump: answer ? null : JSON.stringify(items[i].json).slice(0, 1500),
      evaluated_at: $now.setZone('Europe/Moscow').toFormat('yyyy-MM-dd HH:mm:ss')
    })
  });
}

return out;
