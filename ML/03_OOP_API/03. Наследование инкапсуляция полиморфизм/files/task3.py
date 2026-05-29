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
        """Сравнение студентов по средней оценке (<)"""
        if not isinstance(other, Student):
            return NotImplemented
        return self.get_average_grade() < other.get_average_grade()

    def __le__(self, other):
        """Сравнение студентов по средней оценке (<=)"""
        if not isinstance(other, Student):
            return NotImplemented
        return self.get_average_grade() <= other.get_average_grade()

    def __gt__(self, other):
        """Сравнение студентов по средней оценке (>)"""
        if not isinstance(other, Student):
            return NotImplemented
        return self.get_average_grade() > other.get_average_grade()

    def __ge__(self, other):
        """Сравнение студентов по средней оценке (>=)"""
        if not isinstance(other, Student):
            return NotImplemented
        return self.get_average_grade() >= other.get_average_grade()

    def __eq__(self, other):
        """Сравнение студентов по средней оценке (==)"""
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
        else:
            return 'Ошибка'


class Lecturer(Mentor):
    """Класс Lecturer - лектор, получает оценки от студентов"""

    def __init__(self, name, surname):
        super().__init__(name, surname)
        self.grades = {}  # Словарь для хранения оценок от студентов

    def get_average_grade(self):
        """Метод для подсчета средней оценки за лекции"""
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
        """Сравнение лекторов по средней оценке (<)"""
        if not isinstance(other, Lecturer):
            return NotImplemented
        return self.get_average_grade() < other.get_average_grade()

    def __le__(self, other):
        """Сравнение лекторов по средней оценке (<=)"""
        if not isinstance(other, Lecturer):
            return NotImplemented
        return self.get_average_grade() <= other.get_average_grade()

    def __gt__(self, other):
        """Сравнение лекторов по средней оценке (>)"""
        if not isinstance(other, Lecturer):
            return NotImplemented
        return self.get_average_grade() > other.get_average_grade()

    def __ge__(self, other):
        """Сравнение лекторов по средней оценке (>=)"""
        if not isinstance(other, Lecturer):
            return NotImplemented
        return self.get_average_grade() >= other.get_average_grade()

    def __eq__(self, other):
        """Сравнение лекторов по средней оценке (==)"""
        if not isinstance(other, Lecturer):
            return NotImplemented
        return self.get_average_grade() == other.get_average_grade()


class Reviewer(Mentor):
    """Класс Reviewer - ревьюер, выставляет оценки студентам"""

    def __str__(self):
        return (f"Имя: {self.name}\n"
                f"Фамилия: {self.surname}")


# Пример использования и тестирования
if __name__ == "__main__":
    # Создаем студентов
    student1 = Student('Ruoy', 'Eman', 'male')
    student1.courses_in_progress += ['Python', 'Git']
    student1.finished_courses += ['Введение в программирование']
    student1.grades = {'Python': [10, 9, 8], 'Git': [9, 9, 10]}

    student2 = Student('Anna', 'Smith', 'female')
    student2.courses_in_progress += ['Python', 'Java']
    student2.finished_courses += ['Основы программирования']
    student2.grades = {'Python': [8, 7, 9], 'Java': [9, 8, 8]}

    # Создаем лекторов
    lecturer1 = Lecturer('John', 'Doe')
    lecturer1.courses_attached += ['Python', 'Git']
    lecturer1.grades = {'Python': [9, 10, 8, 9], 'Git': [10, 9, 9]}

    lecturer2 = Lecturer('Jane', 'Smith')
    lecturer2.courses_attached += ['Python', 'Java']
    lecturer2.grades = {'Python': [7, 8, 9, 8], 'Java': [9, 8, 7]}

    # Создаем ревьюера
    reviewer = Reviewer('Some', 'Buddy')
    reviewer.courses_attached += ['Python']

    # Тестируем __str__
    print("=== Тестирование вывода ===")
    print("Ревьюер:")
    print(reviewer)
    print()

    print("Лектор 1:")
    print(lecturer1)
    print()

    print("Лектор 2:")
    print(lecturer2)
    print()

    print("Студент 1:")
    print(student1)
    print()

    print("Студент 2:")
    print(student2)
    print()

    # Тестируем сравнение лекторов
    print("=== Сравнение лекторов ===")
    print(f"Средняя оценка лектора 1: {lecturer1.get_average_grade():.2f}")
    print(f"Средняя оценка лектора 2: {lecturer2.get_average_grade():.2f}")
    print(f"lecturer1 > lecturer2: {lecturer1 > lecturer2}")
    print(f"lecturer1 < lecturer2: {lecturer1 < lecturer2}")
    print(f"lecturer1 == lecturer2: {lecturer1 == lecturer2}")
    print()

    # Тестируем сравнение студентов
    print("=== Сравнение студентов ===")
    print(f"Средняя оценка студента 1: {student1.get_average_grade():.2f}")
    print(f"Средняя оценка студента 2: {student2.get_average_grade():.2f}")
    print(f"student1 > student2: {student1 > student2}")
    print(f"student1 < student2: {student1 < student2}")
    print(f"student1 == student2: {student1 == student2}")
