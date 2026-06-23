import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    YANDEX_DISK_TOKEN = os.getenv('YANDEX_DISK_TOKEN')
    GROUP_NAME = os.getenv('GROUP_NAME', 'default_group')
    CAT_API_URL = 'https://cataas.com/cat'
    OUTPUT_JSON = 'backup_info.json'

    @classmethod
    def validate(cls):
        if not cls.YANDEX_DISK_TOKEN:
            raise ValueError("Токен Яндекс.Диска не найден! Укажите его в файле .env")
        if not cls.GROUP_NAME:
            raise ValueError("Название группы не найдено! Укажите его в файле .env")