class Student:
    def __init__(self, name, surname, gender):
        self.name = name
        self.surname = surname
        self.gender = gender
        self.finished_courses = []
        self.courses_in_progress = []
        self.grades = {}

    def rate_lecture(self, lecturer, course, grade):
        """Метод для выставления оценки лектору студентом"""
        if not isinstance(grade, (int, float)) or grade < 0 or grade > 10:
            return 'Ошибка: оценка должна быть от 0 до 10'

        if not isinstance(lecturer, Lecturer):
            return 'Ошибка: можно оценивать только лекторов'

        if course not in self.courses_in_progress and course not in self.finished_courses:
            return f'Ошибка: вы не изучаете курс {course}'

        if course not in lecturer.courses_attached:
            return f'Ошибка: лектор не ведет курс {course}'

        if course in lecturer.grades:
            lecturer.grades[course].append(grade)
        else:
            lecturer.grades[course] = [grade]

    def get_average_grade(self):
        """Метод для подсчета средней оценки за домашние задания"""
        if not self.grades:
            return 0

        all_grades = []
        for grades_list in self.grades.values():
            all_grades.extend(grades_list)

        if not all_grades:
            return 0

        return sum(all_grades) / len(all_grades)

    def __str__(self):
        avg_grade = self.get_average_grade()
        courses_in_progress_str = ", ".join(self.courses_in_progress)
        finished_courses_str = ", ".join(self.finished_courses) if self.finished_courses else "Нет"

        return (f"Имя: {self.name}\n"
                f"Фамилия: {self.surname}\n"
                f"Средняя оценка за домашние задания: {avg_grade:.1f}\n"
                f"Курсы в процессе изучения: {courses_in_progress_str}\n"
                f"Завершенные курсы: {finished_courses_str}")

    def __lt__(self, other):
        if not isinstance(other, Student):
            return NotImplemented
        return self.get_average_grade() < other.get_average_grade()

    def __le__(self, other):
        if not isinstance(other, Student):
            return NotImplemented
        return self.get_average_grade() <= other.get_average_grade()

    def __gt__(self, other):
        if not isinstance(other, Student):
            return NotImplemented
        return self.get_average_grade() > other.get_average_grade()

    def __ge__(self, other):
        if not isinstance(other, Student):
            return NotImplemented
        return self.get_average_grade() >= other.get_average_grade()

    def __eq__(self, other):
        if not isinstance(other, Student):
            return NotImplemented
        return self.get_average_grade() == other.get_average_grade()


class Mentor:
    def __init__(self, name, surname):
        self.name = name
        self.surname = surname
        self.courses_attached = []

    def rate_hw(self, student, course, grade):
        if isinstance(student, Student) and course in self.courses_attached and course in student.courses_in_progress:
            if course in student.grades:
                student.grades[course] += [grade]
            else:
                student.grades[course] = [grade]
            return f'Оценка {grade} за ДЗ по курсу {course} выставлена студенту {student.name} {student.surname}'
        else:
            return 'Ошибка'


class Lecturer(Mentor):
    def __init__(self, name, surname):
        super().__init__(name, surname)
        self.grades = {}

    def get_average_grade(self):
        if not self.grades:
            return 0

        all_grades = []
        for grades_list in self.grades.values():
            all_grades.extend(grades_list)

        if not all_grades:
            return 0

        return sum(all_grades) / len(all_grades)

    def __str__(self):
        avg_grade = self.get_average_grade()
        return (f"Имя: {self.name}\n"
                f"Фамилия: {self.surname}\n"
                f"Средняя оценка за лекции: {avg_grade:.1f}")

    def __lt__(self, other):
        if not isinstance(other, Lecturer):
            return NotImplemented
        return self.get_average_grade() < other.get_average_grade()

    def __le__(self, other):
        if not isinstance(other, Lecturer):
            return NotImplemented
        return self.get_average_grade() <= other.get_average_grade()

    def __gt__(self, other):
        if not isinstance(other, Lecturer):
            return NotImplemented
        return self.get_average_grade() > other.get_average_grade()

    def __ge__(self, other):
        if not isinstance(other, Lecturer):
            return NotImplemented
        return self.get_average_grade() >= other.get_average_grade()

    def __eq__(self, other):
        if not isinstance(other, Lecturer):
            return NotImplemented
        return self.get_average_grade() == other.get_average_grade()


class Reviewer(Mentor):
    def __str__(self):
        return (f"Имя: {self.name}\n"
                f"Фамилия: {self.surname}")


# Функция для подсчета средней оценки за ДЗ по всем студентам в рамках курса
def average_student_grade_for_course(students_list, course_name):
    """
    Подсчитывает среднюю оценку за домашние задания по всем студентам в рамках конкретного курса

    Args:
        students_list: список студентов
        course_name: название курса

    Returns:
        float: средняя оценка или 0, если оценок нет
    """
    if not students_list:
        return 0

    all_grades = []
    for student in students_list:
        if isinstance(student, Student) and course_name in student.grades:
            all_grades.extend(student.grades[course_name])

    if not all_grades:
        return 0

    return sum(all_grades) / len(all_grades)


# Функция для подсчета средней оценки за лекции всех лекторов в рамках курса
def average_lecturer_grade_for_course(lecturers_list, course_name):
    """
    Подсчитывает среднюю оценку за лекции всех лекторов в рамках курса

    Args:
        lecturers_list: список лекторов
        course_name: название курса

    Returns:
        float: средняя оценка или 0, если оценок нет
    """
    if not lecturers_list:
        return 0

    all_grades = []
    for lecturer in lecturers_list:
        if isinstance(lecturer, Lecturer) and course_name in lecturer.grades:
            all_grades.extend(lecturer.grades[course_name])

    if not all_grades:
        return 0

    return sum(all_grades) / len(all_grades)


# Создание экземпляров классов
print("=" * 60)
print("СОЗДАНИЕ ЭКЗЕМПЛЯРОВ КЛАССОВ")
print("=" * 60)

# Создаем 2 ревьюеров
reviewer1 = Reviewer('Иван', 'Иванов')
reviewer1.courses_attached = ['Python', 'Java', 'Git']

reviewer2 = Reviewer('Петр', 'Петров')
reviewer2.courses_attached = ['Python', 'C++', 'JavaScript']

print("Созданы ревьюеры:")
print(reviewer1)
print()
print(reviewer2)
print()

# Создаем 2 лекторов
lecturer1 = Lecturer('Алексей', 'Смирнов')
lecturer1.courses_attached = ['Python', 'Git', 'Алгоритмы']

lecturer2 = Lecturer('Елена', 'Козлова')
lecturer2.courses_attached = ['Python', 'Java', 'Базы данных']

print("Созданы лекторы:")
print(lecturer1)
print()
print(lecturer2)
print()

# Создаем 2 студентов
student1 = Student('Ольга', 'Алёхина', 'Ж')
student1.courses_in_progress = ['Python', 'Git']
student1.finished_courses = ['Введение в программирование']

student2 = Student('Дмитрий', 'Соколов', 'М')
student2.courses_in_progress = ['Python', 'Java']
student2.finished_courses = ['Основы алгоритмов']

print("Созданы студенты:")
print(student1)
print()
print(student2)
print()

# Вызов всех методов
print("=" * 60)
print("ВЫЗОВ МЕТОДОВ")
print("=" * 60)

# 1. Метод rate_hw у ревьюера (выставление оценок студентам)
print("1. Выставление оценок студентам (метод rate_hw):")
print(reviewer1.rate_hw(student1, 'Python', 10))
print(reviewer1.rate_hw(student1, 'Python', 9))
print(reviewer1.rate_hw(student1, 'Git', 8))
print(reviewer2.rate_hw(student2, 'Python', 7))
print(reviewer2.rate_hw(student2, 'Java', 9))
print(reviewer2.rate_hw(student2, 'Java', 8))
print()

# 2. Метод rate_lecture у студентов (выставление оценок лекторам)
print("2. Выставление оценок лекторам (метод rate_lecture):")
print(student1.rate_lecture(lecturer1, 'Python', 9))
print(student1.rate_lecture(lecturer1, 'Python', 10))
print(student1.rate_lecture(lecturer1, 'Git', 8))
print(student2.rate_lecture(lecturer2, 'Python', 7))
print(student2.rate_lecture(lecturer2, 'Java', 9))
print(student2.rate_lecture(lecturer2, 'Java', 8))
print()

# 3. Метод get_average_grade у студентов
print("3. Средние оценки студентов:")
print(f"Средняя оценка {student1.name} {student1.surname}: {student1.get_average_grade():.2f}")
print(f"Средняя оценка {student2.name} {student2.surname}: {student2.get_average_grade():.2f}")
print()

# 4. Метод get_average_grade у лекторов
print("4. Средние оценки лекторов:")
print(f"Средняя оценка {lecturer1.name} {lecturer1.surname}: {lecturer1.get_average_grade():.2f}")
print(f"Средняя оценка {lecturer2.name} {lecturer2.surname}: {lecturer2.get_average_grade():.2f}")
print()

# 5. Сравнение студентов (магические методы)
print("5. Сравнение студентов:")
print(f"{student1.name} > {student2.name}: {student1 > student2}")
print(f"{student1.name} < {student2.name}: {student1 < student2}")
print(f"{student1.name} == {student2.name}: {student1 == student2}")
print()

# 6. Сравнение лекторов (магические методы)
print("6. Сравнение лекторов:")
print(f"{lecturer1.name} > {lecturer2.name}: {lecturer1 > lecturer2}")
print(f"{lecturer1.name} < {lecturer2.name}: {lecturer1 < lecturer2}")
print(f"{lecturer1.name} == {lecturer2.name}: {lecturer1 == lecturer2}")
print()

# 7. Вывод информации через __str__
print("7. Полная информация об объектах через __str__:")
print("Студент 1:")
print(student1)
print()
print("Студент 2:")
print(student2)
print()
print("Лектор 1:")
print(lecturer1)
print()
print("Лектор 2:")
print(lecturer2)
print()
print("Ревьюер 1:")
print(reviewer1)
print()
print("Ревьюер 2:")
print(reviewer2)
print()

# Использование функций для подсчета средних оценок
print("=" * 60)
print("ФУНКЦИИ ДЛЯ ПОДСЧЕТА СРЕДНИХ ОЦЕНОК")
print("=" * 60)

# Функция 1: средняя оценка за ДЗ по всем студентам в рамках курса
students_list = [student1, student2]

print("Функция 1: Средняя оценка за домашние задания по курсу")
print("-" * 50)

for course in ['Python', 'Git', 'Java', 'C++']:
    avg = average_student_grade_for_course(students_list, course)
    if avg > 0:
        print(f"Курс '{course}': {avg:.2f}")
    else:
        print(f"Курс '{course}': нет оценок")

print()

# Функция 2: средняя оценка за лекции всех лекторов в рамках курса
lecturers_list = [lecturer1, lecturer2]

print("Функция 2: Средняя оценка за лекции всех лекторов по курсу")
print("-" * 50)

for course in ['Python', 'Git', 'Java', 'Алгоритмы']:
    avg = average_lecturer_grade_for_course(lecturers_list, course)
    if avg > 0:
        print(f"Курс '{course}': {avg:.2f}")
    else:
        print(f"Курс '{course}': нет оценок")

print()

# Дополнительная демонстрация работы функций
print("=" * 60)
print("ДОПОЛНИТЕЛЬНАЯ ДЕМОНСТРАЦИЯ")
print("=" * 60)

# Добавляем больше оценок для наглядности
print("Добавляем еще оценки...")
student1.rate_lecture(lecturer1, 'Алгоритмы', 10)
lecturer1.rate_hw(student1, 'Python', 10)
reviewer1.rate_hw(student1, 'Python', 10)

print("\nОбновленная средняя оценка за лекции по курсу 'Python':")
avg_lecture_python = average_lecturer_grade_for_course(lecturers_list, 'Python')
print(f"Средняя оценка лекторов по курсу Python: {avg_lecture_python:.2f}")

print("\nОбновленная средняя оценка за ДЗ по курсу 'Python':")
avg_student_python = average_student_grade_for_course(students_list, 'Python')
print(f"Средняя оценка студентов по курсу Python: {avg_student_python:.2f}")

