Установить terraform скачиваем с зеркала https://hashicorp-releases.yandexcloud.net/terraform/
установка на linux
скачиваем wget https://hashicorp-releases.yandexcloud.net/terraform/1.16.0/terraform_1.16.0_linux_amd64.zip
распаковываем unzip terraform_1.16.0_linux_amd64.zip
устанавливаем mv terraform /usr/bin/terraform
проверка версии terraform --version

Для того чтобы провайдер работал с яндекс зеркала .terraformrc разместить в домашнем каталоге пользоваетеля

инициализируем проэкт terraform init
