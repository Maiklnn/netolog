// Узел «Подготовка файла (CSV)».
// Вторая запись на диск: расписание для демо-среды. Данные берутся из узла
// «Сборка итогового документа» напрямую — так узел не зависит от того, что
// предыдущий шаг уже перезаписал своё бинарное поле.

const d = $('Сборка итогового документа').first().json;
const fileName = 'demo-schedule-' + d.plan_start + '.csv';

const bin = await helpers.prepareBinaryData(
  Buffer.from(d.demo_csv, 'utf8'),
  fileName,
  'text/csv'
);

return [{
  json: {
    run_date: d.plan_start,
    file_name: fileName,
    demo_rows: (d.demo_rows || []).length,
    on_check: (d.demo_rows || []).filter(function (r) { return r.status === 'на проверке'; }).length,
    draft: (d.demo_rows || []).filter(function (r) { return r.status === 'черновик'; }).length,
    verdict: d.verdict,
    checks_passed: d.checks_passed,
    checks_total: d.checks_total,
  },
  binary: { data: bin },
}];
