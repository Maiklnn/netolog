// Узел «Подготовка файла (Markdown)».
// Операция write в узле «Read/Write Files from Disk» работает с бинарными данными,
// поэтому текст документа превращается в бинарный файл content-plan-<дата>.md.

const d = $json;
const fileName = 'content-plan-' + d.plan_start + '.md';

const bin = await helpers.prepareBinaryData(
  Buffer.from(d.document_md, 'utf8'),
  fileName,
  'text/markdown'
);

return [{
  json: {
    run_date: d.plan_start,
    file_name: fileName,
    document_chars: d.document_chars,
    verdict: d.verdict,
    checks_passed: d.checks_passed,
    checks_total: d.checks_total,
    document_md: d.document_md,
  },
  binary: { data: bin },
}];
