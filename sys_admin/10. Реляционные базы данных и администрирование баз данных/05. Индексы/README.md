Домашнее задание к занятию «SQL. Часть 2» Ражев М.Н

## Задание 1.
Напишите запрос к учебной базе данных, который вернёт процентное отношение общего размера всех индексов к общему размеру всех таблиц.
  
**Ответ**

SELECT 
    table_name AS 'Таблица',
    ROUND(data_length / 1024 / 1024, 2) AS 'Размер данных (МБ)',
    ROUND(index_length / 1024 / 1024, 2) AS 'Размер индексов (МБ)',
    ROUND((data_length + index_length) / 1024 / 1024, 2) AS 'Общий размер (МБ)',
    ROUND((index_length / (data_length + index_length)) * 100, 2) AS 'Индексы (%)'
FROM information_schema.tables
WHERE table_schema = 'sakila'
ORDER BY (data_length + index_length) DESC;



-----------------------------------------------------------------------------------

## Задание 2.

Выполните explain analyze следующего запроса:

select distinct concat(c.last_name, ' ', c.first_name), sum(p.amount) over (partition by c.customer_id, f.title)
from payment p, rental r, customer c, inventory i, film f
where date(p.payment_date) = '2005-07-30' and p.payment_date = r.rental_date and r.customer_id = c.customer_id and i.inventory_id = r.inventory_id

- перечислите узкие места;
- оптимизируйте запрос: внесите корректировки по использованию операторов, при необходимости добавьте индексы.

**Ответ**

EXPLAIN ANALYZE
SELECT DISTINCT 
    CONCAT(c.last_name, ' ', c.first_name) AS customer_name,
    SUM(p.amount) OVER (PARTITION BY c.customer_id, f.title) AS total_per_film
FROM payment p
INNER JOIN rental r ON p.rental_id = r.rental_id
INNER JOIN customer c ON r.customer_id = c.customer_id
INNER JOIN inventory i ON r.inventory_id = i.inventory_id
INNER JOIN film f ON i.film_id = f.film_id
WHERE p.payment_date >= '2005-07-30' 
  AND p.payment_date < '2005-07-31';
