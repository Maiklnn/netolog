// ============================================================================
// ШАГ 4б. КАРТИНКА ИЗ BASE64 (ветка запасного генератора)
// ----------------------------------------------------------------------------
// Нужен для Stable Horde: он отдаёт не ссылку, а картинку в base64 внутри JSON.
// Code-узел не умеет тянуть бинарник из сети, но base64 -> файл он собирает
// без потерь: проверено диагностикой tools/probe-binary-roundtrip.py —
// md5 записанного файла совпадает с исходным.
//
// Тип файла определяем по «магическим» байтам, а не по расширению: воркеры
// Stable Horde отдают то webp, то png, то jpg.
// ============================================================================

const H = this.helpers;
const items = $input.all();
const out = [];

function sniffImage(buf) {
  if (buf[0] === 0x89 && buf[1] === 0x50) return { mime: 'image/png', ext: 'png' };
  if (buf[0] === 0xFF && buf[1] === 0xD8) return { mime: 'image/jpeg', ext: 'jpg' };
  if (buf[0] === 0x52 && buf[1] === 0x49) return { mime: 'image/webp', ext: 'webp' };
  return { mime: 'image/png', ext: 'png' };
}

for (let i = 0; i < items.length; i++) {
  const j = items[i].json;

  if (!j.image_b64) {
    throw new Error('Нет base64-изображения для варианта ' + j.id + ' — ветка вызвана ошибочно.');
  }

  const buf = Buffer.from(j.image_b64, 'base64');
  if (!buf.length) {
    throw new Error('Base64-изображение варианта ' + j.id + ' не декодировалось.');
  }

  const kind = sniffImage(buf);
  const fileName = String(j.file_name).replace(/\.[a-z0-9]+$/i, '') + '.' + kind.ext;
  const bin = await H.prepareBinaryData(buf, fileName, kind.mime);

  const next = Object.assign({}, j, {
    file_name: fileName,
    image_mime: kind.mime,
    image_bytes: buf.length,
    image_kb: Math.round(buf.length / 1024)
  });
  delete next.image_b64;   // дальше картинка живёт в binary, base64 в JSON не нужен

  out.push({ json: next, binary: { data: bin } });
}

return out;
