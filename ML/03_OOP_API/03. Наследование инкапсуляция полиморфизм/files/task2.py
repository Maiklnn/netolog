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
        # Проверка корректности оценки (10-балльная шкала)
        if not isinstance(grade, (int, float)) or grade < 0 or grade > 10:
            return 'Ошибка: оценка должна быть от 0 до 10'

        # Проверка, что лектор является экземпляром класса Lecturer
        if not isinstance(lecturer, Lecturer):
            return 'Ошибка: можно оценивать только лекторов'

        # Проверка, что студент изучает этот курс
        if course not in self.courses_in_progress and course not in self.finished_courses:
            return f'Ошибка: вы не изучаете курс {course}'

        # Проверка, что лектор закреплен за этим курсом
        if course not in lecturer.courses_attached:
            return f'Ошибка: лектор не ведет курс {course}'

        # Добавление оценки лектору
        if course in lecturer.grades:
            lecturer.grades[course].append(grade)
        else:
            lecturer.grades[course] = [grade]

        # Функция ничего не возвращает (None), как в вашем примере для успешного случая
        # Но для наглядности можно вернуть None или сообщение

    def rate_lecturer(self, lecturer, course, grade):
        """Альтернативное название метода (если нужно)"""
        return self.rate_lecture(lecturer, course, grade)


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


class Reviewer(Mentor):
    """Класс Reviewer - ревьюер, выставляет оценки студентам"""
    pass


# Тестирование
lecturer = Lecturer('Иван', 'Иванов')
reviewer = Reviewer('Пётр', 'Петров')
student = Student('Алёхина', 'Ольга', 'Ж')

student.courses_in_progress += ['Python', 'Java']
lecturer.courses_attached += ['Python', 'C++']
reviewer.courses_attached += ['Python', 'C++']

# Тест 1: Успешное выставление оценки (метод ничего не возвращает -> None)
print(student.rate_lecture(lecturer, 'Python', 7))  # None

# Тест 2: Студент не изучает Java (нет в courses_in_progress)
print(student.rate_lecture(lecturer, 'Java', 8))  # Ошибка: вы не изучаете курс Java

# Тест 3: Проблема с написанием C++ (в примере кириллическая 'С')
# В lecturer.courses_attached 'C++' (латиница), а передается 'С++' (кириллица)
print(student.rate_lecture(lecturer, 'С++', 8))  # Ошибка: лектор не ведет курс С++

# Тест 4: Попытка оценить ревьюера вместо лектора
print(student.rate_lecture(reviewer, 'Python', 6))  # Ошибка: можно оценивать только лекторов

print(lecturer.grades)  # {'Python': [7]}
