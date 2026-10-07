// ============================================================================
// ШАГ 5. ЗАПРОС К VISION-МОДЕЛИ
// ----------------------------------------------------------------------------
// Готовит тело запроса к Ollama: промт проверки и картинку в base64.
//
// ВАЖНО про бинарные данные. В этом n8n бинарники хранятся в файловом режиме
// (N8N_DEFAULT_BINARY_DATA_MODE=filesystem): в поле binary.data.data лежит не
// base64-строка, а короткая ссылка вида "filesystem-v2". Поэтому байты надо
// доставать хелпером getBinaryDataBuffer — он возвращает настоящий Buffer
// внутри Code-узла, и уже его переводим в base64.
// (Проверено диагностикой tools/probe-binary.py: ссылка длиной 13 символов
//  против 40826 байт у getBinaryDataBuffer.)
// ============================================================================

const H = this.helpers;
const items = $input.all();
const out = [];

for (let i = 0; i < items.length; i++) {
  const j = items[i].json;
  const bin = (items[i].binary && items[i].binary.data) ? items[i].binary.data : null;

  if (!bin) {
    throw new Error('Нет бинарных данных изображения для варианта ' + j.id + ' (' + j.file_name + ')');
  }

  let b64 = null;
  let bytes = 0;
  try {
    const buf = await H.getBinaryDataBuffer(i, 'data');
    if (Buffer.isBuffer(buf) && buf.length > 0) {
      b64 = buf.toString('base64');
      bytes = buf.length;
    }
  } catch (e) {
    throw new Error('Не удалось прочитать байты изображения ' + j.file_name + ': ' +
      String((e && e.message) || e));
  }

  if (!b64) {
    throw new Error('Пустые байты изображения ' + j.file_name);
  }

  const st = j.settings || {};

  const prompt = [
    'Ты — арт-директор онлайн-школы английского языка. Оцени готовый рекламный креатив по чек-листу заказчика.',
    '',
    j.vision_context,
    '',
    'ПРОВЕРЯЕМЫЙ ВАРИАНТ ' + j.id + ':',
    'Сегмент ЦА: ' + j.segment_id + ' — ' + j.segment_name + '. ' + j.segment_who + '. Инсайт: ' + j.segment_insight + '.',
    'Площадка: ' + j.placement_id + ' — ' + j.placement_name + ', ' + j.placement_size + ' (' + j.placement_ratio + '), зона под текст: ' + j.placement_text_zone + '.',
    'Заявленный стиль: ' + j.style + '. Фокус: ' + j.composition_focus + '. Акцент: ' + j.accent + '.',
    'Задание генератору (промт): ' + j.prompt,
    '',
    'ЧЕК-ЛИСТ — ответь «да» или «нет» по каждому пункту:',
    '1. brief — соответствие брифу, бренду и площадке: сюжет и настроение совпадают с описанием, пропорция и композиция подходят площадке, зона под будущий текст действительно свободна, цвета согласуются с палитрой бренда и заявленным стилем.',
    '2. audience — релевантность ЦА: изображённый человек и ситуация выглядят как описанный сегмент (возраст, контекст, уровень жизни), не вызывают отторжения у этой аудитории.',
    '3. forbidden — отсутствие запрещённых элементов: на картинке нет текста, букв и цифр, логотипов и водяных знаков, флагов и политической символики, стереотипов об Англии, детей, алкоголя, оружия, искажённых лиц и лишних пальцев.',
    '4. quality — техническое качество: композиция читается, изображение резкое, нет артефактов генерации, креатив пригоден для публикации в ленте.',
    '',
    'Ответь СТРОГО одним JSON-объектом, без markdown и без текста вокруг:',
    '{"brief":"да|нет","audience":"да|нет","forbidden":"да|нет","quality":"да|нет","comment":"1-2 предложения: что изображено и общее впечатление","improve":"одно предложение, что конкретно поправить, если есть «нет»; иначе — правки не нужны"}'
  ].join('\n');

  out.push({
    json: Object.assign({}, j, {
      ollama_model: st.vision_model || 'deepseek-v4.1-flash:cloud',
      vision_temperature: (st.vision_temperature === undefined ? 0.1 : st.vision_temperature),
      vision_prompt: prompt,
      image_b64: b64,
      image_bytes: bytes,
      image_kb: Math.round(bytes / 1024)
    })
  });
}

return out;
