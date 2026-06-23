import requests
import hashlib
import os
from config import Config


class CatAPI:
    """Класс для работы с API cataas.com"""

    @staticmethod
    def get_cat_image(text: str) -> tuple:
        """
        Получает картинку кота с текстом от cataas.com

        Args:
            text: Текст, который будет на картинке

        Returns:
            tuple: (изображение в байтах, имя файла)
        """
        url = f"{Config.CAT_API_URL}/says/{text}"
        params = {
            'fontSize': 50,
            'fontColor': 'white',
            'type': 'png'
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            # Генерируем имя файла на основе текста
            safe_filename = CatAPI._sanitize_filename(text)
            filename = f"{safe_filename}.png"

            return response.content, filename

        except requests.exceptions.RequestException as e:
            print(f"Ошибка при получении картинки: {e}")
            return None, None

    @staticmethod
    def _sanitize_filename(text: str) -> str:
        """Преобразует текст в безопасное имя файла"""
        # Удаляем недопустимые символы
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            text = text.replace(char, '')
        # Ограничиваем длину
        return text[:50] if len(text) > 50 else text