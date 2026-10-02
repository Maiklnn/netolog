-- ============================================================================
-- ДОМАШНЕЕ ЗАДАНИЕ №4. «Управление данными и схемой (DDL/DML)»
-- База: postgres (контейнер с учебными базами), новая схема razhev
--
-- Использованы только операторы и функции занятий 1-4:
--   CREATE SCHEMA / CREATE TABLE (типы, NOT NULL, UNIQUE, PRIMARY KEY, DEFAULT,
--   CHECK, REFERENCES, составной PRIMARY KEY), GENERATED/IDENTITY, INSERT ...
--   VALUES (несколько строк), INSERT ... SELECT, unnest(), UPDATE, DELETE,
--   DROP TABLE, ROUND
--
-- ВАЖНО: имя схемы razhev — фамилия латиницей в нижнем регистре. Если база
-- облачная, схема обязана называться фамилией; при локальном сервере имя любое.
-- Если фамилия другая — поменяйте razhev на своё значение в строках ниже.
-- ============================================================================

-- Раскомментируйте, если скрипт запускается повторно:
-- DROP SCHEMA IF EXISTS razhev CASCADE;

CREATE SCHEMA razhev;
SET search_path TO razhev;

-- ============================================================================
-- ОСНОВНАЯ ЧАСТЬ
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Три справочника: языки, народности, страны.
-- У всех: автоинкрементный первичный ключ, название NOT NULL и UNIQUE
-- (уникальность не даёт дубликатов названий).
-- ---------------------------------------------------------------------------

CREATE TABLE razhev.language (
    language_id   serial       PRIMARY KEY,
    language_name varchar(50)  NOT NULL UNIQUE
);

CREATE TABLE razhev.nationality (
    nationality_id   serial      PRIMARY KEY,
    nationality_name varchar(50) NOT NULL UNIQUE
);

CREATE TABLE razhev.country (
    country_id   serial      PRIMARY KEY,
    country_name varchar(60) NOT NULL UNIQUE
);

-- ---------------------------------------------------------------------------
-- Две таблицы связей M:N (по образцу film_actor).
-- Составной PRIMARY KEY (две колонки) гарантирует, что одна и та же пара
-- не повторится, но у каждой сущности может быть сколько угодно связей.
-- Обе колонки — внешние ключи на справочники.
-- ---------------------------------------------------------------------------

-- связь «язык — народность»
CREATE TABLE razhev.language_nationality (
    language_id    int NOT NULL REFERENCES razhev.language(language_id),
    nationality_id int NOT NULL REFERENCES razhev.nationality(nationality_id),
    PRIMARY KEY (language_id, nationality_id)
);

-- связь «народность — страна»
CREATE TABLE razhev.nationality_country (
    nationality_id int NOT NULL REFERENCES razhev.nationality(nationality_id),
    country_id     int NOT NULL REFERENCES razhev.country(country_id),
    PRIMARY KEY (nationality_id, country_id)
);

-- ---------------------------------------------------------------------------
-- По 5 строк данных в каждую справочную таблицу
-- ---------------------------------------------------------------------------

INSERT INTO razhev.language (language_name)
VALUES ('Русский'),
       ('Английский'),
       ('Французский'),
       ('Немецкий'),
       ('Японский');

INSERT INTO razhev.nationality (nationality_name)
VALUES ('Славяне'),
       ('Англосаксы'),
       ('Французы'),
       ('Немцы'),
       ('Японцы');

INSERT INTO razhev.country (country_name)
VALUES ('Россия'),
       ('Великобритания'),
       ('Франция'),
       ('Германия'),
       ('Япония');

-- ---------------------------------------------------------------------------
-- По 5 строк в каждую таблицу связей
-- ---------------------------------------------------------------------------

INSERT INTO razhev.language_nationality (language_id, nationality_id)
VALUES (1, 1),
       (2, 2),
       (3, 3),
       (4, 4),
       (5, 5);

INSERT INTO razhev.nationality_country (nationality_id, country_id)
VALUES (1, 1),
       (2, 2),
       (3, 3),
       (4, 4),
       (5, 5);

-- ---------------------------------------------------------------------------
-- Контрольный вывод
-- ---------------------------------------------------------------------------
SELECT l.language_name    AS "Язык",
       n.nationality_name AS "Народность",
       c.country_name     AS "Страна"
FROM razhev.language_nationality ln
JOIN razhev.language l    ON l.language_id = ln.language_id
JOIN razhev.nationality n ON n.nationality_id = ln.nationality_id
JOIN razhev.nationality_country nc ON nc.nationality_id = n.nationality_id
JOIN razhev.country c     ON c.country_id = nc.country_id
ORDER BY l.language_id;


-- ============================================================================
-- ДОПОЛНИТЕЛЬНАЯ ЧАСТЬ
-- ============================================================================

-- ---------------------------------------------------------------------------
-- ЗАДАНИЕ 1. Новая таблица film_new
-- ---------------------------------------------------------------------------
CREATE TABLE razhev.film_new (
    film_name        varchar(255) NOT NULL,
    film_year        integer      CHECK (film_year > 0),
    film_rental_rate numeric(4,2) DEFAULT 0.99,
    film_duration    integer      NOT NULL CHECK (film_duration > 0)
);

-- ---------------------------------------------------------------------------
-- ЗАДАНИЕ 2. Заполнение таблицы: колонкам соответствуют массивы данных
-- unnest() разворачивает несколько массивов в строки
-- ---------------------------------------------------------------------------
INSERT INTO razhev.film_new (film_name, film_year, film_rental_rate, film_duration)
SELECT *
FROM unnest(
        ARRAY['The Shawshank Redemption', 'The Green Mile', 'Back to the Future',
              'Forrest Gump', 'Schindlers List'],
        ARRAY[1994, 1999, 1985, 1994, 1993],
        ARRAY[2.99, 0.99, 1.99, 2.99, 3.99],
        ARRAY[142, 189, 116, 142, 195]
     );

-- ---------------------------------------------------------------------------
-- ЗАДАНИЕ 3. Стоимость аренды всех фильмов выросла на 1.41
-- ---------------------------------------------------------------------------
UPDATE razhev.film_new
SET film_rental_rate = film_rental_rate + 1.41;

-- ---------------------------------------------------------------------------
-- ЗАДАНИЕ 4. Фильм «Back to the Future» снят с аренды — удаляем строку
-- ---------------------------------------------------------------------------
DELETE FROM razhev.film_new
WHERE film_name = 'Back to the Future';

-- ---------------------------------------------------------------------------
-- ЗАДАНИЕ 5. Добавляем ещё один фильм
-- ---------------------------------------------------------------------------
INSERT INTO razhev.film_new (film_name, film_year, film_rental_rate, film_duration)
VALUES ('The Godfather', 1972, 2.49, 175);

-- ---------------------------------------------------------------------------
-- ЗАДАНИЕ 6. Все колонки + вычисляемая колонка «длительность фильма в часах»
-- Число минут делим на 60 и округляем до десятых
-- ---------------------------------------------------------------------------
SELECT film_name        AS "Название фильма",
       film_year        AS "Год выпуска",
       film_rental_rate AS "Стоимость аренды",
       film_duration    AS "Длительность, мин",
       ROUND(film_duration / 60.0, 1) AS "Длительность фильма в часах"
FROM razhev.film_new;

-- ---------------------------------------------------------------------------
-- ЗАДАНИЕ 7. Удаляем таблицу film_new
-- ---------------------------------------------------------------------------
DROP TABLE razhev.film_new;
