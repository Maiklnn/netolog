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

    # 🔽 ИСПРАВЛЕНИЕ: лектор НЕ может выставлять оценки студентам
    def rate_hw(self, student, course, grade):
        return 'Ошибка: лектор не имеет права выставлять оценки за домашние задания'

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


# Функции для подсчета средних оценок
def average_student_grade_for_course(students_list, course_name):
    if not students_list:
        return 0
    all_grades = []
    for student in students_list:
        if isinstance(student, Student) and course_name in student.grades:
            all_grades.extend(student.grades[course_name])
    if not all_grades:
        return 0
    return sum(all_grades) / len(all_grades)


def average_lecturer_grade_for_course(lecturers_list, course_name):
    if not lecturers_list:
        return 0
    all_grades = []
    for lecturer in lecturers_list:
        if isinstance(lecturer, Lecturer) and course_name in lecturer.grades:
            all_grades.extend(lecturer.grades[course_name])
    if not all_grades:
        return 0
    return sum(all_grades) / len(all_grades)
