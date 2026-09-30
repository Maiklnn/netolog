// ============================================================================
// ШАГ 5. ОЧИСТКА ОТВЕТА LLM И ФОРМИРОВАНИЕ ИТОГОВОГО БРИФИНГА
// ----------------------------------------------------------------------------
// Используемая модель (deepseek-v4.1-flash:cloud) — «рассуждающая»: вместе с
// брифингом она возвращает цепочку размышлений на английском, причём в самих
// рассуждениях часто повторяется план с теми же заголовками разделов.
// Поэтому надёжный признак готового брифинга — не маркер, а ПОЛНЫЙ набор из
// шести разделов, идущих по порядку. Берём самый поздний такой фрагмент:
// рассуждения всегда идут раньше финального ответа.
// ============================================================================

const src = $input.first().json;
const raw = String(
  (src.message && src.message.content) ? src.message.content :
  (src.content || src.text || src.output || '')
).replace(/\r\n/g, '\n');

// Ключевые слова обязательных разделов — в том порядке, в котором они должны идти.
const SEC_KEYWORDS = [/контекст/i, /тренд/i, /паттерн/i, /уязвим/i, /гипотез/i, /что делать/i];

// Ищем заголовки разделов ПО ВСЕМУ тексту, а не по началам строк: модель иногда
// приклеивает заголовок к служебной фразе и он оказывается не в начале строки —
// например «I'll write concisely but completely.### 1. Контекст анализа».
// Такой заголовок старый экстрактор не видел и возвращал вместо брифинга план.
function findHeads(t) {
  const re = /(#{1,6})[ \t]*([1-6])\.[ \t]*([^\n]*)/g;
  const heads = [];
  let m;
  while ((m = re.exec(t)) !== null) {
    const sec = parseInt(m[2], 10) - 1;
    if (sec < 0 || sec > 5) continue;
    if (!SEC_KEYWORDS[sec].test(m[3])) continue;   // «1. Что-то другое» не считаем
    heads.push({ sec: sec, start: m.index });
  }
  return heads;
}

// Тело раздела-заглушки: «...», «перечислить.», «list.», «3-5 действий.» —
// так модель размечает план перед тем, как писать сам брифинг.
function looksLikeStub(s) {
  return s.replace(/[.\-—–…\s]/g, '').length < 30;
}

// --- 1. Отрезаем служебные рассуждения модели ---
function extractBriefing(t) {
  const lines = t.split('\n');
  const heads = findHeads(t);

  // Основной способ: последний фрагмент, где все шесть разделов идут по порядку,
  // и при этом каждый раздел наполнен текстом, а не заглушкой.
  const starts = heads.filter(h => h.sec === 0);
  for (let k = starts.length - 1; k >= 0; k--) {
    const chain = [starts[k]];
    let ok = true;
    for (let s = 1; s < 6; s++) {
      const next = heads.find(h => h.sec === s && h.start > chain[chain.length - 1].start);
      if (!next) { ok = false; break; }
      chain.push(next);
    }
    if (!ok) continue;

    // Проверяем, что все шесть разделов действительно написаны.
    let stubbed = false;
    for (let i = 0; i < 6; i++) {
      const bodyStart = t.indexOf('\n', chain[i].start);
      const from = bodyStart < 0 ? t.length : bodyStart + 1;
      const to = i < 5 ? chain[i + 1].start : t.length;
      if (looksLikeStub(t.slice(from, to))) { stubbed = true; break; }
    }
    if (stubbed) continue;

    // Модель нередко печатает ответ дважды. Конец брифинга — начало ПОВТОРНОГО
    // раздела 1, то есть следующий заголовок первого раздела после шестого.
    const restart = heads.find(h => h.sec === 0 && h.start > chain[5].start);
    const end = restart ? restart.start : t.length;

    const body = t.slice(chain[0].start, end).trim();
    if (body.length >= 800) return body;
  }

  // Запасной способ 1: всё после последнего маркера «###».
  const marker = t.lastIndexOf('###');
  if (marker >= 0) return t.slice(marker).replace(/^#+\s*/, '').trim();

  // Запасной способ 2: первый заголовок Markdown с кириллицей.
  let head = -1;
  for (let i = 0; i < lines.length; i++) {
    if (/^#{1,3}\s+\S/.test(lines[i]) && /[а-яё]/i.test(lines[i])) { head = i; break; }
  }
  if (head >= 0) return lines.slice(head).join('\n').trim();

  // Запасной способ 3: отбрасываем ведущие англоязычные абзацы.
  const out = [];
  let started = false;
  for (const l of lines) {
    const latin = (l.match(/[A-Za-z]/g) || []).length;
    const cyr = (l.match(/[А-Яа-яЁё]/g) || []).length;
    if (!started && latin > 20 && cyr < 5) continue;
    if (l.trim()) started = true;
    out.push(l);
  }
  return out.join('\n').trim();
}

let briefing = extractBriefing(raw);

// --- 2. Финальная чистка: маркеры списка-заглушек и хвостовые служебные строки ---
briefing = briefing
  .replace(/\n{3,}/g, '\n\n')
  .replace(/^\s*(###\s*)?(Вот|Here is|Below is)[^\n]*\n/i, '')
  .trim();

// --- 3. Подставляем фактические метаданные прогона ---
const counts = $('Фильтрация и группировка').first().json.counts;
const ctxStats = $('Фильтрация и группировка').first().json.context.stats;

const header =
  '# Аналитический брифинг: онлайн-школы английского языка\n\n' +
  '_Сформирован ИИ-агентом рыночной аналитики. ' +
  'Дата прогона: ' + $now.setZone('Europe/Moscow').toFormat('yyyy-MM-dd HH:mm') + ' (МСК)._\n\n' +
  '_Объект анализа: ' + $('Фильтрация и группировка').first().json.context.object + '._\n' +
  '_Конкуренты: ' + $('Фильтрация и группировка').first().json.context.competitors.join(', ') + '._\n' +
  '_Период данных: ' + ctxStats.date_range + '._\n' +
  '_Обработано: тарифных позиций — ' + counts.tariffs + ', отзывов — ' + counts.reviews + '._\n' +
  '_Прошло фильтр шума: сигналов-наблюдений — ' + counts.observations +
  ', гипотез — ' + counts.hypotheses + ', исключено единичных — ' + counts.noise_excluded + '._\n\n---\n\n';

const briefingMd = header + briefing;

if (!briefing || briefing.length < 300) {
  throw new Error('Брифинг пуст или слишком короткий (' + (briefing || '').length +
                  ' символов). Проверьте ответ LLM.');
}

// Предохранитель: если в извлечённом тексте нет всех шести разделов, значит
// за брифинг принят план или черновик. Лучше упасть с внятной ошибкой, чем
// отдать команде заглушку с «...» вместо анализа.
const foundSecs = findHeads(briefing).map(h => h.sec);
const lackSecs = [0, 1, 2, 3, 4, 5].filter(n => foundSecs.indexOf(n) < 0);
if (lackSecs.length) {
  throw new Error('В извлечённом брифинге нет разделов: ' +
    lackSecs.map(n => n + 1).join(', ') +
    '. Похоже, за брифинг принят план или черновик ответа модели.');
}

return [{
  json: {
    briefing_md: briefingMd,
    briefing_chars: briefingMd.length,
    generated_at: $now.setZone('Europe/Moscow').toFormat('yyyy-MM-dd HH:mm'),
    run_date: $now.setZone('Europe/Moscow').toFormat('yyyy-MM-dd'),
    counts: counts,
    raw_llm_chars: raw.length,
    reasoning_stripped: raw.length - briefing.length
  }
}];
