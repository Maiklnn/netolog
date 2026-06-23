import json
import os
from datetime import datetime
from config import Config
from cat_api import CatAPI
from yandex_disk import YandexDisk


def save_backup_info(backup_data: list, filename: str = Config.OUTPUT_JSON):
    """
    Сохраняет информацию о бэкапе в JSON-файл

    Args:
        backup_data: Список с информацией о загруженных файлах
        filename: Имя JSON-файла
    """
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        print(f"\nИнформация о бэкапе сохранена в файл: {filename}")
    except Exception as e:
        print(f"Ошибка сохранения JSON: {e}")


def main():
    """Основная функция программы"""
    print("=" * 50)
    print("🐱 Резервное копирование картинок кошек в Яндекс.Диск")
    print("=" * 50)

    # Проверка конфигурации
    try:
        Config.validate()
    except ValueError as e:
        print(f"Ошибка: {e}")
        return

    # Ввод данных от пользователя
    text = input("\nВведите текст для картинки: ").strip()
    if not text:
        print("Ошибка: текст не может быть пустым!")
        return

    # Инициализация
    cat_api = CatAPI()
    yandex = YandexDisk()

    # Шаг 1: Создание папки на Яндекс.Диске
    print("\n📁 Создание папки на Яндекс.Диске...")
    if not yandex.create_folder():
        print("Не удалось создать папку. Программа завершена.")
        return

    # Шаг 2: Получение картинки
    print(f"\n📸 Получение картинки с текстом '{text}'...")
    image_data, filename = cat_api.get_cat_image(text)

    if image_data is None:
        print("Не удалось получить картинку. Проверьте подключение к интернету.")
        return

    print(f"Файл получен: {filename} (размер: {len(image_data)} байт)")

    # Шаг 3: Загрузка картинки на Яндекс.Диск
    print("\n☁️ Загрузка на Яндекс.Диск...")
    if not yandex.upload_file(image_data, filename):
        print("Не удалось загрузить файл на Яндекс.Диск.")
        return

    # Шаг 4: Получение информации о файле
    print("\n📋 Получение информации о файле...")
    file_info = yandex.get_file_info(filename)

    if file_info is None:
        print("Не удалось получить информацию о файле.")
        return

    # Шаг 5: Формирование данных для JSON
    backup_data = [{
        'text': text,
        'filename': filename,
        'size_bytes': file_info.get('size', 0),
        'size_kb': round(file_info.get('size', 0) / 1024, 2),
        'created': file_info.get('created'),
        'modified': file_info.get('modified'),
        'mime_type': file_info.get('mime_type'),
        'group': Config.GROUP_NAME,
        'backup_date': datetime.now().isoformat(),
        'yandex_disk_path': f"/{Config.GROUP_NAME}/{filename}"
    }]

    # Сохранение JSON
    save_backup_info(backup_data)

    # Вывод итоговой информации
    print("\n" + "=" * 50)
    print("✅ Резервное копирование успешно завершено!")
    print("=" * 50)
    print(f"📁 Группа: {Config.GROUP_NAME}")
    print(f"📄 Имя файла: {filename}")
    print(f"📦 Размер: {file_info.get('size', 0)} байт ({round(file_info.get('size', 0) / 1024, 2)} КБ)")
    print(f"📅 Дата создания: {file_info.get('created')}")
    print(f"📊 JSON-файл: {Config.OUTPUT_JSON}")
    print("=" * 50)


if __name__ == "__main__":
    main()