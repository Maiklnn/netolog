-- =====================================================================
--  ДОМАШНЕЕ ЗАДАНИЕ №6
--  «Производительность: представления, индексы и анализ запросов»
--  База данных: dvd-rental, схема public
--
--  Использованы операторы и функции, пройденные на занятиях 1-6:
--    select / join / group by / having / подзапросы / CTE (with) /
--    оконные функции (row_number, rank, lag) / distinct on /
--    create view / create materialized view / refresh materialized view /
--    explain [analyze] / pg_size_pretty, pg_total_relation_size, pg_class.
-- =====================================================================

SET client_encoding = 'UTF8';
SET search_path TO public;


-- =====================================================================
--  ОСНОВНАЯ ЧАСТЬ
-- =====================================================================

-- ---------------------------------------------------------------------
-- ЗАДАНИЕ 1.1. Для каждого сотрудника выведите информацию о его первой
-- продаже. Обязательно с использованием оконной функции.
-- Столбцы результата = все столбцы таблицы платежей.
--
-- Логика: нумеруем платежи внутри каждого сотрудника по возрастанию даты
-- (тай-брейк — payment_id, чтобы нумерация была однозначной) и оставляем
-- строку с номером 1.
-- ---------------------------------------------------------------------
\echo '===== ЗАДАНИЕ 1.1 (оконная функция) ====='
SELECT payment_id, customer_id, staff_id, rental_id, amount, payment_date
FROM (
    SELECT p.*,
           row_number() OVER (PARTITION BY p.staff_id
                              ORDER BY p.payment_date, p.payment_id) AS rn
    FROM payment p
) t
WHERE t.rn = 1
ORDER BY staff_id;


-- ---------------------------------------------------------------------
-- ЗАДАНИЕ 1.2. То же самое, но обязательно с использованием агрегации.
--
-- Логика: агрегатный подзапрос находит для каждого сотрудника самую
-- раннюю дату платежа (min), затем эта дата соединяется с таблицей
-- платежей. Проверено: ни у одного сотрудника нет двух платежей в одну
-- и ту же секунду, поэтому результат — ровно одна строка на сотрудника.
-- Если бы ничьи были, потребовался бы дополнительный тай-брейк по
-- минимальному payment_id.
-- ---------------------------------------------------------------------
\echo '===== ЗАДАНИЕ 1.2 (агрегация) ====='
SELECT p.payment_id, p.customer_id, p.staff_id, p.rental_id, p.amount, p.payment_date
FROM payment p
JOIN (
    SELECT staff_id, min(payment_date) AS first_payment_date
    FROM payment
    GROUP BY staff_id
) f ON f.staff_id = p.staff_id
   AND f.first_payment_date = p.payment_date
ORDER BY p.staff_id;


-- ---------------------------------------------------------------------
-- ЗАДАНИЕ 1.3. То же самое, но обязательно с использованием distinct on.
--
-- Логика: distinct on (staff_id) оставляет первую строку каждой группы
-- сотрудника в порядке сортировки order by, поэтому сортировка задана как
-- staff_id, payment_date, payment_id.
-- ---------------------------------------------------------------------
\echo '===== ЗАДАНИЕ 1.3 (distinct on) ====='
SELECT DISTINCT ON (p.staff_id)
       p.payment_id, p.customer_id, p.staff_id, p.rental_id, p.amount, p.payment_date
FROM payment p
ORDER BY p.staff_id, p.payment_date, p.payment_id;


-- ---------------------------------------------------------------------
-- ЗАДАНИЕ 2. Для каждого покупателя посчитайте, сколько фильмов со
-- специальным атрибутом «Behind the Scenes» он брал в аренду.
-- Обязательно использовать CTE, при этом в CTE должна использоваться
-- строго одна таблица.
--
-- CTE bts_films читает только таблицу film и возвращает нужные film_id.
-- Далее обычная цепочка customer -> rental -> inventory -> bts_films.
--
-- Внимание: фильмы с этим атрибутом брали 412 покупателей из 599. Здесь
-- показаны только те, кто брал хотя бы один (соединение inner join).
-- Если нужен отчёт по всем 599 покупателям с нулями для остальных —
-- достаточно заменить цепочку join на LEFT JOIN и считать count(b.film_id).
-- ---------------------------------------------------------------------
\echo '===== ЗАДАНИЕ 2 (CTE, строго одна таблица) ====='
WITH bts_films AS (
    SELECT f.film_id
    FROM film f
    WHERE f.special_features @> ARRAY['Behind the Scenes']
)
SELECT c.last_name || ' ' || c.first_name AS "Фамилия и имя пользователя",
       count(*)                           AS "Количество арендованных фильмов"
FROM customer c
JOIN rental r     ON r.customer_id = c.customer_id
JOIN inventory i  ON i.inventory_id = r.inventory_id
JOIN bts_films b  ON b.film_id = i.film_id
GROUP BY c.customer_id, c.last_name, c.first_name
ORDER BY "Количество арендованных фильмов" DESC, "Фамилия и имя пользователя";


-- ---------------------------------------------------------------------
-- ЗАДАНИЕ 3. То же самое, но с использованием подзапроса, который также
-- обращается строго к одной таблице (film).
-- ---------------------------------------------------------------------
\echo '===== ЗАДАНИЕ 3 (подзапрос, строго одна таблица) ====='
SELECT c.last_name || ' ' || c.first_name AS "Фамилия и имя пользователя",
       count(*)                           AS "Количество арендованных фильмов"
FROM customer c
JOIN rental r     ON r.customer_id = c.customer_id
JOIN inventory i  ON i.inventory_id = r.inventory_id
WHERE i.film_id IN (
    SELECT f.film_id
    FROM film f
    WHERE f.special_features @> ARRAY['Behind the Scenes']
)
GROUP BY c.customer_id, c.last_name, c.first_name
ORDER BY "Количество арендованных фильмов" DESC, "Фамилия и имя пользователя";


-- ---------------------------------------------------------------------
-- ЗАДАНИЕ 4. Создайте материализованное представление с запросом из
-- задания 3 и напишите запрос на его обновление.
-- ---------------------------------------------------------------------
\echo '===== ЗАДАНИЕ 4 (материализованное представление) ====='
DROP MATERIALIZED VIEW IF EXISTS mv_bts_rentals;

CREATE MATERIALIZED VIEW mv_bts_rentals AS
SELECT c.last_name || ' ' || c.first_name AS "Фамилия и имя пользователя",
       count(*)                           AS "Количество арендованных фильмов"
FROM customer c
JOIN rental r     ON r.customer_id = c.customer_id
JOIN inventory i  ON i.inventory_id = r.inventory_id
WHERE i.film_id IN (
    SELECT f.film_id
    FROM film f
    WHERE f.special_features @> ARRAY['Behind the Scenes']
)
GROUP BY c.customer_id, c.last_name, c.first_name;

-- Запрос на обновление материализованного представления:
REFRESH MATERIALIZED VIEW mv_bts_rentals;

-- Проверка: данные лежат в представлении и читаются без обращений к
-- исходным таблицам.
\echo '----- проверка материализованного представления -----'
SELECT count(*) AS "Строк в представлении" FROM mv_bts_rentals;

SELECT pg_size_pretty(pg_total_relation_size('mv_bts_rentals')) AS "Размер всего"
FROM (SELECT 1) t;


-- ---------------------------------------------------------------------
-- ЗАДАНИЕ 5. С помощью explain analyze проанализируйте стоимость запросов
-- из всех предыдущих заданий и ответьте на два вопроса.
-- ---------------------------------------------------------------------
\echo '===== ЗАДАНИЕ 5. Планы выполнения ====='

\echo '----- 5.1. План задания 1.1 (оконная функция) -----'
EXPLAIN (ANALYZE, BUFFERS, COSTS)
SELECT payment_id, customer_id, staff_id, rental_id, amount, payment_date
FROM (
    SELECT p.*, row_number() OVER (PARTITION BY p.staff_id
                                   ORDER BY p.payment_date, p.payment_id) AS rn
    FROM payment p
) t
WHERE t.rn = 1
ORDER BY staff_id;

\echo '----- 5.2. План задания 1.2 (агрегация) -----'
EXPLAIN (ANALYZE, BUFFERS, COSTS)
SELECT p.payment_id, p.customer_id, p.staff_id, p.rental_id, p.amount, p.payment_date
FROM payment p
JOIN (SELECT staff_id, min(payment_date) AS first_payment_date
      FROM payment GROUP BY staff_id) f
  ON f.staff_id = p.staff_id AND f.first_payment_date = p.payment_date
ORDER BY p.staff_id;

\echo '----- 5.3. План задания 1.3 (distinct on) -----'
EXPLAIN (ANALYZE, BUFFERS, COSTS)
SELECT DISTINCT ON (p.staff_id)
       p.payment_id, p.customer_id, p.staff_id, p.rental_id, p.amount, p.payment_date
FROM payment p
ORDER BY p.staff_id, p.payment_date, p.payment_id;

\echo '----- 5.4. План задания 2 (CTE) -----'
EXPLAIN (ANALYZE, BUFFERS, COSTS)
WITH bts_films AS (
    SELECT f.film_id FROM film f WHERE f.special_features @> ARRAY['Behind the Scenes']
)
SELECT c.last_name || ' ' || c.first_name AS "Фамилия и имя пользователя", count(*) AS cnt
FROM customer c
JOIN rental r    ON r.customer_id = c.customer_id
JOIN inventory i ON i.inventory_id = r.inventory_id
JOIN bts_films b ON b.film_id = i.film_id
GROUP BY c.customer_id, c.last_name, c.first_name;

\echo '----- 5.5. План задания 3 (подзапрос) -----'
EXPLAIN (ANALYZE, BUFFERS, COSTS)
SELECT c.last_name || ' ' || c.first_name AS "Фамилия и имя пользователя", count(*) AS cnt
FROM customer c
JOIN rental r    ON r.customer_id = c.customer_id
JOIN inventory i ON i.inventory_id = r.inventory_id
WHERE i.film_id IN (SELECT f.film_id FROM film f
                    WHERE f.special_features @> ARRAY['Behind the Scenes'])
GROUP BY c.customer_id, c.last_name, c.first_name;

-- ОТВЕТ НА ВОПРОС (а): какой из вариантов 1.1, 1.2, 1.3 потребляет меньше
-- ресурсов?
--
--   | вариант             | стоимость плана    | время, мс | буферы |
--   |---------------------|--------------------|-----------|--------|
--   | 1.1 оконная функция | 1400.55..1962.24   |    5.85   |   119  |
--   | 1.2 агрегация       |  359.78..723.55    |    3.46   |   238  |
--   | 1.3 distinct on     | 1400.53..1480.77   |    8.93   |   119  |
--
--   (Значения времени и буферов слегка колеблются от прогона к прогону —
--   это нормально, оценка стоимости cost при этом не меняется.)
--
--   Меньше всего ресурсов потребляет вариант 1.2 (агрегация): у него самая
--   низкая оценка стоимости (723 против 1481 и 1962), самое низкое
--   фактическое время (3.6 мс) и он не сортирует всю таблицу платежей.
--   Плата за это одна — таблица payment читается дважды (сначала для
--   агрегата, затем для соединения), поэтому буферов больше (238).
--
--   Варианты 1.1 и 1.3 оба вынуждены отсортировать все 16 049 строк
--   таблицы payment (Sort ... Memory: 1137kB — сортировка дороже
--   агрегации, отсюда оценка ~1400). Обе читают одинаковое число страниц
--   (119), то есть по буферам они равны.
--   Вариант 1.3 дешевле варианта 1.1 по стоимости плана (1481 против
--   1962), но фактически работает медленнее всех (8.9 мс): после полной
--   сортировки узел Unique отбрасывает 16 047 строк из 16 049.
--   Вариант 1.1 интересен тем, что планировщик добавил
--   «Run Condition: (row_number() OVER (?) <= 1)» и прекращает отдавать
--   строки окна, как только номер превысил 1, — но сортировка всё равно
--   выполняется целиком.
--
--   Итог: 1.2 < 1.3 < 1.1 по стоимости, 1.2 < 1.1 < 1.3 по фактическому
--   времени. По совокупности ресурсов выигрывает 1.2.
--
-- ОТВЕТ НА ВОПРОС (б): что потребляет меньше — CTE из задания 2 или
-- подзапрос из задания 3?
--
--   Планы получились ОДИНАКОВЫМИ:
--     CTE:        cost=370.07..379.05, actual 1.280 мс, Buffers: shared hit=1305
--     подзапрос:  cost=370.07..379.05, actual 1.380 мс, Buffers: shared hit=1305
--   Повторные прогоны дали 1.319 и 1.486 мс у CTE против 1.349 и 1.173 мс
--   у подзапроса — то есть разница целиком в пределах шума измерений.
--
--   Причина: начиная с PostgreSQL 12 нерекурсивный CTE, который
--   используется в запросе один раз, по умолчанию «встраивается» (CTE
--   inlining) в основной запрос как обычный подзапрос. Поэтому CTE не
--   является барьером материализации и ресурсы расходуются одинаково.
--   Названия узлов плана в обоих случаях совпадают: HashAggregate ->
--   Hash Join -> Nested Loop -> Hash Join (film+inventory) ->
--   Index Scan по rental.
--
--   Если материализацию CTE включить принудительно
--   (WITH bts_films AS MATERIALIZED (...)), то в плане появляется
--   дополнительный узел CTE Scan, стоимость немного растёт
--   (393.33 против 379.05), потому что 50 строк сначала складываются во
--   временное хранилище, а потом читаются из него. Но при таком размере
--   данных различие практически незаметно.
--
--   Итог: у одного и того же запроса CTE и подзапрос потребляют одинаковое
--   количество ресурсов; различать их по производительности на этом
--   занятии не нужно.


-- =====================================================================
--  ДОПОЛНИТЕЛЬНАЯ ЧАСТЬ
-- =====================================================================

-- ---------------------------------------------------------------------
-- ЗАДАНИЕ ДОП. 1. Откройте SQL-запрос (файл sql-hw5.sql), выполните для
-- него explain analyze, найдите и опишите узкие места, сравните с решением
-- из задания 4 и сделайте построчное описание explain analyze
-- оптимизированного запроса.
-- ---------------------------------------------------------------------

-- Исходный запрос (из файла sql-hw5.sql):
--
--   select distinct cu.first_name || ' ' || cu.last_name as name,
--          count(ren.iid) over (partition by cu.customer_id)
--   from customer cu
--   full outer join
--       (select *, r.inventory_id as iid, inv.sf_string as sfs, r.customer_id as cid
--        from rental r
--        full outer join
--            (select *, unnest(f.special_features) as sf_string
--             from inventory i
--             full outer join film f on f.film_id = i.film_id) as inv
--            on r.inventory_id = inv.inventory_id) as ren
--       on ren.cid = cu.customer_id
--   where ren.sfs like '%Behind the Scenes%'
--   order by count desc;

\echo '===== ДОП.1. План исходного (плохого) запроса ====='
EXPLAIN (ANALYZE, BUFFERS, COSTS)
select distinct cu.first_name || ' ' || cu.last_name as name,
       count(ren.iid) over (partition by cu.customer_id)
from customer cu
full outer join
    (select *, r.inventory_id as iid, inv.sf_string as sfs, r.customer_id as cid
     from rental r
     full outer join
         (select *, unnest(f.special_features) as sf_string
          from inventory i
          full outer join film f on f.film_id = i.film_id) as inv
         on r.inventory_id = inv.inventory_id) as ren
    on ren.cid = cu.customer_id
where ren.sfs like '%Behind the Scenes%'
order by count desc;

\echo '===== ДОП.1. План оптимизированного запроса (задание 3/4) ====='
EXPLAIN (ANALYZE, BUFFERS, COSTS)
SELECT c.last_name || ' ' || c.first_name AS "Фамилия и имя пользователя", count(*) AS cnt
FROM customer c
JOIN rental r    ON r.customer_id = c.customer_id
JOIN inventory i ON i.inventory_id = r.inventory_id
WHERE i.film_id IN (SELECT f.film_id FROM film f
                    WHERE f.special_features @> ARRAY['Behind the Scenes'])
GROUP BY c.customer_id, c.last_name, c.first_name;

\echo '===== ДОП.1. План чтения материализованного представления ====='
EXPLAIN (ANALYZE, BUFFERS, COSTS) SELECT * FROM mv_bts_rentals;

-- ---------------------------------------------------------------------
-- УЗКИЕ МЕСТА ИСХОДНОГО ЗАПРОСА
--
-- 1. unnest(f.special_features) превращает каждую строку film в столько
--    строк, сколько элементов в массиве special_features. Узел
--    ProjectSet разворачивает 4 623 строки соединения inventory+film в
--    16 362 строки — почти в 3.5 раза больше, чем нужно. Это самая
--    дорогая часть плана.
-- 2. Условие ren.sfs like '%Behind the Scenes%' — несагрируемое
--    (шаблон начинается с %), поэтому индекс по special_features
--    использоваться не может. Узел Subquery Scan вынужден перебрать все
--    16 362 строки и выбросить 16 151 из них (Rows Removed by Filter:
--    16151), чтобы оставить 211.
--    Правильнее проверять массив целиком оператором @> (содержит),
--    который умеет работать с индексом GIN: special_features @>
--    ARRAY['Behind the Scenes'] — так делает оптимизированный запрос.
-- 3. Двойной full outer join. Внешние соединения (Full Join) не дают
--    планировщику отбросить ненужные строки заранее и мешают выбрать
--    порядок соединения; после применения условия WHERE они фактически
--    вырождаются в левые соединения, то есть написаны зря.
-- 4. Побочный эффект full outer join: в результат попадают фильмы с
--    атрибутом «Behind the Scenes», которые вообще ни разу не арендовали
--    (таких фильмов 2). У этих строк нет покупателя, поэтому в отчёте
--    появляется лишняя строка с пустым именем: запрос возвращает 413
--    строк вместо 412 (проверено: count(*) filter (where name is null) = 1).
-- 5. distinct по паре (имя, счётчик) — это дорогая сортировка всего
--    результата, к тому же покупателя правильнее идентифицировать по
--    customer_id, а не по строке с именем (однофамильцы склеятся).
-- 6. Оконная функция здесь вообще не нужна: задача решается обычной
--    агрегацией group by. Оконный вариант заставляет сначала
--    отсортировать данные по customer_id (лишний Sort на 736 строк), а
--    затем прогнать WindowAgg, который считает одно и то же число для
--    каждой строки покупателя.
-- 7. order by count desc — сортировка уже после distinct, ещё один
--    проход по результату.
--
-- СРАВНЕНИЕ С РЕШЕНИЕМ ИЗ ЗАДАНИЯ 4 (материализованное представление):
--
--   | решение                        | строк | буферы | время, мс |
--   |--------------------------------|-------|--------|-----------|
--   | исходный «плохой» запрос       |  413  |  3470  |    5.04   |
--   | оптимизированный запрос (з. 3) |  412  |  1305  |    1.38   |
--   | чтение материализованного пред.|  412  |     4  |    0.03   |
--
--   Оптимизированный запрос читает в 2.6 раза меньше страниц и работает
--   в 4 раза быстрее, при этом не тратит память на разворачивание массива
--   (в плохом плане сортировки используют 60kB + 54kB, здесь — 105kB на
--   HashAggregate, но без промежуточных 16 362 строк).
--   Материализованное представление убирает работу целиком: 412 строк
--   лежат готовыми (48 kB), чтение — один Seq Scan по 4 страницам за
--   0.03 мс, то есть примерно в 150 раз быстрее плохого запроса.
--   Цена — данные приходится обновлять командой refresh materialized view.
--
-- ---------------------------------------------------------------------
-- ПОСТРОЧНОЕ ОПИСАНИЕ EXPLAIN ANALYZE ОПТИМИЗИРОВАННОГО ЗАПРОСА
--
-- План читается снизу вверх: самые нижние строки выполняются первыми.
--
--  HashAggregate  (cost=370.07..379.05 rows=599 width=57)
--                 (actual time=1.085..1.136 rows=412 loops=1)
--        Верхний узел: группировка строк по покупателю и подсчёт
--        количества аренд (то самое count(*)). Планировщик ожидал 599
--        групп (столько всего покупателей), фактически получилось 412 —
--        столько покупателей брали хотя бы один фильм с этим атрибутом.
--        cost=370.07..379.05 — оценка: 370 стартовая стоимость (всё, что
--        нужно прочитать) и 379 полная; время дано в мс.
--    Group Key: c.customer_id
--        Ключ группировки — идентификатор покупателя.
--    Batches: 1  Memory Usage: 105kB
--        Хеш-таблица агрегации поместилась в память целиком (1 пакет),
--        на диск ничего не сбрасывалось.
--    Buffers: shared hit=1305
--        Все 1305 страниц нужных таблиц уже были в кеше PostgreSQL
--        (shared hit), чтения с диска (read) не потребовалось.
--    ->  Hash Join  (cost=154.89..366.06 rows=802 width=17)
--                   (actual time=0.206..0.985 rows=734 loops=1)
--        Соединение результата нижнего узла с таблицей покупателей
--        хеш-методом. Ожидалось 802 строки, получено 734.
--          Hash Cond: (r.customer_id = c.customer_id)
--        Условие соединения: покупатель аренды = покупатель таблицы.
--          ->  Nested Loop  (cost=101.41..310.46 rows=802 width=2)
--                           (actual time=0.126..0.818 rows=734 loops=1)
--        Соединение «вложенный цикл»: для каждой подходящей позиции
--        инвентаря выполняется поиск аренд по индексу.
--                ->  Hash Join  (cost=101.12..184.02 rows=229 width=4)
--                               (actual time=0.124..0.508 rows=209 loops=1)
--        Отбор нужных позиций инвентаря: хеш-соединение inventory с
--        film по film_id. Ожидалось 229 строк, получено 209 — столько
--        позиций инвентаря приходится на фильмы с атрибутом
--        «Behind the Scenes».
--                      Hash Cond: (i.film_id = f.film_id)
--                      ->  Seq Scan on inventory i
--                          (cost=0.00..70.81 rows=4581 width=6)
--                          (actual time=0.001..0.144 rows=4581 loops=1)
--        Последовательное чтение всей таблицы inventory: 4581 строка
--        за 0.144 мс. Таблица маленькая, индекс здесь не нужен.
--                          Buffers: shared hit=25
--                      ->  Hash  (cost=100.50..100.50 rows=50 width=4)
--                                (actual time=0.121..0.122 rows=50 loops=1)
--                          ->  Seq Scan on film f
--                              (cost=0.00..100.50 rows=50 width=4)
--                              (actual time=0.109..0.119 rows=50 loops=1)
--                              Filter: (special_features @> '{"Behind the Scenes"}'::text[])
--                              Rows Removed by Filter: 950
--        Здесь главное отличие от плохого запроса: читается таблица film
--        (1000 строк), фильтр по массиву special_features выполняется
--        ОДНИМ условием «содержит» (@>), без unnest и без like по
--        подстроке. 950 строк отброшено, осталось 50 нужных фильмов,
--        из них строится хеш-таблица для соединения.
--                ->  Index Scan using idx_fk_inventory_id on rental r
--                    (cost=0.29..0.51 rows=4 width=6)
--                    (actual time=0.001..0.001 rows=4 loops=209)
--                      Index Cond: (inventory_id = i.inventory_id)
--        Обращение к таблице аренд по индексу внешнего ключа (этот индекс
--        уже есть в базе, создавать его не нужно). loops=209 — узел
--        выполнялся 209 раз, по одному на каждую найденную позицию
--        инвентаря; каждый раз индекс сразу отдаёт ровно 4 аренды.
--                      Buffers: shared hit=1152
--        Основная часть прочитанных страниц — здесь, но это точечные
--        попадания по индексу, а не перебор всей таблицы.
--          ->  Hash  (cost=45.99..45.99 rows=599 width=17)
--                    (actual time=0.077..0.078 rows=599 loops=1)
--              ->  Seq Scan on customer c
--                  (cost=0.00..45.99 rows=599 width=17)
--                  (actual time=0.002..0.040 rows=599 loops=1)
--        Справа строится хеш-таблица из всех 599 покупателей (0.078 мс) —
--        по ней верхний узел и соединяет аренды с покупателями.
--  Planning Time: 0.208 ms
--        Время построения плана: 0.208 мс, то есть меньше 20 % от общего
--        времени (для сравнения, у плохого запроса — 0.163 мс при
--        4.753 мс выполнения).
--
--  Итого: план состоит из одного последовательного чтения маленьких
--  таблиц (inventory, film, customer), одного точечного поиска по индексу
--  в rental и одной группировки. Ни одного лишнего прохода по 16 000
--  строк и ни одного разворачивания массива.
-- ---------------------------------------------------------------------


-- ---------------------------------------------------------------------
-- ЗАДАНИЕ ДОП. 2. Для каждого магазина в ОДНОМ запросе определите:
--   * день, в который арендовали больше всего фильмов (формат ГГГГ-ММ-ДД),
--     и количество фильмов в этот день;
--   * день с наименьшей суммой продаж (формат ГГГГ-ММ-ДД) и сумму продаж
--     в этот день.
-- Столбцы: Идентификатор магазина, день аренды, количество фильмов,
--          день продажи, сумма продаж.
--
-- Замечание по данным: магазин аренды определяем через продавца
-- (rental.staff_id -> staff.store_id), а не через
-- inventory.store_id, потому что суммы продаж привязаны к магазину
-- только через продавца (payment.staff_id -> staff.store_id). Так обе
-- половины отчёта считаются по одному и тому же магазину.
-- (Для справки: у 7981 аренды из 16044 магазин позиции inventory
-- отличается от магазина продавца.)
--
-- Ничьих нет: у каждого магазина ровно один день-максимум по арендам и
-- ровно один день-минимум по продажам, поэтому row_number() с
-- тай-брейком по дате даёт ровно одну строку на магазин.
-- ---------------------------------------------------------------------
\echo '===== ДОП.2 (один запрос на два показателя) ====='
WITH rent_daily AS (
    SELECT s.store_id,
           r.rental_date::date AS rental_day,
           count(*)            AS films_count
    FROM rental r
    JOIN staff s ON s.staff_id = r.staff_id
    GROUP BY s.store_id, r.rental_date::date
),
rent_top AS (
    SELECT store_id, rental_day, films_count,
           row_number() OVER (PARTITION BY store_id
                              ORDER BY films_count DESC, rental_day) AS rn
    FROM rent_daily
),
pay_daily AS (
    SELECT s.store_id,
           p.payment_date::date AS payment_day,
           sum(p.amount)        AS day_sum
    FROM payment p
    JOIN staff s ON s.staff_id = p.staff_id
    GROUP BY s.store_id, p.payment_date::date
),
pay_low AS (
    SELECT store_id, payment_day, day_sum,
           row_number() OVER (PARTITION BY store_id
                              ORDER BY day_sum ASC, payment_day) AS rn
    FROM pay_daily
),
report AS (
    SELECT t.store_id,
           t.rental_day,
           t.films_count,
           l.payment_day,
           l.day_sum
    FROM rent_top t
    JOIN pay_low l ON l.store_id = t.store_id AND l.rn = 1
    WHERE t.rn = 1
)
SELECT store_id            AS "Идентификатор магазина",
       rental_day::text    AS "День аренды",
       films_count         AS "Количество фильмов",
       payment_day::text   AS "День продажи",
       day_sum             AS "Сумма продаж"
FROM report
ORDER BY store_id;


-- ---------------------------------------------------------------------
-- ЗАДАНИЕ ДОП. 3. Создайте ненаполненное материализованное представление,
-- в котором будет храниться отчёт:
--   * идентификатор сотрудника;
--   * ФИО сотрудника одним значением;
--   * город проживания сотрудника;
--   * идентификатор магазина;
--   * город магазина;
--   * дата последнего платежа, принятого сотрудником;
--   * сумма этого последнего платежа;
--   * общая сумма продаж.
-- ---------------------------------------------------------------------
\echo '===== ДОП.3 (ненаполненное материализованное представление) ====='
DROP MATERIALIZED VIEW IF EXISTS mv_staff_report;

CREATE MATERIALIZED VIEW mv_staff_report AS
SELECT s.staff_id                                        AS "Идентификатор сотрудника",
       s.last_name || ' ' || s.first_name                AS "ФИО сотрудника",
       ca.city                                           AS "Город сотрудника",
       st.store_id                                       AS "Идентификатор магазина",
       sa.city                                           AS "Город магазина",
       lp.payment_date                                   AS "Дата последнего платежа",
       lp.amount                                         AS "Сумма последнего платежа",
       ts.sales_sum                                       AS "Общая сумма продаж"
FROM staff s
JOIN address a    ON a.address_id = s.address_id
JOIN city ca      ON ca.city_id = a.city_id
JOIN store st     ON st.store_id = s.store_id
JOIN address sta  ON sta.address_id = st.address_id
JOIN city sa      ON sa.city_id = sta.city_id
LEFT JOIN LATERAL (
    SELECT p.payment_date, p.amount
    FROM payment p
    WHERE p.staff_id = s.staff_id
    ORDER BY p.payment_date DESC, p.payment_id DESC
    LIMIT 1
) lp ON true
LEFT JOIN (
    SELECT p.staff_id, sum(p.amount) AS sales_sum
    FROM payment p
    GROUP BY p.staff_id
) ts ON ts.staff_id = s.staff_id
WITH NO DATA;

-- Представление создано ненаполненным: WITH NO DATA. Проверяем это.
\echo '----- представление не наполнено (relispopulated = false) -----'
SELECT relname AS "Имя", relispopulated AS "Наполнено"
FROM pg_class
WHERE relname = 'mv_staff_report';

-- Чтобы наполнить отчёт, нужно выполнить (в решении не выполняется,
-- так как представление должно остаться ненаполненным):
--   REFRESH MATERIALIZED VIEW mv_staff_report;

-- Проверка содержимого будущего отчёта — тем же запросом напрямую,
-- без обращения к представлению.
\echo '----- проверка содержимого отчёта (запрос тех же данных) -----'
SELECT s.staff_id                          AS "Идентификатор сотрудника",
       s.last_name || ' ' || s.first_name  AS "ФИО сотрудника",
       ca.city                             AS "Город сотрудника",
       st.store_id                         AS "Идентификатор магазина",
       sa.city                             AS "Город магазина",
       lp.payment_date                     AS "Дата последнего платежа",
       lp.amount                           AS "Сумма последнего платежа",
       ts.sales_sum                        AS "Общая сумма продаж"
FROM staff s
JOIN address a    ON a.address_id = s.address_id
JOIN city ca      ON ca.city_id = a.city_id
JOIN store st     ON st.store_id = s.store_id
JOIN address sta  ON sta.address_id = st.address_id
JOIN city sa      ON sa.city_id = sta.city_id
LEFT JOIN LATERAL (
    SELECT p.payment_date, p.amount
    FROM payment p
    WHERE p.staff_id = s.staff_id
    ORDER BY p.payment_date DESC, p.payment_id DESC
    LIMIT 1
) lp ON true
LEFT JOIN (
    SELECT p.staff_id, sum(p.amount) AS sales_sum
    FROM payment p
    GROUP BY p.staff_id
) ts ON ts.staff_id = s.staff_id
ORDER BY s.staff_id;
