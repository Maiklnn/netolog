// ============================================================================
// ШАГ 7. ИСПРАВЛЕНИЕ ПРОМТА
// ----------------------------------------------------------------------------
// Сюда попадают только те креативы, у которых в чек-листе больше двух «нет».
// Дописываем в промт ровно то, на что указал чек-лист, — по одному блоку
// уточнений на каждый проваленный пункт. Ничего другого не меняем, чтобы
// правка осталась правкой, а не новой генерацией «с нуля».
//
// Сид НЕ меняем. Раньше здесь стоял новый сид (`seed + 1000 × попытка`) с
// объяснением «иначе выйдет почти та же картинка». Объяснение верное, но цена
// оказалась выше: по заданию альтернатива V4 — это V1 с изменённым ровно одним
// параметром (стилем), и сид для неё копируется от V1 принудительно. Как только
// правка уводила сид, пара V1/V4 расходилась по кадру, и «чем отличается
// результат» описывал уже не разницу стилей, а две разные сцены. В прогоне 87
// V1 попал в правку, V4 — нет, и сравнивать их стало нечем.
// Теперь правка меняет только текст промта: кадр остаётся тем же, а уточнения
// по проваленным пунктам чек-листа — то, ради чего правка и делалась. Победившую
// попытку выбирает реестр: если правка не помогла, остаётся исходный вариант.
//
// ВАЖНО про язык уточнений. Раньше блоки собирались из русских полей брифа
// (стиль, зона под текст, портрет ЦА) и дописывались в англоязычный промт как
// есть. Для генератора русские слова — не текст, а случайный набор токенов:
// вместо уточнения он получал шум, и «исправленный» креатив выходил хуже
// исходного (в прогоне 82 у V4 стало 4 «нет» вместо 3). Поэтому берём
// английские двойники полей из брифа — style_en, focus_en, *_en.
// ============================================================================

const out = [];

for (const item of $input.all()) {
  const j = item.json;
  const bad = {};
  (j.checklist || []).forEach(function (c) { if (c.answer === 'нет') bad[c.key] = true; });

  const fixes = [];

  if (bad.brief) {
    fixes.push('strictly follow the declared style (' + j.style_en +
      ') and the composition focus (' + j.composition_focus_en +
      '), keep the brand palette: deep navy blue #1B3A6B as the base colour, ' +
      'orange accent #FF7A45 used sparingly, light grey background #F5F7FA; ' +
      j.placement_text_zone_en);
  }
  if (bad.audience) {
    fixes.push('the person in the frame must look like the target audience: ' +
      j.segment_who_en + '; the scene must show this situation: ' + j.segment_insight_en);
  }
  if (bad.forbidden) {
    fixes.push('absolutely no text, no letters, no numbers, no words, no logo, no watermark, ' +
      'no brand marks, no flags, no children, no alcohol, no weapons');
  }
  if (bad.quality) {
    fixes.push('sharp focus, natural anatomy, correct hands with exactly five fingers, ' +
      'clean uncluttered composition, professional commercial photography');
  }

  const attempt = Number(j.attempt || 1) + 1;
  const joined = (j.prompt + '. ' + fixes.join('; ')).replace(/\s+/g, ' ').trim();

  // Страховка на случай, если кириллица всё-таки приползла из брифа: вырезаем
  // её из промта и честно помечаем это в реестре, а не отправляем молча.
  const stripped = joined.replace(/(?:[А-Яа-яЁё][А-Яа-яЁё\s,;:.()«»—–-]*)+/g, ' ');
  const prompt = stripped.replace(/\s+/g, ' ').replace(/\s+([;,.])/g, '$1').replace(/;\s*;/g, ';').trim();
  const prompt_language_fixed = prompt !== joined;

  out.push({
    json: Object.assign({}, j, {
      attempt: attempt,
      prompt: prompt,
      prompt_source: j.prompt_source + ' + правка',
      prompt_language_fixed: prompt_language_fixed,
      seed: j.seed,
      file_name: j.id + '-a' + attempt + '.webp',
      fix_reason: (j.checklist || []).filter(function (c) { return c.answer === 'нет'; })
        .map(function (c) { return c.label; }).join(' '),
      fix_comment: j.vision_improve || '',
      previous_image_url: j.image_url,
      previous_file_name: j.file_name,
      previous_checklist: j.checklist,
      previous_no_count: j.no_count,
      previous_comment: j.vision_comment,
      fixed_at: $now.setZone('Europe/Moscow').toFormat('yyyy-MM-dd HH:mm:ss')
    })
  });
}

return out;
