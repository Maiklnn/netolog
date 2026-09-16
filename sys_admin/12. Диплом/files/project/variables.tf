
variable "flow" {
  type    = string
  default = "24-01"
}

variable "cloud_id" {
  type    = string
  default = "b1go3k4pjd6ivbe0andm"
}
variable "folder_id" {
  type    = string
  default = "b1ghipgmhs5950r1vdu5"
}

variable "test" {
  type = map(number)
  default = {
    cores         = 2
    memory        = 2
    core_fraction = 20
  }
}

# Прерываемые ВМ живут не больше 24 часов.
# Перед сдачей работы дипломному руководителю переключить на false:
#   terraform apply -var="preemptible=false"
variable "preemptible" {
  type    = bool
  default = true
}

# Elasticsearch и Kibana требуют больше памяти, чем остальные ВМ стенда, поэтому
# у них отдельные размеры. Требование задания — минимальные конфигурации — здесь
# выдержано настолько, насколько это возможно: ядра 2 по 20 % Intel Ice Lake и
# прерываемость те же, отличаются только память и диск:
#  * Elasticsearch хранит индексы журналов nginx и выполняет поиск. На 2 ГБ он
#    работает на пределе (JVM-куча минимум 1 ГБ, плюс файловый кеш) и регулярно
#    уходит в отказы индексации, поэтому 4 ГБ и диск 20 ГБ — под сами индексы
#    (в 10 ГБ журналы nginx и служебные индексы не помещаются);
#  * Kibana — приложение на Node.js, ему хватает 2 ГБ и 10 ГБ диска.
variable "elasticsearch" {
  type = map(number)
  default = {
    cores         = 2
    memory        = 4
    core_fraction = 20
    disk          = 20
  }
}

variable "kibana" {
  type = map(number)
  default = {
    cores         = 2
    memory        = 2
    core_fraction = 20
    disk          = 10
  }
}
