
# online_food.py
import os
import random
import requests
from urllib.parse import urlencode

# -------- TheMealDB: Recipes (free public API) --------
# Docs & endpoints: test key '1', search, filter by category/area/ingredient, lookup by id  [1](https://www.themealdb.com/api.php)
MEALDB_BASE = "https://www.themealdb.com/api/json/v1/1"

def _mealdb_get(path: str, params: dict) -> dict:
    url = f"{MEALDB_BASE}/{path}"
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()

def search_recipes(query: str = "", category: str | None = "Dessert", ingredient: str | None = None, limit: int = 5):
    """
    Returns a list of {title, url, image, instructions, ingredients[]} for quick suggestion cards.
    Priority: by ingredient -> by category -> by text search -> random.
    """
    meals = None

    # 1) Ingredient filter (fast narrow)  [1](https://www.themealdb.com/api.php)
    if ingredient:
        data = _mealdb_get("filter.php", {"i": ingredient})
        meals = data.get("meals") or []

    # 2) Category filter (Dessert is a good 'cheer-up' default)  [1](https://www.themealdb.com/api.php)
    if (not meals) and category:
        data = _mealdb_get("filter.php", {"c": category})
        meals = data.get("meals") or []

    # 3) Text search (name)  [1](https://www.themealdb.com/api.php)
    if (not meals) and query:
        data = _mealdb_get("search.php", {"s": query})
        meals = data.get("meals") or []

    # 4) Random fallback  [1](https://www.themealdb.com/api.php)
    if not meals:
        data = _mealdb_get("random.php", {})
        meals = data.get("meals") or []

    # Hydrate details via lookup (filter endpoints return only id/name/thumb)  [3](https://www.educative.io/courses/fetching-recipes-with-themealdb-and-thecocktaildb-in-javascript/filter-meals)
    def hydrate(meal_id):
        d = _mealdb_get("lookup.php", {"i": meal_id})
        m = (d.get("meals") or [None])[0]
        if not m:
            return None
        # Collect ingredients
        ings = []
        for i in range(1, 21):
            ing = (m.get(f"strIngredient{i}") or "").strip()
            meas = (m.get(f"strMeasure{i}") or "").strip()
            if ing:
                ings.append(f"{ing}{' - ' + meas if meas else ''}")
        return {
            "title": m.get("strMeal"),
            "url": m.get("strSource") or f"https://www.themealdb.com/meal/{m.get('idMeal')}",
            "image": m.get("strMealThumb"),
            "instructions": (m.get("strInstructions") or "").strip(),
            "ingredients": ings,
            "id": m.get("idMeal"),
            "area": m.get("strArea"),
            "category": m.get("strCategory"),
        }

    random.shuffle(meals)
    hydrated = []
    for m in meals[: max(limit, 1)]:
        item = hydrate(m.get("idMeal"))
        if item:
            hydrated.append(item)

    return hydrated[:limit]


# -------- OpenFoodFacts: Treats (ready-to-buy snacks) --------
# Use CGI search with tag filters; send a descriptive User-Agent; respect rate limits (10 search req/min).  [4](https://wiki.openfoodfacts.org/API/Read/Search)[5](https://openfoodfacts.github.io/openfoodfacts-server/api/)
OFF_SEARCH = "https://world.openfoodfacts.org/cgi/search.pl"

def search_treats(
    keywords: list[str] | None = None,
    categories: list[str] | None = None,
    country: str | None = "Poland",
    page_size: int = 20,
):
    """
    Returns a list of {product_name, url, brands, image, categories, allergens} from OpenFoodFacts.
    """
    params = {
        "action": "process",
        "json": 1,
        "page_size": page_size,
        "search_simple": 1,
    }

    # Build tag filters (combine for powerful queries)  [4](https://wiki.openfoodfacts.org/API/Read/Search)
    # Example: countries=Poland AND categories=Chocolate
    tag_idx = 0
    if country:
        params[f"tagtype_{tag_idx}"] = "countries"
        params[f"tag_contains_{tag_idx}"] = "contains"
        params[f"tag_{tag_idx}"] = country
        tag_idx += 1

    if categories:
        for cat in categories:
            params[f"tagtype_{tag_idx}"] = "categories"
            params[f"tag_contains_{tag_idx}"] = "contains"
            params[f"tag_{tag_idx}"] = cat
            tag_idx += 1

    if keywords:
        # generic full‑text terms
        params["search_terms"] = " ".join(keywords)

    headers = {
        # OpenFoodFacts asks for a descriptive UA to avoid accidental blocking  [4](https://wiki.openfoodfacts.org/API/Read/Search)
        "User-Agent": os.getenv("OFF_USER_AGENT", "CheerUpBot/1.0 (https://github.com/EV22332233/CheerUpBot)"),
    }

    r = requests.get(OFF_SEARCH, params=params, headers=headers, timeout=20)
    r.raise_for_status()
    data = r.json()

    out = []
    for p in data.get("products", []):
        out.append({
            "product_name": p.get("product_name") or p.get("generic_name") or "Unknown",
            "brands": p.get("brands"),
            "url": p.get("url"),
            "image": p.get("image_url"),
            "categories": p.get("categories"),
            "allergens": p.get("allergens"),
        })
    return out
