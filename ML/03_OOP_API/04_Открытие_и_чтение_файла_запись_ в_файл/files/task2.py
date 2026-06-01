def read_cook_book(file_path):
    cook_book = {}

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    i = 0
    while i < len(lines):
        dish_name = lines[i]
        ingredients_count = int(lines[i + 1])
        ingredients = []

        for j in range(ingredients_count):
            parts = lines[i + 2 + j].split(' | ')
            ingredients.append({
                'ingredient_name': parts[0],
                'quantity': int(parts[1]),
                'measure': parts[2]
            })

        cook_book[dish_name] = ingredients
        i += 2 + ingredients_count

    return cook_book


# Использование:
cook_book = read_cook_book('recipes.txt')

def get_shop_list_by_dishes(dishes, person_count, cook_book):
    """Компактная версия функции"""
    shop_list = {}

    for dish in dishes:
        if dish in cook_book:
            for ingredient in cook_book[dish]:
                name = ingredient['ingredient_name']
                qty = ingredient['quantity'] * person_count

                if name in shop_list:
                    shop_list[name]['quantity'] += qty
                else:
                    shop_list[name] = {
                        'measure': ingredient['measure'],
                        'quantity': qty
                    }

    return shop_list

result = get_shop_list_by_dishes(['Запеченный картофель', 'Омлет'], 2, cook_book)

print(result)