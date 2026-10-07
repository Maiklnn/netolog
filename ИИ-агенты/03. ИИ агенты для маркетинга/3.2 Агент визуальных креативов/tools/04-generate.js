// ============================================================================
// ШАГ 4. ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЙ
// ----------------------------------------------------------------------------
// Бесплатные публичные генераторы живут неровно, поэтому эшелонов три.
//
//   1) Быстрый эшелон — публичные спейсы Hugging Face на ZeroGPU
//      (FLUX.1-merged, Kolors, FLUX.1-dev). Отдают ссылку за секунды, но
//      квота у них на IP, а не на запрос: когда она выбрана, все три спейса
//      отвечают «event: error / data: null» за пару секунд. Поэтому спейсы
//      проверяются ОДНИМ пробным запросом на первом же варианте, а не
//      двадцатью четырьмя, как было бы при переборе по каждому варианту.
//   2) Основной эшелон — Stable Horde, краудсорсинг-сеть воркеров. Ключ не
//      нужен (анонимный '0000000000'), квоты нет, отдаёт base64. Но очередь
//      анонимного клиента тем длиннее, чем «дороже» задание: у задачи на
//      512x512 она стартует сразу, у 1024x1024 может стоять сотни позиций.
//      В часы нагрузки сервис вдобавок закрывает крупные запросы порогом
//      «заслуг»: «Due to heavy demand, for requests over 1024x1024 or over the
//      applicable first-order-equivalent sampler work budget the client needs to
//      already have the required kudos» (замер tools/horde-queue-probe.py:
//      задача 1024x1024 у SDXL 1.0 стояла 295-й, а та же сцена 512x512 —
//      нулевой). Порог считается по площади и числу шагов, поэтому список из
//      нескольких SDXL-моделей его тоже перешагивает: он оценивается дороже
//      одной модели (20.03 против 18.0) и был отклонён. Отсюда правило: у
//      основного эшелона ровно одна модель, а лёгкий запас — рабочий путь, а
//      не редкая страховка (в прогоне 86 тяжёлый размер так и не дошёл).
//   3) Лёгкий запас — если за HORDE_FAST_AFTER_MS ни одна задача основного
//      эшелона не сдвинулась с места, недостающие варианты досылаются в
//      уменьшенном размере с меньшим числом шагов. Первичные задачи при этом
//      продолжают опрашиваться: что придёт раньше — то и пойдёт в результат.
//      Фактический размер пишется в поле size_actual.
//
// Pollinations.ai (вариант, который пробовали первым) в работу не годится:
// на любой новый запрос отвечает 402 Payment Required, картинку отдаёт только
// из кэша — проверено tools/horde-size-test.py и отдельной пробой параметров.
//
// ВАЖНО про бинарные данные: Code-узел в этом n8n НЕ умеет скачивать бинарник
// по сети — helpers.httpRequest отдаёт побитую строку (проверено диагностикой
// tools/probe-binary-roundtrip.py: 28710 «байт» вместо 30320). Зато base64,
// полученный как обычный JSON, Code-узел превращает в настоящий файл без потерь
// (md5 совпадает). Поэтому:
//   • быстрый эшелон отдаёт ССЫЛКУ  -> её скачивает узел HTTP Request;
//   • Stable Horde отдаёт BASE64     -> его собирает узел «Картинка из base64».
// Дальше ветки сходятся на узле сохранения файла.
// ============================================================================

const H = this.helpers;
const items = $input.all();

function sleep(ms) {
  return new Promise(function (resolve) { setTimeout(resolve, ms); });
}

function msg(e) {
  return String((e && e.message) || e);
}

// --- эшелон 1: публичные спейсы Hugging Face --------------------------------
const HF_PROVIDERS = [
  {
    name: 'FLUX.1-merged (multimodalart)',
    host: 'https://multimodalart-flux-1-merged.hf.space',
    endpoint: '/infer',
    body: function (t) { return { data: [t.prompt, t.seed, false, t.width, t.height, 3.5, 4] }; }
  },
  {
    name: 'Kolors (Kwai)',
    host: 'https://kwai-kolors-kolors.hf.space',
    endpoint: '/infer',
    body: function (t) {
      return { data: [t.prompt, null, 0.5, negativeFor(t), t.seed, false, t.width, t.height, 5.0, 25] };
    }
  },
  {
    name: 'FLUX.1-dev (black-forest-labs)',
    host: 'https://black-forest-labs-flux-1-dev.hf.space',
    endpoint: '/infer',
    body: function (t) { return { data: [t.prompt, t.seed, false, t.width, t.height, 3.5, 4] }; }
  }
];

async function hfOnce(provider, t) {
  const call = await H.httpRequest({
    url: provider.host + '/gradio_api/call' + provider.endpoint,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: provider.body(t),
    json: true,
    timeout: 30000
  });

  const eventId = call && call.event_id;
  if (!eventId) throw new Error('спейс не вернул event_id');

  const stream = await H.httpRequest({
    url: provider.host + '/gradio_api/call' + provider.endpoint + '/' + eventId,
    method: 'GET',
    encoding: 'utf8',
    timeout: 180000
  });

  const text = String(stream || '');
  if (/event:\s*error/.test(text)) {
    throw new Error('спейс отклонил задание (квота ZeroGPU или ошибка модели)');
  }
  const m = text.match(/"url"\s*:\s*"([^"]+)"/);
  if (!m) throw new Error('в ответе спейса нет ссылки на картинку');
  return m[1];
}

// --- эшелон 2 и 3: Stable Horde ---------------------------------------------
const HORDE_API = 'https://stablehorde.net/api/v2';
const HORDE_KEY = '0000000000';   // анонимный ключ Stable Horde
const HORDE_MODEL = 'SDXL 1.0';

// Модели для лёгкого запаса — с родным разрешением 512 (SD 1.5-финетюны).
// SDXL 1.0 рассчитан на 1024: на 512x512 он уходит в плоскую стилизацию, и
// «запасная» картинка получается абстрактной — в прогоне 82 так вышли V1 и V3,
// чек-лист поставил им 4 и 3 «нет» именно за это.
//
// Base-модель stable_diffusion из списка убрана: в прогоне 86 она нарисовала
// «руки над блокнотом» вместо героини в кадре и куклу вместо женщины у стола,
// и чек-лист справедливо поставил этим вариантам «нет» за соответствие брифу.
// Замер на одном и том же промте (tools/horde-model-pick.py, 512x512, 30 шагов)
// показал, что финетюны держат сцену, а base-модель её теряет. AbsoluteReality
// стоит первым: у него кадр совпал с брифом лучше всех — героиня в тёмно-синем
// костюме с оранжевым акцентом, брендовая палитра и свободная левая половина.
// Порядок в списке — приоритет: Stable Horde берёт первую модель, воркер
// которой свободен.
const HORDE_MODELS_FAST = ['AbsoluteReality', 'Realistic Vision', 'Deliberate'];
const HORDE_POLL_MS = 15000;
const HORDE_MAX_WAIT_MS = 35 * 60 * 1000;   // общий потолок ожидания очереди
// Столько ждём «тяжёлый» размер, прежде чем досылать лёгкий. Замер на боевых
// конфигурациях (tools/horde-size-test.py): задача 1024x1024 у анонимного
// клиента стояла 189-й в общей очереди и за 15 минут не сдвинулась, а та же
// сцена в 512x512 на модели с родным разрешением 512 стартовала сразу
// (queue_position 0, 13 свободных воркеров) и была готова за 1,9 минуты.
const HORDE_FAST_AFTER_MS = 3 * 60 * 1000;
// Анонимному клиенту сервис разрешает около одного запроса в секунду и отвечает
// 429, если частить. Паузы держим и между отправками, и между опросами: иначе
// пачка проверок «съедает» лимит, отправка лёгкого размера падает, и узел
// честно ждёт тяжёлую очередь до самого потолка.
const HORDE_GAP_MS = 1500;
const HORDE_POLL_GAP_MS = 400;
// Окно на «повышение» размера. Цикл выходит, как только закрылась последняя
// дырка, поэтому лёгкая картинка успевала проскочить раньше тяжёлой и оставалась
// в результате навсегда — тяжёлая задача при этом ещё стояла в очереди и её
// никто не ждал. Теперь после сборки всех вариантов даём живым тяжёлым задачам
// ещё немного времени: что успело — заменит лёгкую картинку.
const HORDE_UPGRADE_GRACE_MS = 8 * 60 * 1000;

// Воркеры Stable Horde берут размеры, кратные 64. Пропорции площадок держим
// точно, а по площади не выходим за 1024x1024: у анонимного клиента запрос
// крупнее требует «заслуг» (KudosUpfront).
const HORDE_SIZES = {
  '1:1': [1024, 1024],
  '4:5': [768, 960],
  '3:4': [768, 1024],
  '4:3': [1024, 768],
  '16:9': [1024, 576]
};

// Лёгкий запас: те же пропорции, но маленькая площадь — такие задачи анонимной
// очереди стартуют почти сразу.
const HORDE_SIZES_FAST = {
  '1:1': [512, 512],
  '4:5': [512, 640],
  '3:4': [512, 640],
  '4:3': [512, 384],
  '16:9': [576, 320]
};

// Английский список запретов, собранный из restrictions.forbidden_elements
// брифа. Это не только запасной вариант: генератор понимает английские слова,
// поэтому русский negative из брифа ему бесполезен (см. negativeFor ниже).
const DEFAULT_NEGATIVE = 'text, letters, numbers, words, captions, watermark, ' +
  'logo, signature, brand logos, apple logo, laptop logo, headset logo, ' +
  'device brand marks, stickers on devices, flags, coats of arms, maps, ' +
  'political or religious symbols, Big Ben, red double-decker bus, cup of tea, ' +
  'royal guard, Tower Bridge, children, teenagers, school chalkboard, ' +
  'celebrities, real people, alcohol, tobacco, weapons, blood, gambling, drugs, ' +
  'medical masks, disasters, nudity, distorted face, extra fingers, fused ' +
  'fingers, deformed limbs, low quality, blurry, jpeg artifacts, collage, ' +
  'frame, gradient stock background';

// SDXL и другие диффузионные модели работают через английский CLIP: русские
// слова для них — не текст, а случайные токены, то есть запретов становится ноль.
// Агент писал negative по-русски (так же, как сформулированы запреты в брифе),
// и в генератор уходил неработающий набор. Поэтому здесь проверяем язык: если
// кириллица есть — берём английский список, а исходный текст сохраняем для
// реестра отдельным полем.
function negativeFor(t) {
  const n = String(t.negative || '');
  if (n.length > 3 && !/[А-Яа-яЁё]/.test(n)) return n;
  return DEFAULT_NEGATIVE;
}

async function horde(path, method, body) {
  const options = {
    url: HORDE_API + path,
    method: method,
    headers: {
      apikey: HORDE_KEY,
      'Client-Agent': 'n8n-visual-creatives:1.0:anonymous',
      'Content-Type': 'application/json'
    },
    json: true,
    timeout: 60000
  };
  if (body) options.body = body;
  return await H.httpRequest(options);
}

function hordeBody(t, size, steps, models) {
  return {
    prompt: t.prompt,
    params: {
      width: size[0],
      height: size[1],
      steps: steps,
      cfg_scale: 7,
      sampler_name: 'k_euler_a',
      n: 1,
      seed: String(t.seed === undefined || t.seed === null ? 0 : t.seed),
      negative_prompt: negativeFor(t)
    },
    nsfw: false,
    censor_nsfw: true,
    trusted_workers: false,
    slow_workers: true,
    models: models || [HORDE_MODEL],
    r2: false
  };
}

function sniffImage(buf) {
  if (buf[0] === 0x89 && buf[1] === 0x50) return { mime: 'image/png', ext: 'png' };
  if (buf[0] === 0xFF && buf[1] === 0xD8) return { mime: 'image/jpeg', ext: 'jpg' };
  if (buf[0] === 0x52 && buf[1] === 0x49) return { mime: 'image/webp', ext: 'webp' };
  return { mime: 'image/png', ext: 'png' };
}

// --- эшелон 1: быстрые спейсы -----------------------------------------------
const result = [];
const errors = [];

if (items.length) {
  // Квота у спейсов одна на IP, поэтому сначала один пробный запрос: если он
  // не прошёл — перебирать остальные варианты бессмысленно и долго.
  let hfProvider = null;
  for (const provider of HF_PROVIDERS) {
    try {
      result[0] = { url: await hfOnce(provider, items[0].json), provider: provider.name, attempt: 1 };
      hfProvider = provider;
      break;
    } catch (e) {
      errors.push(items[0].json.id + ' | проверка ' + provider.name + ': ' + msg(e));
      await sleep(1000);
    }
  }

  if (hfProvider) {
    for (let i = 1; i < items.length; i++) {
      try {
        result[i] = { url: await hfOnce(hfProvider, items[i].json), provider: hfProvider.name, attempt: 1 };
      } catch (e) {
        errors.push(items[i].json.id + ' | ' + hfProvider.name + ': ' + msg(e));
      }
    }
  }
}

// --- эшелоны 2 и 3: Stable Horde --------------------------------------------
const needHorde = [];
for (let i = 0; i < items.length; i++) {
  if (!result[i]) needHorde.push(i);
}

const hordeNote = [];

if (needHorde.length) {
  const jobs = [];        // {id, index, size, fast, taken}
  const pending = {};     // id -> job

  async function submitJob(idx, fast) {
    const t = items[idx].json;
    const table = fast ? HORDE_SIZES_FAST : HORDE_SIZES;
    const size = table[t.placement_ratio] || (fast ? HORDE_SIZES_FAST['1:1'] : HORDE_SIZES['1:1']);
    const models = fast ? HORDE_MODELS_FAST : [HORDE_MODEL];
    try {
      const sub = await horde('/generate/async', 'POST', hordeBody(t, size, fast ? 30 : 25, models));
      if (!sub || !sub.id) throw new Error('сервис не вернул id задания');
      const job = { id: sub.id, index: idx, size: size, fast: fast, models: models, taken: false };
      jobs.push(job);
      pending[sub.id] = job;
      return true;
    } catch (e) {
      errors.push(t.id + ' | Stable Horde (отправка ' + size[0] + 'x' + size[1] + '): ' + msg(e));
      return false;
    }
  }

  const startedAt = Date.now();
  const missing = function () {
    return needHorde.filter(function (i) { return !result[i]; });
  };

  for (const idx of needHorde) {
    await submitJob(idx, false);
    await sleep(HORDE_GAP_MS);
  }

  let fastSwitched = false;
  const faulted = {};
  const fastTries = {};

  // Варианты, которые уже закрыты лёгкой картинкой, но у которых тяжёлая задача
  // ещё жива: ради них и держим окно ожидания.
  const upgradeable = function () {
    const list = [];
    for (let i = 0; i < items.length; i++) {
      const r = result[i];
      if (!r || !r.fast) continue;
      const alive = jobs.some(function (j) {
        return j.index === i && !j.fast && pending[j.id];
      });
      if (alive) list.push(i);
    }
    return list;
  };

  let upgradeDeadline = null;

  while (Date.now() - startedAt < HORDE_MAX_WAIT_MS) {
    if (!missing().length) {
      const waiting = upgradeable();
      if (!waiting.length) break;
      if (upgradeDeadline === null) {
        upgradeDeadline = Date.now() + HORDE_UPGRADE_GRACE_MS;
        hordeNote.push('лёгкие картинки собраны, ждём тяжёлый размер ещё ' +
          Math.round(HORDE_UPGRADE_GRACE_MS / 60000) + ' мин: ' +
          waiting.map(function (i) { return items[i].json.id; }).join(', '));
      }
      if (Date.now() > upgradeDeadline) break;
    }
    await sleep(HORDE_POLL_MS);

    let moving = 0;
    for (const id of Object.keys(pending)) {
      const job = pending[id];
      const have = result[job.index];
      // Готовый результат — не повод бросить задачу: лёгкая картинка уже есть,
      // но тяжёлую мы всё ещё ждём, чтобы она её заменила. Раньше здесь стояла
      // проверка «result есть — удалить», и тяжёлая задача пропадала из pending
      // в тот же круг, как приходила лёгкая. Окно ожидания после этого не
      // находило живых тяжёлых задач и закрывалось мгновенно.
      if (have && (job.fast || !have.fast)) { delete pending[id]; continue; }
      try {
        const check = await horde('/generate/check/' + id, 'GET');
        if (!check) continue;
        if (check.done) {
          // забираем картинку
          const status = await horde('/generate/status/' + id, 'GET');
          const gen = (status && status.generations && status.generations[0]) ? status.generations[0] : null;
          if (gen && gen.img) {
            const buf = Buffer.from(gen.img, 'base64');
            if (buf.length) {
              // тяжёлый размер важнее лёгкого: если место ещё свободно — берём его
              if (!result[job.index] || (result[job.index].fast && !job.fast)) {
                const kind = sniffImage(buf);
                result[job.index] = {
                  base64: gen.img,
                  provider: 'Stable Horde (' + (gen.model || HORDE_MODEL) + ')',
                  ext: kind.ext,
                  mime: kind.mime,
                  bytes: buf.length,
                  seed: gen.seed,
                  fast: job.fast,
                  size: job.size
                };
                hordeNote.push(items[job.index].json.id + ': ' + String(gen.model || HORDE_MODEL) +
                  ' ' + job.size[0] + 'x' + job.size[1]);
              }
            } else {
              errors.push(items[job.index].json.id + ' | Stable Horde: картинка не декодировалась');
            }
          } else {
            errors.push(items[job.index].json.id + ' | Stable Horde: пустой ответ без картинки');
          }
          delete pending[id];
          continue;
        }
        if (check.faulted) {
          if (!faulted[job.index]) {
            errors.push(items[job.index].json.id + ' | Stable Horde (' + job.size[0] + 'x' + job.size[1] +
              '): задание отклонено');
            faulted[job.index] = true;
          }
          delete pending[id];
          continue;
        }
        const q = check.queue_position;
        if (check.processing || (typeof q === 'number' && q < 40)) moving++;
      } catch (e) {
        // одиночный сбой опроса не должен ронять весь цикл
      }
      await sleep(HORDE_POLL_GAP_MS);
    }

    // Лёгкий запас: тяжёлые задачи стоят в очереди — досылаем уменьшенные.
    // Отправка может не пройти (лимит запросов, сбой сети), поэтому пробуем
    // в каждом круге опроса, пока у варианта нет ни лёгкой задачи, ни картинки.
    if (Date.now() - startedAt > HORDE_FAST_AFTER_MS && missing().length) {
      if (!fastSwitched) {
        fastSwitched = true;
        hordeNote.push('включён лёгкий размер (в очереди оставалось ' +
          jobs.filter(function (j) { return !faulted[j.index]; }).length + ' задач)');
      }
      for (const idx of missing()) {
        const hasFast = jobs.some(function (j) {
          return j.index === idx && j.fast && pending[j.id];
        });
        if (hasFast) continue;
        // пять попыток на вариант: если сервис стабильно отказывает,
        // долбить его каждые 15 секунд до потолка бессмысленно
        fastTries[idx] = (fastTries[idx] || 0);
        if (fastTries[idx] >= 5) continue;
        fastTries[idx]++;
        await submitJob(idx, true);
        await sleep(HORDE_GAP_MS);
      }
    }
  }

  const still = missing();
  if (still.length) {
    errors.push('Stable Horde: за ' + Math.round(HORDE_MAX_WAIT_MS / 60000) +
      ' мин не дождались картинок для: ' + still.map(function (i) { return items[i].json.id; }).join(', '));
  }

  // Окно закрылось, а тяжёлые задачи так и не дошли: фиксируем это в реестре,
  // чтобы «size_downgraded: true» не выглядел случайностью.
  const notUpgraded = upgradeable();
  if (notUpgraded.length) {
    hordeNote.push('тяжёлый размер не догнал за окно ожидания: ' +
      notUpgraded.map(function (i) { return items[i].json.id; }).join(', ') + ' — оставлен лёгкий');
  }
}

// --- собираем результат ------------------------------------------------------
const out = [];

for (let i = 0; i < items.length; i++) {
  const t = Object.assign({}, items[i].json);
  const r = result[i];

  if (!r) {
    throw new Error('Ни один генератор не отдал изображение для варианта ' + t.id + '. ' +
      errors.join(' | '));
  }

  t.generator = r.provider;
  t.generator_attempt = r.attempt || 1;
  t.generator_errors = errors.slice();
  // Заметки по ходу ожидания (какой размер, что успело дойти) — раньше они
  // копились в массиве и никуда не попадали: в реестре не было видно, почему
  // у креатива понижен размер.
  t.generator_note = hordeNote.slice();
  // Что именно ушло в генератор как запрет и почему: если negative_used не
  // совпадает с negative из ответа агента, значит исходный был на кириллице и
  // модель его всё равно не поняла.
  t.negative_used = negativeFor(t);
  t.negative_source = (t.negative_used === String(t.negative || ''))
    ? 'ответ агента' : 'английский список из брифа (ответ агента был на русском)';
  t.generated_at = $now.setZone('Europe/Moscow').toFormat('yyyy-MM-dd HH:mm:ss');

  if (r.url) {
    // быстрый эшелон: картинку скачает следующий узел HTTP Request
    t.image_url = r.url;
    t.image_b64 = null;
    t.image_delivery = 'url';
    t.size_actual = t.width + 'x' + t.height;
  } else {
    // Stable Horde: base64 -> бинарник соберёт узел «Картинка из base64»
    t.image_url = null;
    t.image_b64 = r.base64;
    t.image_delivery = 'base64';
    t.image_mime = r.mime;
    t.file_name = String(t.file_name).replace(/\.[a-z0-9]+$/i, '') + '.' + r.ext;
    if (r.seed !== undefined && r.seed !== null) t.seed_actual = r.seed;
    t.size_actual = r.size[0] + 'x' + r.size[1];
    t.size_downgraded = !!r.fast;
    t.width = r.size[0];
    t.height = r.size[1];
  }

  out.push({ json: t });
}

return out;
