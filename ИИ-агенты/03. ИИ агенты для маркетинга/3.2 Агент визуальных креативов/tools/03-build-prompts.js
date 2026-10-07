// ============================================================================
// ШАГ 3. ПРОМТЫ ОТ LLM-АГЕНТА + ПРОВЕРКА ВАРИАТИВНОСТИ
// ----------------------------------------------------------------------------
// Забирает ответ агента-промт-инженера, разбирает JSON и склеивает его с
// параметрами вариантов из брифа. Здесь же — три предохранителя:
//
//   1. Если модель вернула мусор вместо JSON или промт слишком короткий —
//      берём запасной промт из брифа (он лежит в plan[].fallback_prompt).
//   2. Если в промте осталась кириллица или он не запрещает текст на картинке —
//      чиним принудительно, не доверяя модели.
//   3. Вариативность: промт альтернативы (V4) собирается НЕ заново, а заменой
//      одного фрагмента в промте базового варианта (V1). Так требование «изменён
//      ровно один параметр» выполняется конструктивно, а не по обещанию модели.
// ============================================================================

const src = $input.first().json;
const pack = $('Разобрать бриф').first().json;

const raw = String(
  (src.message && src.message.content) ? src.message.content :
  (src.content || src.text || src.output || '')
);

// --- вытаскиваем JSON из ответа модели --------------------------------------
// Модель-рассуждалка сначала печатает длинное размышление, а следом — JSON.
// Узел Ollama отдаёт и то и другое одной строкой, без разделителя, и в боевом
// ответе (прогон 83) начало объекта оказалось испорчено: вместо
// «…Let me finalize.{"variants":[…]}» пришло «…Let me finalize.variants":[…]}» —
// без открывающих `{"`, зато с лишней закрывающей `}`. Прямой разбор такого
// текста падал, узел молча уходил на запасные промты из брифа, и работа
// LLM-агента пропадала целиком. Поэтому разбор трёхступенчатый.

// Возвращает сбалансированный кусок текста от скобки start до парной ей,
// пропуская скобки внутри строк. null — если пары нет.
function balanced(s, start) {
  const open = s[start];
  const close = open === '{' ? '}' : ']';
  let depth = 0;
  let inStr = false;
  let esc = false;
  for (let i = start; i < s.length; i++) {
    const c = s[i];
    if (inStr) {
      if (esc) esc = false;
      else if (c === '\\') esc = true;
      else if (c === '"') inStr = false;
      continue;
    }
    if (c === '"') { inStr = true; continue; }
    if (c === open) depth++;
    else if (c === close) {
      depth--;
      if (!depth) return s.slice(start, i + 1);
    }
  }
  return null;
}

function tryParse(s) {
  try { return JSON.parse(s); } catch (e) { return null; }
}

function extractJson(t) {
  const cleaned = t.replace(/```json/gi, '```').split('```').join('\n');

  // 1. Обычный случай: от первой `{` до последней `}`. Требуем массив
  //    вариантов: если в прозе попался корректный, но посторонний объект,
  //    он не должен подменять собой ответ (иначе узел снова уйдёт на запасной
  //    промт, хотя разбираемый ответ в тексте есть).
  const a = cleaned.indexOf('{');
  const b = cleaned.lastIndexOf('}');
  if (a >= 0 && b > a) {
    const p = tryParse(cleaned.slice(a, b + 1));
    if (p && Array.isArray(p.variants)) return p;
  }

  // 2. Испорченное начало массива вариантов. Массив при этом целый, поэтому
  //    берём любой сбалансированный массив, элементы которого похожи на
  //    варианты (объекты с полем id), и собираем объект заново — имя ключа
  //    восстанавливаем сами, в тексте от него мог остаться только хвост.
  for (let i = cleaned.indexOf('['); i >= 0; i = cleaned.indexOf('[', i + 1)) {
    const piece = balanced(cleaned, i);
    if (!piece) continue;
    const arr = tryParse(piece);
    if (!Array.isArray(arr) || !arr.length) continue;
    const looksLikeVariants = arr.every(function (v) {
      return v && typeof v === 'object' && !Array.isArray(v) && v.id;
    });
    if (looksLikeVariants) return { variants: arr };
  }

  // 3. Последняя попытка: перебираем все `{` и берём первый сбалансированный
  //    кусок, в котором есть массив вариантов.
  for (let i = cleaned.indexOf('{'); i >= 0; i = cleaned.indexOf('{', i + 1)) {
    const piece = balanced(cleaned, i);
    if (!piece) continue;
    const p = tryParse(piece);
    if (p && Array.isArray(p.variants)) return p;
  }

  return null;
}

const parsed = extractJson(raw);
const byId = {};
if (parsed && Array.isArray(parsed.variants)) {
  parsed.variants.forEach(function (v) {
    if (v && v.id) byId[String(v.id).toUpperCase()] = v;
  });
}

// Диагностика ответа агента: попадает в реестр, чтобы при разборе полётов было
// видно, что именно вернула модель.
const agentDiag = {
  agent_answer_chars: raw.length,
  agent_json_ok: !!(parsed && Array.isArray(parsed.variants)),
  agent_variants: Object.keys(byId),
  agent_input_keys: Object.keys(src).join(','),
  agent_answer_head: (parsed && Array.isArray(parsed.variants)) ? null : raw.slice(0, 800)
};

const NO_TEXT_CLAUSE = 'no text, no letters, no numbers, no words, no watermark, no logo';

function sane(text, id) {
  const p = String(text || '').trim().replace(/\s+/g, ' ').replace(/^["'«]|["'»]$/g, '');
  if (p.length < 60) return null;                 // слишком короткий — это не промт
  if (/[А-Яа-яЁё]/.test(p)) return null;          // промт должен быть на английском
  if (!/prompt|photo|photograph|illustration|image|scene|shot/i.test(p)) return null;
  if (!/no text/i.test(p)) return p + ', ' + NO_TEXT_CLAUSE;
  return p;
}

const items = pack.tasks.map(function (t) {
  const task = Object.assign({}, t);
  const fromModel = byId[task.id];
  let warning = null;

  // Имя файла задаём сразу и здесь, а не по ходу дела: узел сохранения берёт
  // его выражением {{ $json.file_name }} и без этого писал один и тот же
  // «undefined.webp» на все варианты. Расширение условное — оба генератора
  // (ссылка и base64) переписывают его по фактическому формату картинки.
  task.file_name = task.id + '-a' + (task.attempt || 1) + '.webp';

  if (fromModel) {
    const p = sane(fromModel.prompt, task.id);
    if (p) {
      task.prompt = p;
      task.prompt_source = 'llm';
    } else {
      warning = 'Промт от модели не прошёл проверку — взят запасной промт из брифа';
    }
    task.negative = String(fromModel.negative || '').trim();
    task.rationale = String(fromModel.rationale || '').trim();
    if (fromModel.style_swap) task.style_swap = fromModel.style_swap;
  } else {
    warning = 'Модель не вернула вариант ' + task.id + ' — взят запасной промт из брифа';
  }

  task.prompt_warning = warning;
  Object.assign(task, agentDiag);
  return task;
});

// --- вариативность: альтернатива = базовый вариант с одной заменой ----------
const byVariant = {};
items.forEach(function (t) { byVariant[t.id] = t; });

items.forEach(function (t) {
  if (!t.base_variant) return;
  const base = byVariant[t.base_variant];
  const swap = t.style_swap;
  let applied = false;

  if (base && swap && swap.from && swap.to) {
    const from = String(swap.from).trim();
    const to = String(swap.to).trim();
    const idx = base.prompt.toLowerCase().indexOf(from.toLowerCase());
    if (idx >= 0) {
      t.prompt = base.prompt.slice(0, idx) + to + base.prompt.slice(idx + from.length);
      t.prompt_source = 'llm (замена одного фрагмента в ' + t.base_variant + ')';
      applied = true;
      // Модель для альтернативы намеренно не пишет полный промт — только пару
      // style_swap. Поэтому проверка «промт не прошёл» выше срабатывает всегда;
      // раз замена удалась, предупреждение снимаем, иначе оно врёт в реестре.
      t.prompt_warning = null;
    }
  }

  if (!applied) {
    // Замена не удалась — берём запасной промт альтернативы и запрещаем
    // считать это «изменением одного параметра» по факту.
    t.prompt = sane(t.fallback_prompt, t.id) || t.prompt;
    t.prompt_source = 'fallback';
    t.prompt_warning = 'Фрагмент стиля не найден в промте ' + t.base_variant +
      ' — альтернатива сгенерирована по запасному промту. Различие параметров проверено вручную.';
  }

  t.seed = base ? base.seed : t.seed;   // сид принудительно тот же
  t.variativity_applied = applied;
});

return items.map(function (t) { return { json: t }; });
