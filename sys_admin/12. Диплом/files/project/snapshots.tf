# Задание 7. Резервное копирование: ежедневные снимки дисков всех ВМ стенда.
#
# Снимки создаёт расписание (yandex_compute_snapshot_schedule). Оно запускается
# по cron-выражению и само же удаляет устаревшие снимки — отдельного скрипта
# очистки не нужно. К расписанию подключены загрузочные диски всех шести ВМ:
# и публичных (bastion, Zabbix, Kibana), и внутреннего контура (web-a, web-b,
# Elasticsearch).
#
# Параметры резервного копирования:
#   * расписание — ежедневно в 03:00 UTC (06:00 по Москве);
#   * retention_period = "168h0m0s" — каждый снимок живёт одну неделю (168 часов),
#     после чего Cloud удаляет его автоматически. Глубина хранения — ровно
#     семь снимков на диск, поэтому место в квоте не растёт бесконечно.
#     Провайдер разбирает это поле как длительность Go, поэтому "1w" он не
#     принимает («unknown unit "w"»), а неделя задаётся в часах и минутах.
#
# disk_ids — идентификаторы загрузочных дисков. Берём их из ресурсов ВМ, а не
# константами: диски создаёт Terraform вместе с ВМ, и при пересоздании ВМ
# (например, при переходе на непрерываемые перед сдачей работы) идентификаторы
# меняются — расписание подхватит новые автоматически.
resource "yandex_compute_snapshot_schedule" "daily" {
  name        = "daily-snapshots-${var.flow}"
  description = "Ежедневные снимки дисков всех ВМ стенда, срок жизни снимка — неделя"

  schedule_policy {
    # cron по UTC: минуты, часы, день месяца, месяц, день недели
    expression = "0 3 * * *"
  }

  # срок жизни снимка — одна неделя (7 суток).
  # Запись в часах и минутах, а не "168h" и не "1w": провайдер разбирает поле
  # как длительность Go («unknown unit "w"» на "1w") и хранит её в каноническом
  # виде, поэтому при короткой записи каждый plan показывал бы ложное изменение
  # "168h0m0s" -> "168h".
  retention_period = "168h0m0s"

  snapshot_spec {
    description = "Ежедневный снимок диска ВМ стенда (создан по расписанию)"
    labels = {
      flow = var.flow
      task = "backup"
    }
  }

  disk_ids = [
    yandex_compute_instance.bastion.boot_disk[0].disk_id,
    yandex_compute_instance.web_a.boot_disk[0].disk_id,
    yandex_compute_instance.web_b.boot_disk[0].disk_id,
    yandex_compute_instance.zabbix.boot_disk[0].disk_id,
    yandex_compute_instance.elasticsearch.boot_disk[0].disk_id,
    yandex_compute_instance.kibana.boot_disk[0].disk_id,
  ]
}
