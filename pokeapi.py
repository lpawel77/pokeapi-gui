import io

import requests
from PIL import Image

API_URL = "https://pokeapi.co/api/v2"


def pobierz_json(url: str):
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def pobierz_pokemon(nazwa: str):
    url = f"{API_URL}/pokemon/{nazwa.lower()}"
    dane = pobierz_json(url)

    print(f"\nNazwa: {dane['name'].capitalize()}")
    print(f"ID: {dane['id']}")
    print(f"Wzrost: {dane['height'] / 10} m")
    print(f"Waga: {dane['weight'] / 10} kg")

    typy = [t['type']['name'] for t in dane['types']]
    print(f"Typy: {', '.join(typy)}")

    print("Umiejętności:")
    for ability in dane['abilities']:
        if ability['is_hidden']:
            print(f"  - {ability['ability']['name']} (ukryta)")
        else:
            print(f"  - {ability['ability']['name']}")

    print("Statystyki:")
    for stat in dane['stats']:
        print(f"  - {stat['stat']['name']}: {stat['base_stat']}")

    pokaz_obrazek(dane)


def pokaz_obrazek(dane: dict):
    sprites = dane['sprites']
    url_obrazka = sprites['other']['official-artwork']['front_default'] or sprites['front_default']
    if not url_obrazka:
        print("Brak dostępnego obrazka dla tego Pokémona.")
        return

    response = requests.get(url_obrazka)
    response.raise_for_status()

    obrazek = Image.open(io.BytesIO(response.content))
    obrazek.save(f"{dane['name']}.png")
    print(f"Zapisano obrazek jako {dane['name']}.png")
    obrazek.show()


if __name__ == "__main__":
    print("=== PokeAPI ===")
    print("Wpisz nazwę lub numer Pokémona, np. pikachu, 25, bulbasaur")

    while True:
        try:
            wpis = input("\nPokemon: ").strip()
            if not wpis:
                print("Nie wpisałeś nazwy.")
                continue

            pobierz_pokemon(wpis)

            jeszcze = input("\nChcesz sprawdzić kolejnego Pokémona? (t/n): ").strip().lower()
            if jeszcze not in ("t", "tak", "y", "yes"):
                print("Do widzenia!")
                break

        except requests.exceptions.HTTPError:
            print("Nie znaleziono Pokémona. Sprawdź nazwę lub numer.")
        except requests.exceptions.RequestException as e:
            print(f"Błąd połączenia z API: {e}")
            break
