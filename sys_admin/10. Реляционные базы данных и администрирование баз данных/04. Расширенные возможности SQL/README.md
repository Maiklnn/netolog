Домашнее задание к занятию «SQL. Часть 2» Ражев М.Н

## Задание 1.
Одним запросом получите информацию о магазине, в котором обслуживается более 300 покупателей, и выведите в результат следующую информацию:

- фамилия и имя сотрудника из этого магазина;
- город нахождения магазина;
- количество пользователей, закреплённых в этом магазине.
  
**Ответ**

SELECT 
    s.staff_id,
    CONCAT(s.first_name, ' ', s.last_name) AS staff_name,
    c.city AS store_city,
    COUNT(cu.customer_id) AS customer_count
FROM store st
INNER JOIN staff s ON st.manager_staff_id = s.staff_id
INNER JOIN address a ON st.address_id = a.address_id
INNER JOIN city c ON a.city_id = c.city_id
INNER JOIN customer cu ON st.store_id = cu.store_id
GROUP BY s.staff_id, s.first_name, s.last_name, c.city
HAVING COUNT(cu.customer_id) > 300;

-----------------------------------------------------------------------------------

## Задание 2.

Получите количество фильмов, продолжительность которых больше средней продолжительности всех фильмов.

**Ответ**

SELECT 
    COUNT(*) AS films_longer_than_avg
FROM film
WHERE length > (SELECT AVG(length) FROM film);

-----------------------------------------------------------------------------------

## Задание 3.

Получите информацию, за какой месяц была получена наибольшая сумма платежей, и добавьте информацию по количеству аренд за этот месяц.

**Ответ**

SELECT 
    DATE_FORMAT(p.payment_date, '%Y-%m') AS payment_month,
    SUM(p.amount) AS total_amount,
    COUNT(DISTINCT r.rental_id) AS rental_count
FROM payment p
INNER JOIN rental r ON p.rental_id = r.rental_id
GROUP BY DATE_FORMAT(p.payment_date, '%Y-%m')
ORDER BY SUM(p.amount) DESC
LIMIT 1;


-----------------------------------------------------------------------------------

## Задание 4.

Посчитайте количество продаж, выполненных каждым продавцом. Добавьте вычисляемую колонку «Премия». Если количество продаж превышает 8000, то значение в колонке будет «Да», иначе должно быть значение «Нет».

**Ответ**

SELECT 
    s.staff_id,
    CONCAT(s.first_name, ' ', s.last_name) AS staff_name,
    COUNT(p.payment_id) AS sales_count,
    CASE 
        WHEN COUNT(p.payment_id) > 8000 THEN 'Да'
        ELSE 'Нет'
    END AS bonus
FROM staff s
INNER JOIN payment p ON s.staff_id = p.staff_id
GROUP BY s.staff_id, s.first_name, s.last_name
ORDER BY sales_count DESC;

-----------------------------------------------------------------------------------

## Задание 5.

Найдите фильмы, которые ни разу не брали в аренду.

**Ответ**

SELECT 
    f.film_id, 
    f.title
FROM film f
LEFT JOIN inventory i ON f.film_id = i.film_id
LEFT JOIN rental r ON i.inventory_id = r.inventory_id
WHERE r.rental_id IS NULL
GROUP BY f.film_id, f.title;
