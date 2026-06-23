import requests
import json
from config import Config


class YandexDisk:
    """Класс для работы с Яндекс.Диском"""

    def __init__(self):
        self.token = Config.YANDEX_DISK_TOKEN
        self.base_url = 'https://cloud-api.yandex.net/v1/disk'
        self.headers = {
            'Authorization': f'OAuth {self.token}',
            'Content-Type': 'application/json'
        }
        self.group_folder = Config.GROUP_NAME

    def create_folder(self) -> bool:
        """Создает папку на Яндекс.Диске"""
        url = f"{self.base_url}/resources"
        params = {'path': f'/{self.group_folder}'}

        try:
            response = requests.put(url, headers=self.headers, params=params)
            if response.status_code == 201:
                print(f"Папка '{self.group_folder}' успешно создана")
                return True
            elif response.status_code == 409:
                print(f"Папка '{self.group_folder}' уже существует")
                return True
            else:
                print(f"Ошибка создания папки: {response.json()}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при создании папки: {e}")
            return False

    def get_upload_url(self, filename: str) -> str:
        """Получает URL для загрузки файла"""
        url = f"{self.base_url}/resources/upload"
        path = f"/{self.group_folder}/{filename}"
        params = {'path': path, 'overwrite': True}

        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json().get('href')
        except requests.exceptions.RequestException as e:
            print(f"Ошибка получения URL для загрузки: {e}")
            return None

    def upload_file(self, file_content: bytes, filename: str) -> bool:
        """Загружает файл на Яндекс.Диск"""
        upload_url = self.get_upload_url(filename)
        if not upload_url:
            return False

        try:
            response = requests.put(upload_url, data=file_content)
            response.raise_for_status()
            print(f"Файл '{filename}' успешно загружен")
            return True
        except requests.exceptions.RequestException as e:
            print(f"Ошибка загрузки файла: {e}")
            return False

    def get_file_info(self, filename: str) -> dict:
        """Получает информацию о файле на Яндекс.Диске"""
        url = f"{self.base_url}/resources"
        path = f"/{self.group_folder}/{filename}"
        params = {'path': path}

        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            return {
                'name': data.get('name'),
                'size': data.get('size'),
                'created': data.get('created'),
                'modified': data.get('modified'),
                'mime_type': data.get('mime_type')
            }
        except requests.exceptions.RequestException as e:
            print(f"Ошибка получения информации о файле: {e}")
            return None