def merge_files_by_lines_count(input_files, output_file):
    """
    Объединяет файлы, сортируя по количеству строк
    """
    # Читаем все файлы и сохраняем информацию
    files_data = []

    for file_path in input_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                files_data.append({
                    'name': file_path,
                    'lines_count': len(lines),
                    'content': lines
                })
        except FileNotFoundError:
            print(f"Ошибка: файл {file_path} не найден")
            continue

    # Сортируем по количеству строк
    files_data.sort(key=lambda x: x['lines_count'])

    # Записываем в выходной файл
    with open(output_file, 'w', encoding='utf-8') as out_f:
        for file_data in files_data:
            out_f.write(f"{file_data['name']}\n")
            out_f.write(f"{file_data['lines_count']}\n")
            out_f.writelines(file_data['content'])


# Пример использования
if __name__ == "__main__":
    # Список файлов для объединения
    files = ['1.txt', '2.txt', '3.txt']

    # Объединяем файлы
    merge_files_by_lines_count(files, 'result.txt')

    # Проверяем результат
    with open('result.txt', 'r', encoding='utf-8') as f:
        print(f.read())