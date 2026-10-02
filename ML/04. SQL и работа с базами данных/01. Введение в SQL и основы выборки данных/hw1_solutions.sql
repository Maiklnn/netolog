-- ============================================================================
-- Домашнее задание №1. «Введение в SQL и основы выборки данных»
-- База: dvd-rental (схема public базы postgres)
-- Использованы только операторы/функции занятия №1: SELECT, DISTINCT, WHERE,
-- LIKE, ORDER BY, LIMIT, конкатенация ||, LENGTH, UPPER/LOWER, LEFT,
-- SUBSTRING, POSITION, ROUND, арифметика.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- ОСНОВНАЯ ЧАСТЬ
-- ---------------------------------------------------------------------------

-- Задание №1. Уникальные названия городов
SELECT DISTINCT city AS "Название города"
FROM city
ORDER BY city;

-- Задание №2. Города на "L", заканчиваются на "a", без пробелов
-- (без регулярных выражений — только LIKE)
SELECT DISTINCT city AS "Название города"
FROM city
WHERE city LIKE 'L%a'
  AND city NOT LIKE '% %'
ORDER BY city;

-- Задание №3. 10 последних платежей за прокат фильмов
-- Второй ключ сортировки нужен обязательно: у 182 платежей одинаковая
-- максимальная дата (2006-02-14 15:16:03), без него результат неустойчив.
SELECT *
FROM payment
ORDER BY payment_date DESC, payment_id DESC
LIMIT 10;

-- Задание №4. Информация по покупателям
SELECT
    last_name || ' ' || first_name                    AS "Фамилия и имя",
    email                                             AS "Email",
    SUBSTRING(email FROM POSITION('@' IN email))      AS "Домен",
    LENGTH(email)                                     AS "Количество символов"
FROM customer
ORDER BY last_name, first_name;

-- Задание №5. Активные покупатели KELLY и WILLIE, имя и фамилия в нижнем регистре
SELECT
    LOWER(last_name || ' ' || first_name) AS "Имя и фамилия",
    activebool                            AS "Флаг активности"
FROM customer
WHERE first_name IN ('KELLY', 'WILLIE')
  AND activebool = TRUE
ORDER BY 1;

-- Задание №6. Фильмы на "be", описание > 100 символов, rental_rate/length > 0.015
SELECT
    film_id                                   AS "Идентификатор фильма",
    title                                     AS "Название фильма",
    ROUND(film.rental_rate / film.length, 3)  AS "Отношение аренды к длительности"
FROM film
WHERE title ILIKE 'be%'
  AND LENGTH(description) > 100
  AND ROUND(film.rental_rate / film.length, 3) > 0.015
ORDER BY film_id;

-- ---------------------------------------------------------------------------
-- ДОПОЛНИТЕЛЬНАЯ ЧАСТЬ
-- ---------------------------------------------------------------------------

-- Доп. №1. R при аренде 0.00–3.00 включительно ИЛИ PG-13 при аренде >= 4.00
SELECT
    title       AS "Название фильма",
    rating      AS "Рейтинг",
    rental_rate AS "Стоимость аренды"
FROM film
WHERE (rating = 'R'     AND rental_rate BETWEEN 0.00 AND 3.00)
   OR (rating = 'PG-13' AND rental_rate >= 4.00)
ORDER BY rating, rental_rate, title;

-- Доп. №2. Три фильма с самым длинным описанием
SELECT
    title               AS "Название фильма",
    description         AS "Описание",
    LENGTH(description) AS "Количество символов"
FROM film
ORDER BY LENGTH(description) DESC
LIMIT 3;

-- Доп. №3. Email, разбитый на имя ящика и домен
SELECT
    email                                                   AS "Email",
    SUBSTRING(email FROM 1 FOR POSITION('@' IN email) - 1)  AS "Имя почтового ящика",
    SUBSTRING(email FROM POSITION('@' IN email) + 1)        AS "Домен"
FROM customer
ORDER BY customer_id;

-- Доп. №4. То же, но первая буква заглавная, остальные строчные
SELECT
    email AS "Email",
    UPPER(LEFT(SUBSTRING(email FROM 1 FOR POSITION('@' IN email) - 1), 1))
        || LOWER(SUBSTRING(email FROM 2 FOR POSITION('@' IN email) - 2))  AS "Имя почтового ящика",
    UPPER(LEFT(SUBSTRING(email FROM POSITION('@' IN email) + 1), 1))
        || LOWER(SUBSTRING(email FROM POSITION('@' IN email) + 2))        AS "Домен"
FROM customer
ORDER BY customer_id;
