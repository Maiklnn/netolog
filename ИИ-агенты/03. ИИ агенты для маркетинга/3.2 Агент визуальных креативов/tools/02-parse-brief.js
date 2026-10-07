// ============================================================================
// ШАГ 2. РАЗБОР БРИФА И ПЛАН ВАРИАНТОВ
// ----------------------------------------------------------------------------
// Читает текст brief.json (пришёл из узла «Текст брифа»), проверяет, что в брифе
// есть всё обязательное, и собирает из него:
//   • brief_pack — компактный текст брифа для LLM-агента (промт-инженера);
//   • tasks      — список вариантов, которые надо сгенерировать.
//
// Размер генерации выводится из пропорции площадки: генератор даёт картинку
// ровно в нужной пропорции, финальный макет дизайнер собирает уже в размере
// площадки, поэтому «несоответствия по размеру» на этом шаге не возникает.
// ============================================================================

const text = String($input.first().json.data || '').trim();
const entry = $('Входной бриф').first().json;
const overrides = entry.overrides || {};

if (!text) {
  throw new Error('Бриф пуст: узел «Текст брифа» не получил текста из ' + entry.brief_path);
}

let brief;
try {
  brief = JSON.parse(text);
} catch (e) {
  throw new Error('brief.json не разбирается как JSON: ' + e.message);
}

// --- проверка обязательных разделов брифа -----------------------------------
const missing = [];
if (!brief.product || !brief.product.name) missing.push('product');
if (!brief.brand || !brief.brand.name) missing.push('brand');
if (!Array.isArray(brief.segments) || brief.segments.length < 2) {
  missing.push('segments (нужно не менее двух сегментов ЦА)');
}
if (!Array.isArray(brief.placements) || !brief.placements.length) missing.push('placements');
if (!brief.restrictions || !Array.isArray(brief.restrictions.forbidden_elements)) {
  missing.push('restrictions.forbidden_elements');
}
if (!Array.isArray(brief.plan) || !brief.plan.length) missing.push('plan');
if (missing.length) {
  throw new Error('В брифе не хватает обязательных разделов: ' + missing.join(', '));
}

const settings = Object.assign({}, brief.settings || {}, overrides);
const fixThreshold = Number(settings.fix_threshold);
if (!isFinite(fixThreshold)) {
  throw new Error('settings.fix_threshold должен быть числом, получено: ' + settings.fix_threshold);
}

// --- размеры генерации по пропорции площадки --------------------------------
const RATIO_SIZE = {
  '1:1': [1024, 1024],
  '4:5': [1024, 1280],
  '3:4': [768, 1024],
  '4:3': [1024, 768],
  '16:9': [1280, 720]
};

const segById = {};
brief.segments.forEach(function (s) { segById[s.id] = s; });
const plByById = {};
brief.placements.forEach(function (p) { plByById[p.id] = p; });

// Компактный контекст брифа: он поедет вместе с каждым вариантом дальше по
// схеме, чтобы узлы проверки не зависели от данных, прочитанных в начале.
const briefContext = [
  'ПРОДУКТ: ' + brief.product.name + '. ' + brief.product.what,
  'УТП: ' + (brief.product.usp || []).join('; ') + '.',
  'БРЕНД: ' + brief.brand.name + ' — ' + brief.brand.positioning + '.',
  'ПАЛИТРА: ' + Object.keys(brief.brand.palette || {}).map(function (k) {
    return brief.brand.palette[k];
  }).join('; ') + '.',
  'ТОНАЛЬНОСТЬ: ' + brief.brand.tone_of_voice + '.',
  'ЗАПРЕЩЕНО: ' + brief.restrictions.forbidden_elements.join('; ') + '.',
  'ТЕХНИЧЕСКИЕ ОГРАНИЧЕНИЯ: ' + brief.restrictions.technical_restrictions.join('; ') + '.'
].join('\n');

const tasks = brief.plan.map(function (p) {
  const seg = segById[p.segment];
  const pl = plByById[p.placement];
  if (!seg) throw new Error('В плане указан неизвестный сегмент ЦА: ' + p.segment);
  if (!pl) throw new Error('В плане указана неизвестная площадка: ' + p.placement);

  const size = RATIO_SIZE[pl.ratio];
  if (!size) throw new Error('Не знаю размер генерации для пропорции ' + pl.ratio);

  return {
    id: p.id,
    segment_id: seg.id,
    segment_name: seg.name,
    segment_who: seg.who,
    segment_insight: seg.insight,
    segment_message: seg.message,
    // Английские двойники русских полей. Нужны узлу правки: уточнения
    // дописываются прямо в промт, а генератор английский, русского он не
    // понимает — русские фразы в промте для него шум.
    segment_who_en: seg.who_en || seg.who,
    segment_insight_en: seg.insight_en || seg.insight,
    placement_id: pl.id,
    placement_name: pl.name,
    placement_size: pl.size,
    placement_ratio: pl.ratio,
    placement_text_zone: pl.text_zone,
    placement_text_zone_en: pl.text_zone_en || pl.text_zone,
    placement_requirements: pl.requirements,
    style: p.style,
    style_en: p.style_en || p.style,
    composition_focus: p.composition_focus,
    composition_focus_en: p.focus_en || p.composition_focus,
    accent: p.accent,
    seed: p.seed,
    width: size[0],
    height: size[1],
    attempt: 1,
    base_variant: p.base_variant || null,
    changed_parameter: p.changed_parameter || null,
    unchanged_parameters: p.unchanged_parameters || null,
    fallback_prompt: p.fallback_prompt || '',
    // промт подставит LLM-агент; если он не справится — останется запасной
    prompt: p.fallback_prompt || '',
    negative: '',
    rationale: '',
    prompt_source: 'fallback',
    vision_context: briefContext,
    settings: settings
  };
});

// --- текст задания для LLM-агента ------------------------------------------
const pack = [
  'БРИФ НА РЕКЛАМНЫЕ ВИЗУАЛЫ',
  'Кампания: ' + brief.campaign,
  'Продукт: ' + brief.product.name + '. ' + brief.product.what,
  'УТП: ' + (brief.product.usp || []).join('; ') + '.',
  'Призыв к действию: ' + (brief.product.cta || '') + '.',
  '',
  'Бренд: ' + brief.brand.name + ' — ' + brief.brand.positioning + '.',
  'Тональность: ' + brief.brand.tone_of_voice + '.',
  'Палитра: ' + Object.keys(brief.brand.palette || {}).map(function (k) {
    return brief.brand.palette[k];
  }).join('; ') + '.',
  'Типографика: ' + brief.brand.typography + '.',
  'Логотип: ' + brief.brand.logo_rule + '.',
  '',
  'СЕГМЕНТЫ ЦА:',
  brief.segments.map(function (s) {
    return '- ' + s.id + ' ' + s.name + ': ' + s.who + '. Уровень: ' + s.current_level +
      '. Инсайт: ' + s.insight + '. Задача: ' + s.job_to_be_done + '. Сообщение: «' + s.message + '».';
  }).join('\n'),
  '',
  'ПЛОЩАДКИ:',
  brief.placements.map(function (p) {
    return '- ' + p.id + ' ' + p.name + ': ' + p.size + ' (' + p.ratio + '), безопасные поля ' +
      p.safe_zone + ', зона под текст — ' + p.text_zone + '. Контекст: ' + p.reading_context +
      '. Требования: ' + p.requirements + '.';
  }).join('\n'),
  '',
  'ВИЗУАЛЬНЫЙ ЯЗЫК:',
  'Базовый стиль: ' + brief.visual_language.style_base + '.',
  'Свет: ' + brief.visual_language.light + '.',
  'Композиция: ' + brief.visual_language.composition + '.',
  'Фокус: ' + brief.visual_language.focus + '.',
  'Акцент: ' + brief.visual_language.accent + '.',
  'Фотография: ' + brief.visual_language.photography + '.',
  '',
  'ВАРИАНТЫ, КОТОРЫЕ НУЖНО ОПИСАТЬ ПРОМТАМИ:',
  tasks.map(function (t) {
    return [
      '- ' + t.id + ': сегмент ' + t.segment_id + ' (' + t.segment_name + '), площадка ' +
        t.placement_id + ' (' + t.placement_name + ', ' + t.placement_size + ', ' + t.placement_ratio +
        ', зона под текст: ' + t.placement_text_zone + '), стиль: ' + t.style +
        ', фокус: ' + t.composition_focus + ', акцент: ' + t.accent + '.',
      t.changed_parameter ? '  ОСОБОЕ УСЛОВИЕ: ' + t.changed_parameter +
        '. Неизменно: ' + t.unchanged_parameters + '.' : ''
    ].filter(Boolean).join('\n');
  }).join('\n'),
  '',
  'ЗАПРЕЩЁННЫЕ ЭЛЕМЕНТЫ (их не должно быть на картинке):',
  brief.restrictions.forbidden_elements.map(function (f) { return '- ' + f; }).join('\n')
].join('\n');

return [{
  json: {
    brief_pack: pack,
    tasks: tasks,
    settings: settings,
    brief_summary: {
      campaign: brief.campaign,
      product: brief.product.name,
      brand: brief.brand.name,
      segments: brief.segments.length,
      placements: brief.placements.length,
      variants: tasks.length
    },
    fix_threshold: fixThreshold,
    parsed_at: $now.setZone('Europe/Moscow').toFormat('yyyy-MM-dd HH:mm:ss')
  }
}];
