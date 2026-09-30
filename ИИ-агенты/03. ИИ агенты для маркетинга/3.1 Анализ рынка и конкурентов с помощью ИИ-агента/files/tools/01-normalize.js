// ============================================================================
// ШАГ 2. ПОДГОТОВКА ДАННЫХ — очистка, нормализация, объединение в один контекст
// ----------------------------------------------------------------------------
// На входе три разнородных источника:
//   1) Тарифы конкурентов  — CSV, собранный вручную с сайтов школ (первичный)
//   2) Отзывы пользователей — CSV с открытых площадок (поведенческий)
//   3) Обзор рынка          — текстовая выгрузка профильных материалов (вторичный)
//
// На выходе — один нормализованный JSON-контекст: единые названия школ, единая
// дата в формате YYYY-MM, единый список категорий, дедупликация и чистка текста.
// ============================================================================

const tariffsRaw = String($('1. Тарифы (текст)').first().json.data || '');
const reviewsRaw = String($('2. Отзывы (текст)').first().json.data || '');
const marketRaw  = String($('3. Обзор рынка (текст)').first().json.data || '');

// --- 1. Разбор CSV (с учётом кавычек и переводов строк внутри поля) ---
function parseCSV(text) {
  const rows = [];
  let row = [], field = '', inQ = false;
  const s = String(text).replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (inQ) {
      if (c === '"') {
        if (s[i + 1] === '"') { field += '"'; i++; } else { inQ = false; }
      } else field += c;
    } else if (c === '"') {
      inQ = true;
    } else if (c === ',') {
      row.push(field); field = '';
    } else if (c === '\n') {
      row.push(field); rows.push(row); row = []; field = '';
    } else {
      field += c;
    }
  }
  if (field.length || row.length) { row.push(field); rows.push(row); }
  const head = (rows.shift() || []).map(h => h.trim());
  return rows
    .filter(r => r.some(v => String(v).trim() !== ''))
    .map(r => {
      const o = {};
      head.forEach((h, i) => { o[h] = (r[i] === undefined ? '' : String(r[i])).trim(); });
      return o;
    });
}

// --- 2. Чистка текста: лишние пробелы, переводы строк, кавычки ---
function clean(v) {
  return String(v == null ? '' : v)
    .replace(/\s+/g, ' ')
    .replace(/^["'«»\s]+|["'«»\s]+$/g, '')
    .trim();
}

// --- 3. Единые названия школ (нормализация сущности) ---
const SCHOOLS = {
  'skyeng': 'Skyeng', 'скиенг': 'Skyeng', 'скайенг': 'Skyeng', 'скай инглиш': 'Skyeng',
  'инглекс': 'Инглекс', 'englex': 'Инглекс',
  'englishdom': 'EnglishDom', 'инглишдом': 'EnglishDom', 'инглиш дом': 'EnglishDom'
};
function normSchool(v) {
  const k = clean(v).toLowerCase().replace(/[()«»"]/g, '').replace(/\s+/g, ' ');
  if (SCHOOLS[k]) return SCHOOLS[k];
  const hit = Object.keys(SCHOOLS).find(a => k.includes(a));
  return hit ? SCHOOLS[hit] : clean(v);
}

// --- 4. Единый формат даты: DD.MM.YYYY | YYYY-MM-DD | «март 2025» -> YYYY-MM ---
const MONTHS = {
  'январ': '01', 'феврал': '02', 'март': '03', 'апрел': '04', 'ма': '05',
  'июн': '06', 'июл': '07', 'август': '08', 'сентябр': '09', 'октябр': '10',
  'ноябр': '11', 'декабр': '12'
};
function normDate(v) {
  const s = clean(v);
  let m = s.match(/(\d{4})-(\d{2})-(\d{2})/);                 // 2025-03-12
  if (m) return m[1] + '-' + m[2];
  m = s.match(/(\d{1,2})[.\/](\d{1,2})[.\/](\d{4})/);          // 12.03.2025
  if (m) return m[3] + '-' + m[2].padStart(2, '0');
  m = s.match(/(\d{1,2})\s+([а-яё]+)\s+(\d{4})/i);             // 12 марта 2025
  if (m) {
    const key = Object.keys(MONTHS).find(k => m[2].toLowerCase().startsWith(k));
    if (key) return m[3] + '-' + MONTHS[key];
  }
  m = s.match(/([а-яё]+)\s+(\d{4})/i);                         // март 2025
  if (m) {
    const key = Object.keys(MONTHS).find(k => m[1].toLowerCase().startsWith(k));
    if (key) return m[2] + '-' + MONTHS[key];
  }
  m = s.match(/(\d{4})/);                                      // только год
  if (m) return m[1];
  return 'дата не указана';
}

// --- 5. Единый список категорий: любой текст -> одна каноническая категория ---
// Сначала пытаемся распознать ЯВНО указанную категорию (колонка category),
// и только если её нет — определяем категорию по тексту отзыва. Так текстовые
// совпадения не перебивают разметку, сделанную при сборе данных.
const CATEGORY_ALIASES = [
  [/списан|возврат|деньг|refund|двойн|удерж/i,                              'Списания и возвраты'],
  [/навязыв|навяза|впарив|доплат|продаж/i,                                  'Навязывание услуг'],
  [/пробн|бесплатн|вводн/i,                                                 'Пробный урок'],
  [/разговорн|клуб|speaking/i,                                              'Разговорный клуб'],
  [/гибк|удобн|свободн|круглосуточн|расписание под/i,                       'Гибкость расписания'],
  [/отмен|перенос|расписан|график|опозда/i,                                 'Отмена и перенос занятий'],
  [/цен|дорог|стоимост|тариф|оплат|подорож/i,                               'Цена и оплата'],
  [/препод|учител|репетитор|носител|педагог/i,                              'Преподаватель'],
  [/техн|платформ|приложен|интерфейс|кабинет|связ|звук|лаг|глюч|микрофон/i, 'Платформа и техника'],
  [/поддержк|менеджер|куратор|служб/i,                                      'Поддержка'],
  [/результат|прогресс|уровен|выучил|эффект|заговор/i,                      'Результат и прогресс'],
  [/домашн|материал|учебник|методик/i,                                      'Материалы и ДЗ'],
  [/сайт|регистрац/i,                                                       'Сайт и личный кабинет'],
  [/репутац|политич|контор|скандал|довери/i,                                'Репутация компании']
];
// те же правила, но применяются к тексту отзыва, если категория не указана
const CATEGORY_RULES = [
  [/списан|двойн.*оплат|верн.*деньг|возврат|refund/i,                      'Списания и возвраты'],
  [/навязыв|навяза|доплат|прода.*(курс|пакет)|впарив/i,                     'Навязывание услуг'],
  [/пробн|бесплатн.*урок|вводн.*урок/i,                                     'Пробный урок'],
  [/разговорн.*(клуб|практик)|клуб/i,                                       'Разговорный клуб'],
  [/гибк|удобн.*врем|свободн.*слот|круглосуточн/i,                          'Гибкость расписания'],
  [/отмен|перенос|расписан|график|опозда/i,                                 'Отмена и перенос занятий'],
  [/цен|дорог|стоимост|тариф|оплат|подорож|дороже/i,                        'Цена и оплата'],
  [/препод|учител|репетитор|носител|педагог/i,                              'Преподаватель'],
  [/техн|платформ|приложен|интерфейс|связь|звук|лага|глюч|микрофон|кабинет/i, 'Платформа и техника'],
  [/поддержк|менеджер|служб.*забот|куратор/i,                               'Поддержка'],
  [/результат|прогресс|заговор|уровен|выучил|стал.*говорить|эффект/i,       'Результат и прогресс'],
  [/домашн|материал|учебник|методик/i,                                      'Материалы и ДЗ'],
  [/регистрац|личн.*кабинет|сайт/i,                                         'Сайт и личный кабинет'],
  [/репутац|политич|скандал|контор|довери/i,                                'Репутация компании']
];
function normCategory(explicit, text) {
  const e = clean(explicit).toLowerCase();
  if (e) {
    for (const [re, name] of CATEGORY_ALIASES) if (re.test(e)) return name;
  }
  const t = clean(text);
  for (const [re, name] of CATEGORY_RULES) if (re.test(t)) return name;
  return 'Прочее';
}

// --- 6. Тональность: из оценки (1-5) либо из текста ---
function normType(type, rating, text) {
  const t = clean(type).toLowerCase();
  if (/позитив|positive/.test(t)) return 'позитив';
  if (/негатив|negative/.test(t)) return 'негатив';
  if (/смешан|mixed|нейтрал/.test(t)) return 'смешанный';
  const r = parseFloat(clean(rating).replace(',', '.'));
  if (!isNaN(r)) return r >= 4 ? 'позитив' : (r <= 2 ? 'негатив' : 'смешанный');
  if (/отличн|нрав|рекоменд|довол|супер|удобн/i.test(text)) return 'позитив';
  if (/ужас|разочаров|плохо|обман|вернул|больше не/i.test(text)) return 'негатив';
  return 'смешанный';
}

// --- 7. Нормализация трёх источников ---
const tariffs = parseCSV(tariffsRaw)
  .map(r => {
    const priceFrom = parseFloat(clean(r.price_from).replace(/[^\d.]/g, '')) || null;
    const priceTo   = parseFloat(clean(r.price_to).replace(/[^\d.]/g, '')) || null;
    const perLesson = parseFloat(clean(r.price_per_lesson).replace(/[^\d.]/g, '')) || null;
    return {
      source: 'Тарифы конкурентов',
      school: normSchool(r.school),
      plan: clean(r.plan),
      lessons: clean(r.lessons),
      lesson_minutes: clean(r.lesson_minutes),
      price_per_lesson: perLesson,
      price_from: priceFrom,
      price_to: priceTo,
      // Валюта обязательна: EnglishDom работает на украинском рынке и публикует
      // цены в гривнах. Без пометки валюты модель сравнила бы 380 грн с 1890 ₽
      // как сопоставимые числа.
      currency: /uah|грн/i.test(clean(r.currency)) ? 'грн' : '₽',
      format: clean(r.format),
      trial_lesson: clean(r.trial_lesson),
      notes: clean(r.notes),
      source_url: clean(r.source_url),
      checked_date: normDate(r.checked_date)
    };
  })
  .filter(r => r.school && (r.plan || r.price_from));

const seenReview = new Set();
const reviews = parseCSV(reviewsRaw)
  .map(r => {
    const text = clean(r.text);
    return {
      source: 'Отзывы пользователей',
      id: clean(r.id),
      school: normSchool(r.school),
      date: normDate(r.date),
      rating: clean(r.rating),
      platform: clean(r.platform),
      type: normType(r.type, r.rating, text),
      category: normCategory(r.category, text),
      text: text.length > 600 ? text.slice(0, 600) + '…' : text,
      source_url: clean(r.source_url)
    };
  })
  .filter(r => {
    if (!r.school || r.text.length < 15) return false;
    const key = (r.school + '|' + r.text.slice(0, 80)).toLowerCase();
    if (seenReview.has(key)) return false;   // дедупликация повторов
    seenReview.add(key);
    return true;
  });

const marketReview = String(marketRaw).split('\n').map(l => l.replace(/\s+$/, '')).join('\n').trim();

// --- 8. Первичная статистика: частоты по категориям (основа для группировки) ---
const byCategory = {};
for (const r of reviews) {
  const c = byCategory[r.category] || (byCategory[r.category] = {
    category: r.category, total: 0, негатив: 0, позитив: 0, смешанный: 0,
    schools: {}, platforms: {}, months: {}, examples: []
  });
  c.total++;
  c[r.type] = (c[r.type] || 0) + 1;
  c.schools[r.school] = (c.schools[r.school] || 0) + 1;
  c.platforms[r.platform] = (c.platforms[r.platform] || 0) + 1;
  if (/^\d{4}-\d{2}$/.test(r.date)) c.months[r.date] = (c.months[r.date] || 0) + 1;
  if (c.examples.length < 3) c.examples.push('#' + r.id + ': ' + r.text.slice(0, 160));
}

const context = {
  prepared_at: new Date().toISOString().slice(0, 10),
  object: 'Ниша онлайн-школ английского языка (обучение взрослых, B2C, Россия)',
  competitors: ['Skyeng', 'Инглекс', 'EnglishDom'],
  sources: {
    tariffs: { type: 'первичный', role: 'основной', items: tariffs.length, file: 'tariffs.csv' },
    reviews: { type: 'поведенческий', role: 'основной', items: reviews.length, file: 'reviews.csv' },
    market:  { type: 'вторичный', role: 'дополнительный', file: 'market-review.md' }
  },
  normalized: { tariffs: tariffs, reviews: reviews, market_review_text: marketReview },
  stats: {
    reviews_total: reviews.length,
    by_school: reviews.reduce((a, r) => (a[r.school] = (a[r.school] || 0) + 1, a), {}),
    by_type: reviews.reduce((a, r) => (a[r.type] = (a[r.type] || 0) + 1, a), {}),
    platforms: reviews.reduce((a, r) => (a[r.platform] = (a[r.platform] || 0) + 1, a), {}),
    by_month: reviews.filter(r => /^\d{4}-\d{2}$/.test(r.date))
      .reduce((a, r) => (a[r.date] = (a[r.date] || 0) + 1, a), {}),
    date_range: (() => {
      const d = reviews.map(r => r.date).filter(x => /^\d{4}-\d{2}/.test(x)).sort();
      return d.length ? d[0] + ' … ' + d[d.length - 1] : 'даты не указаны';
    })(),
    by_category: Object.values(byCategory).sort((a, b) => b.total - a.total)
  }
};

return [{ json: { context: context, context_json: JSON.stringify(context) } }];
