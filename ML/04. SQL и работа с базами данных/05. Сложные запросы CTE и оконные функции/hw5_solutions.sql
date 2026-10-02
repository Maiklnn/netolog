-- ============================================================================
-- ДОМАШНЕЕ ЗАДАНИЕ №5. «Сложные запросы: CTE и оконные функции»
-- База: dvd-rental (схема public базы postgres)
--
-- Использованы только операторы и функции занятий 1-5:
--   занятия 1-4 : SELECT / WHERE / GROUP BY / HAVING / ORDER BY, CASE, FILTER,
--                 coalesce, соединения таблиц, подзапросы, даты (date_trunc,
--                 date_part, ::date), агрегаты (sum, count, max, string_agg)
--   занятие 5   : оконные функции (OVER, PARTITION BY, ORDER BY, рамка окна),
--                 row_number / rank / dense_rank / lag / lead, оконные агрегаты,
--                 CTE (WITH), generate_series
-- ============================================================================

SET client_encoding = 'UTF8';
SET search_path TO public;

-- ============================================================================
-- ОСНОВНАЯ ЧАСТЬ
-- ============================================================================

-- ---------------------------------------------------------------------------
-- ЗАДАНИЕ №1. Четыре вычисляемые колонки к таблице payment
-- 1.1 нумерация всех платежей по дате платежа
-- 1.2 нумерация платежей отдельно для каждого покупателя по дате платежа
-- 1.3 нарастающий итог суммы платежей покупателя (сортировка: дата, затем
--     размер платежа от меньшего к большему)
-- 1.4 место платежа внутри покупателя по размеру платежа от большего к меньшему;
--     одинаковым суммам — одинаковый номер (rank)
-- Тай-брейк по payment_id добавлен, чтобы при совпадающих датах нумерация была
-- воспроизводимой: без него порядок строк внутри «ничьей» не определён.
-- ---------------------------------------------------------------------------
SELECT p.payment_id AS "Идентификатор платежа",
       p.payment_date AS "Дата платежа",
       p.customer_id  AS "Идентификатор пользователя",
       p.amount       AS "Размер платежа",

       row_number() OVER (
           ORDER BY p.payment_date, p.payment_id
       ) AS "Номер платежа по дате",

       row_number() OVER (
           PARTITION BY p.customer_id
           ORDER BY p.payment_date, p.payment_id
       ) AS "Номер платежа покупателя",

       sum(p.amount) OVER (
           PARTITION BY p.customer_id
           ORDER BY p.payment_date, p.amount
       ) AS "Нарастающий итог покупателя",

       rank() OVER (
           PARTITION BY p.customer_id
           ORDER BY p.amount DESC
       ) AS "Место платежа по размеру"
FROM payment p
ORDER BY p.payment_date, p.payment_id;


-- ---------------------------------------------------------------------------
-- ЗАДАНИЕ №2. Текущий платёж и платёж из предыдущей строки (по дате платежа),
-- для первого платежа покупателя предыдущий размер = 0.0
-- ---------------------------------------------------------------------------
SELECT p.payment_id  AS "Идентификатор платежа",
       p.payment_date AS "Дата платежа",
       p.customer_id  AS "Идентификатор пользователя",
       p.amount       AS "Текущий размер платежа",
       lag(p.amount, 1, 0.0) OVER (
           PARTITION BY p.customer_id
           ORDER BY p.payment_date, p.payment_id
       ) AS "Предыдущий размер платежа"
FROM payment p
ORDER BY p.customer_id, p.payment_date, p.payment_id;


-- ---------------------------------------------------------------------------
-- ЗАДАНИЕ №3. На сколько следующий платёж покупателя больше или меньше текущего
-- ---------------------------------------------------------------------------
SELECT p.payment_id  AS "Идентификатор платежа",
       p.payment_date AS "Дата платежа",
       p.customer_id  AS "Идентификатор пользователя",
       p.amount       AS "Текущий размер платежа",
       lead(p.amount) OVER (
           PARTITION BY p.customer_id
           ORDER BY p.payment_date, p.payment_id
       ) AS "Следующий размер платежа",
       lead(p.amount) OVER (
           PARTITION BY p.customer_id
           ORDER BY p.payment_date, p.payment_id
       ) - p.amount AS "Разница со следующим платежом"
FROM payment p
ORDER BY p.customer_id, p.payment_date, p.payment_id;


-- ---------------------------------------------------------------------------
-- ЗАДАНИЕ №4. Для каждого покупателя — данные о его последней оплате аренды
-- Нумеруем платежи покупателя от последнего к первому и берём строку с rn = 1.
-- ---------------------------------------------------------------------------
SELECT payment_id   AS "Идентификатор платежа",
       customer_id  AS "Идентификатор пользователя",
       staff_id     AS "Идентификатор сотрудника",
       rental_id    AS "Идентификатор аренды",
       amount       AS "Размер платежа",
       payment_date AS "Дата платежа"
FROM (
    SELECT p.*,
           row_number() OVER (
               PARTITION BY p.customer_id
               ORDER BY p.payment_date DESC, p.payment_id DESC
           ) AS rn
    FROM payment p
) t
WHERE rn = 1
ORDER BY customer_id;


-- ---------------------------------------------------------------------------
-- ЗАДАНИЕ №5. Одним запросом — месяц с наибольшей суммой платежей и разница
-- этой суммы с предыдущим месяцем.
-- Условия: payment использована строго один раз; топ-1 месяц — через оконную
-- функцию; при ничьей выводятся все месяцы, попавшие в топ-1.
-- Шаг 1 (cte months): одна агрегация по payment — суммы по месяцам.
-- Шаг 2 (cte ranked): окном считаем место месяца по сумме (rank) и сумму
--                     предыдущего месяца (lag). Ничья по сумме даёт одинаковый
--                     rank, поэтому «топ-1» вернёт сразу все такие месяцы.
-- ---------------------------------------------------------------------------
WITH months AS (
    SELECT date_trunc('month', p.payment_date)::date AS month_date,
           sum(p.amount)                             AS month_sum
    FROM payment p
    GROUP BY date_trunc('month', p.payment_date)
),
ranked AS (
    SELECT month_date,
           month_sum,
           lag(month_sum, 1, 0) OVER (ORDER BY month_date) AS prev_month_sum,
           rank() OVER (ORDER BY month_sum DESC)           AS month_rank
    FROM months
)
SELECT month_date              AS "Значение месяца",
       month_sum               AS "Сумма за месяц",
       prev_month_sum          AS "Сумма за предыдущий месяц",
       month_sum - prev_month_sum AS "Разница между суммами"
FROM ranked
WHERE month_rank = 1
ORDER BY month_date;


-- ============================================================================
-- ДОПОЛНИТЕЛЬНАЯ ЧАСТЬ
-- ============================================================================

-- ---------------------------------------------------------------------------
-- ДОП. №1. По каждому сотруднику — суммы продаж за август 2005 года по каждому
-- дню и накопительный итог по датам.
-- Внутренний sum(amount) считает сумму за день (GROUP BY сотрудник + дата),
-- внешний sum(...) OVER (...) — накопительный итог по датам внутри сотрудника.
-- ---------------------------------------------------------------------------
SELECT s.last_name || ' ' || s.first_name AS "Фамилия и имя сотрудника",
       p.payment_date::date               AS "Дата продажи",
       sum(p.amount)                      AS "Сумма продаж за день",
       sum(sum(p.amount)) OVER (
           PARTITION BY p.staff_id
           ORDER BY p.payment_date::date
       ) AS "Накопительный итог"
FROM payment p
JOIN staff s ON s.staff_id = p.staff_id
WHERE p.payment_date >= '2005-08-01' AND p.payment_date < '2005-09-01'
GROUP BY p.staff_id, s.last_name, s.first_name, p.payment_date::date
ORDER BY s.last_name, s.first_name, p.payment_date::date;


-- ---------------------------------------------------------------------------
-- ДОП. №2. Акция 20 августа 2005 года: скидку получал покупатель каждого сотого
-- платежа этого дня. Нумеруем все платежи дня по порядку и берём каждые 100.
-- ---------------------------------------------------------------------------
SELECT c.customer_id                  AS "Идентификатор пользователя",
       c.last_name || ' ' || c.first_name AS "Фамилия и имя пользователя"
FROM (
    SELECT p.customer_id,
           row_number() OVER (ORDER BY p.payment_date, p.payment_id) AS payment_number
    FROM payment p
    WHERE p.payment_date::date = '2005-08-20'
) pn
JOIN customer c ON c.customer_id = pn.customer_id
WHERE pn.payment_number % 100 = 0
ORDER BY c.customer_id;


-- ---------------------------------------------------------------------------
-- ДОП. №3. По каждой стране — три «лучших» покупателя одним запросом:
--   1) больше всех арендовал фильмов;
--   2) арендовал фильмов на самую большую сумму;
--   3) последним арендовал фильм.
-- По каждому показателю внутри страны считаем row_number() и оставляем первого;
-- ничьи разрешаются по алфавиту (фамилия и имя), то есть из нескольких
-- претендентов выводится один — этот вариант решения разрешён заданием.
-- Агрегаты аренд и платежей считаются в отдельных CTE: у двух аренд в базе
-- больше одного платежа, и соединение rental с payment «размножило» бы аренды.
-- Три результата сводятся в одну строку через max(...) FILTER (WHERE ...).
-- ---------------------------------------------------------------------------
WITH cust_base AS (
    SELECT c.customer_id,
           co.country_id,
           co.country                          AS country_name,
           c.last_name || ' ' || c.first_name  AS fio
    FROM customer c
    JOIN address a  ON a.address_id = c.address_id
    JOIN city ci    ON ci.city_id = a.city_id
    JOIN country co ON co.country_id = ci.country_id
),
rent_stat AS (
    SELECT customer_id,
           count(*)          AS rent_cnt,
           max(rental_date)  AS last_rental
    FROM rental
    GROUP BY customer_id
),
pay_stat AS (
    SELECT customer_id,
           sum(amount) AS pay_sum
    FROM payment
    GROUP BY customer_id
),
metrics AS (
    SELECT b.country_id,
           b.country_name,
           b.fio,
           coalesce(r.rent_cnt, 0) AS rent_cnt,
           coalesce(p.pay_sum, 0)  AS pay_sum,
           r.last_rental
    FROM cust_base b
    LEFT JOIN rent_stat r ON r.customer_id = b.customer_id
    LEFT JOIN pay_stat  p ON p.customer_id = b.customer_id
),
ranked AS (
    SELECT m.*,
           row_number() OVER (
               PARTITION BY country_id
               ORDER BY rent_cnt DESC, fio
           ) AS rn_cnt,
           row_number() OVER (
               PARTITION BY country_id
               ORDER BY pay_sum DESC, fio
           ) AS rn_sum,
           row_number() OVER (
               PARTITION BY country_id
               ORDER BY last_rental DESC NULLS LAST, fio
           ) AS rn_last
    FROM metrics m
)
SELECT country_name AS "Название страны",
       max(fio) FILTER (WHERE rn_cnt = 1)  AS "Лучший по количеству фильмов",
       max(fio) FILTER (WHERE rn_sum = 1)  AS "Лучший по сумме платежей",
       max(fio) FILTER (WHERE rn_last = 1) AS "Последним арендовал фильм"
FROM ranked
GROUP BY country_id, country_name
ORDER BY country_name;
