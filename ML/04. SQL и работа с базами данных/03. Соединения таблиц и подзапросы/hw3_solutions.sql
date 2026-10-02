-- ============================================================================
-- ДОМАШНЕЕ ЗАДАНИЕ №3. «Соединения таблиц и подзапросы»
-- База: dvd-rental (схема public базы postgres)
--
-- Использованы только операторы и функции занятий 1-3:
--   занятия 1-2 : SELECT, WHERE, DISTINCT, ORDER BY, LIMIT, LIKE, ||, ROUND,
--                 даты (::date, date_trunc, date_part), jsonb-операторы,
--                 массивы (индексация, срез, array_agg, string_agg, unnest),
--                 агрегаты, GROUP BY, HAVING, CASE
--   занятие 3   : все виды JOIN (inner / left / right / full / cross, using),
--                 соединение таблицы с самой собой, подзапросы (скалярные,
--                 в IN, в EXISTS, во FROM/JOIN), LATERAL, UNION
-- ============================================================================

SET client_encoding = 'UTF8';
SET search_path TO public;

-- ============================================================================
-- ОСНОВНАЯ ЧАСТЬ
-- ============================================================================

-- ---------------------------------------------------------------------------
-- ЗАДАНИЕ №1. Для каждого покупателя: адрес, город и страна проживания
-- Цепочка: customer -> address -> city -> country
-- ---------------------------------------------------------------------------
SELECT c.first_name AS "Имя пользователя",
       c.last_name  AS "Фамилия пользователя",
       a.address    AS "Адрес",
       ci.city      AS "Город",
       co.country   AS "Страна"
FROM customer c
JOIN address a  ON a.address_id = c.address_id
JOIN city ci    ON ci.city_id = a.city_id
JOIN country co ON co.country_id = ci.country_id
ORDER BY c.customer_id;


-- ---------------------------------------------------------------------------
-- ЗАДАНИЕ №2.1. Количество покупателей по каждому магазину
-- ---------------------------------------------------------------------------
SELECT s.store_id            AS "Идентификатор магазина",
       count(c.customer_id)  AS "Количество прикрепленных пользователей"
FROM store s
LEFT JOIN customer c ON c.store_id = s.store_id
GROUP BY s.store_id
ORDER BY s.store_id;


-- ---------------------------------------------------------------------------
-- ЗАДАНИЕ №2.2. Только магазины, где покупателей больше 300
-- Фильтрация сгруппированных строк — через HAVING по агрегатной функции
-- ---------------------------------------------------------------------------
SELECT s.store_id           AS "Идентификатор магазина",
       count(c.customer_id) AS "Количество прикрепленных пользователей"
FROM store s
LEFT JOIN customer c ON c.store_id = s.store_id
GROUP BY s.store_id
HAVING count(c.customer_id) > 300
ORDER BY s.store_id;


-- ---------------------------------------------------------------------------
-- ЗАДАНИЕ №2.3. Добавляем город магазина и продавца, который в нём работает
-- ---------------------------------------------------------------------------
SELECT st.last_name || ' ' || st.first_name AS "Фамилия и имя сотрудника",
       s.store_id                           AS "Идентификатор магазина",
       ci.city                              AS "Город нахождения магазина",
       count(c.customer_id)                 AS "Количество прикрепленных пользователей"
FROM store s
JOIN staff st     ON st.store_id = s.store_id
JOIN address a    ON a.address_id = s.address_id
JOIN city ci      ON ci.city_id = a.city_id
LEFT JOIN customer c ON c.store_id = s.store_id
GROUP BY s.store_id, st.last_name, st.first_name, ci.city
HAVING count(c.customer_id) > 300
ORDER BY s.store_id;


-- ---------------------------------------------------------------------------
-- ЗАДАНИЕ №3. Сколько раз брали в прокат каждый фильм с актрисами по имени Julia
-- Список «фильмов с Julia» получаем подзапросом с IN; дальше считаем аренды
-- через цепочку inventory -> rental.
-- ---------------------------------------------------------------------------
SELECT f.title            AS "Название фильма",
       count(r.rental_id) AS "Количество аренд"
FROM film f
JOIN inventory i ON i.film_id = f.film_id
JOIN rental r    ON r.inventory_id = i.inventory_id
WHERE f.film_id IN (
        SELECT fa.film_id
        FROM film_actor fa
        JOIN actor a ON a.actor_id = fa.actor_id
        WHERE a.first_name = 'JULIA'
      )
GROUP BY f.film_id, f.title
ORDER BY f.title;


-- ---------------------------------------------------------------------------
-- ЗАДАНИЕ №4. Четыре показателя по каждому покупателю
-- Соединяем rental и payment по rental_id (иначе платежи размножатся).
-- ---------------------------------------------------------------------------
SELECT c.last_name || ' ' || c.first_name AS "Фамилия и имя пользователя",
       count(r.rental_id)                 AS "Количество арендованных фильмов",
       round(sum(p.amount))               AS "Округленная сумма платежей",
       min(p.amount)                      AS "Минимальный платеж",
       max(p.amount)                      AS "Максимальный платеж"
FROM customer c
JOIN rental r  ON r.customer_id = c.customer_id
JOIN payment p ON p.rental_id = r.rental_id
GROUP BY c.customer_id, c.last_name, c.first_name
ORDER BY c.customer_id;


-- ---------------------------------------------------------------------------
-- ЗАДАНИЕ №5. Все возможные пары городов с разными названиями
-- Декартово произведение таблицы city на саму себя + отсечение пар
-- с одинаковыми названиями.
-- ---------------------------------------------------------------------------
SELECT c1.city AS "Город 1",
       c2.city AS "Город 2"
FROM city c1, city c2
WHERE c1.city <> c2.city
ORDER BY c1.city, c2.city;


-- ---------------------------------------------------------------------------
-- ЗАДАНИЕ №6. Самая и самая невостребованная категории фильмов
-- Ровно два подзапроса (ветви UNION): топ-1 по убыванию и топ-1 по возрастанию
-- количества аренд. Каждая таблица использована не более двух раз, CTE нет.
-- ---------------------------------------------------------------------------
(
    SELECT cat."name"          AS "Название категории",
           count(r.rental_id)  AS "Количество аренд",
           sum(p.amount)       AS "Сумма продаж"
    FROM category cat
    JOIN film_category fc ON fc.category_id = cat.category_id
    JOIN inventory inv    ON inv.film_id = fc.film_id
    JOIN rental r         ON r.inventory_id = inv.inventory_id
    JOIN payment p        ON p.rental_id = r.rental_id
    GROUP BY cat.category_id, cat."name"
    ORDER BY count(r.rental_id) DESC
    LIMIT 1
)
UNION
(
    SELECT cat."name"          AS "Название категории",
           count(r.rental_id)  AS "Количество аренд",
           sum(p.amount)       AS "Сумма продаж"
    FROM category cat
    JOIN film_category fc ON fc.category_id = cat.category_id
    JOIN inventory inv    ON inv.film_id = fc.film_id
    JOIN rental r         ON r.inventory_id = inv.inventory_id
    JOIN payment p        ON p.rental_id = r.rental_id
    GROUP BY cat.category_id, cat."name"
    ORDER BY count(r.rental_id) ASC
    LIMIT 1
)
ORDER BY "Количество аренд" DESC;


-- ============================================================================
-- ДОПОЛНИТЕЛЬНАЯ ЧАСТЬ
-- ============================================================================

-- ---------------------------------------------------------------------------
-- ДОП. №1. По каждому фильму: сколько раз брали в аренду и общая стоимость
-- аренды за всё время.
-- Агрегаты вынесены в два подзапроса (по арендам и по платежам) и
-- присоединены через LEFT JOIN — так фильмы без дисков тоже попадут в отчёт
-- (у них количество аренд и платежи будут NULL).
-- ---------------------------------------------------------------------------
SELECT f.title    AS "Название фильма",
       f.rating   AS "Рейтинг фильма",
       l."name"   AS "Язык фильма",
       cat."name" AS "Категория фильма",
       rc.cnt     AS "Количество аренд фильма",
       ps.total   AS "Общий размер платежей по фильму"
FROM film f
JOIN "language" l      ON l.language_id = f.language_id
JOIN film_category fc  ON fc.film_id = f.film_id
JOIN category cat      ON cat.category_id = fc.category_id
LEFT JOIN (
    SELECT inv.film_id,
           count(r.rental_id) AS cnt
    FROM inventory inv
    JOIN rental r ON r.inventory_id = inv.inventory_id
    GROUP BY inv.film_id
) rc ON rc.film_id = f.film_id
LEFT JOIN (
    SELECT inv.film_id,
           sum(p.amount) AS total
    FROM inventory inv
    JOIN rental r  ON r.inventory_id = inv.inventory_id
    JOIN payment p ON p.rental_id = r.rental_id
    GROUP BY inv.film_id
) ps ON ps.film_id = f.film_id
ORDER BY f.title;


-- ---------------------------------------------------------------------------
-- ДОП. №2. Тот же отчёт, но только фильмы, отсутствующие на DVD-дисках
-- (для них в inventory нет ни одной записи — LATERAL-подзапрос вернёт 0 аренд).
-- ---------------------------------------------------------------------------
SELECT f.title    AS "Название фильма",
       f.rating   AS "Рейтинг фильма",
       l."name"   AS "Язык фильма",
       cat."name" AS "Категория фильма",
       t.cnt      AS "Количество аренд фильма",
       t.total    AS "Общий размер платежей по фильму"
FROM film f
JOIN "language" l      ON l.language_id = f.language_id
JOIN film_category fc  ON fc.film_id = f.film_id
JOIN category cat      ON cat.category_id = fc.category_id
LEFT JOIN LATERAL (
    SELECT count(r.rental_id) AS cnt,
           sum(p.amount)      AS total
    FROM inventory inv
    LEFT JOIN rental r  ON r.inventory_id = inv.inventory_id
    LEFT JOIN payment p ON p.rental_id = r.rental_id
    WHERE inv.film_id = f.film_id
) t ON true
WHERE t.cnt = 0
ORDER BY f.title;


-- ---------------------------------------------------------------------------
-- ДОП. №3. Массив индексов категории для каждого фильма.
-- Массив категорий — это array_agg(name ORDER BY category_id) по таблице
-- category (16 элементов). Индекс категории фильма в этом массиве равен
-- количеству категорий с не большим category_id, то есть позиции элемента.
-- Результат — массив (для фильма с одной категорией это один индекс).
-- ---------------------------------------------------------------------------
SELECT f.film_id AS "Идентификатор фильма",
       f.title   AS "Название фильма",
       array_agg(
           (SELECT count(*)
            FROM category c2
            WHERE c2.category_id <= cat.category_id)
           ORDER BY cat.category_id
       ) AS "Массив с индексами"
FROM film f
JOIN film_category fc ON fc.film_id = f.film_id
JOIN category cat     ON cat.category_id = fc.category_id
GROUP BY f.film_id, f.title
ORDER BY f.film_id;


-- ---------------------------------------------------------------------------
-- ДОП. №4 (высокий уровень сложности). Две самые любимые категории каждого
-- покупателя одной строкой. Оконные функции не используются: для каждого
-- покупателя LATERAL-подзапрос берёт топ-2 категории по числу аренд, а
-- string_agg собирает их названия в строку.
-- ---------------------------------------------------------------------------
SELECT c.customer_id AS "Идентификатор пользователя",
       t.cats        AS "Строка с названиями категорий"
FROM customer c
LEFT JOIN LATERAL (
    SELECT string_agg(x.cat, ', ' ORDER BY x.cnt DESC, x.cat) AS cats
    FROM (
        SELECT cat."name" AS cat,
               count(*)   AS cnt
        FROM rental r
        JOIN inventory i      ON i.inventory_id = r.inventory_id
        JOIN film_category fc ON fc.film_id = i.film_id
        JOIN category cat     ON cat.category_id = fc.category_id
        WHERE r.customer_id = c.customer_id
        GROUP BY cat."name"
        ORDER BY count(*) DESC, cat."name"
        LIMIT 2
    ) x
) t ON true
ORDER BY c.customer_id;
