import io
import textwrap
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import requests
from PIL import Image, ImageTk

API_URL = "https://pokeapi.co/api/v2"


def pobierz_json(url: str):
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def pobierz_liste_pokemonow():
    dane = pobierz_json(f"{API_URL}/pokemon?limit=100000")
    wynik = []
    for wpis in dane["results"]:
        id_pokemona = int(wpis["url"].rstrip("/").split("/")[-1])
        wynik.append((id_pokemona, wpis["name"]))
    return wynik


def pobierz_opis(url_gatunku: str) -> str:
    dane = pobierz_json(url_gatunku)
    for wpis in dane["flavor_text_entries"]:
        if wpis["language"]["name"] == "en":
            return wpis["flavor_text"].replace("\x0c", " ").replace("\n", " ")
    return "Brak opisu."


def pobierz_obrazek(dane: dict) -> Image.Image:
    sprites = dane["sprites"]
    url_obrazka = sprites["other"]["official-artwork"]["front_default"] or sprites["front_default"]
    if not url_obrazka:
        return None
    response = requests.get(url_obrazka)
    response.raise_for_status()
    return Image.open(io.BytesIO(response.content))


class PokedexApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pokédex")
        self.geometry("920x650")
        self.minsize(800, 550)

        self.obrazek_tk = None
        self._numer_zapytania = 0
        self._pokemony = []
        self._posortowane = []
        self._sortowanie = "id"
        self._buduj_ui()
        self._wczytaj_liste_w_tle()

    def _buduj_ui(self):
        lewy = ttk.Frame(self, padding=10)
        lewy.pack(side="left", fill="y")

        ttk.Label(lewy, text="Nazwa lub numer:").pack(anchor="w")
        self.wpis = tk.StringVar()
        pole = ttk.Entry(lewy, textvariable=self.wpis, width=22)
        pole.pack(fill="x", pady=(0, 5))
        pole.bind("<Return>", lambda e: self._szukaj())

        ttk.Button(lewy, text="Szukaj", command=self._szukaj).pack(fill="x")

        ttk.Label(lewy, text="Lista Pokémonów:").pack(anchor="w", pady=(10, 0))

        ramka_sortowania = ttk.Frame(lewy)
        ramka_sortowania.pack(fill="x")
        ttk.Button(
            ramka_sortowania, text="Sortuj wg ID", command=lambda: self._ustaw_sortowanie("id")
        ).pack(side="left", expand=True, fill="x")
        ttk.Button(
            ramka_sortowania, text="Sortuj wg nazwy", command=lambda: self._ustaw_sortowanie("nazwa")
        ).pack(side="left", expand=True, fill="x")

        ramka_listy = ttk.Frame(lewy)
        ramka_listy.pack(fill="both", expand=True, pady=(15, 0))

        pasek = ttk.Scrollbar(ramka_listy, orient="vertical")
        self.lista = tk.Listbox(
            ramka_listy, yscrollcommand=pasek.set, width=36, font=("Consolas", 10)
        )
        pasek.config(command=self.lista.yview)
        pasek.pack(side="right", fill="y")
        self.lista.pack(side="left", fill="both", expand=True)
        self.lista.bind("<<ListboxSelect>>", self._wybrano_z_listy)

        self.status = tk.StringVar(value="Wczytywanie listy Pokémonów...")
        ttk.Label(lewy, textvariable=self.status, wraplength=200).pack(anchor="w", pady=(5, 0))

        prawy = ttk.Frame(self, padding=10)
        prawy.pack(side="left", fill="both", expand=True)

        self.etykieta_obrazka = ttk.Label(prawy)
        self.etykieta_obrazka.pack(pady=(0, 10))

        self.etykieta_naglowek = ttk.Label(prawy, font=("Segoe UI", 14, "bold"))
        self.etykieta_naglowek.pack(anchor="w")

        self.etykieta_staty = ttk.Label(prawy, justify="left", font=("Consolas", 10))
        self.etykieta_staty.pack(anchor="w", pady=(5, 10))

        ttk.Label(prawy, text="Opis:", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.etykieta_opis = ttk.Label(prawy, justify="left", wraplength=420)
        self.etykieta_opis.pack(anchor="w")

    def _wczytaj_liste_w_tle(self):
        watek = threading.Thread(target=self._pobierz_liste_watek, daemon=True)
        watek.start()

    def _pobierz_liste_watek(self):
        try:
            nazwy = pobierz_liste_pokemonow()
            self.after(0, self._pokaz_liste, nazwy)
        except requests.exceptions.RequestException as e:
            self.after(0, self._blad_listy, e)

    def _pokaz_liste(self, pokemony):
        self._pokemony = pokemony
        self._odswiez_liste()
        self.status.set(f"Załadowano {len(pokemony)} Pokémonów.")

    def _blad_listy(self, e):
        self.status.set("Nie udało się pobrać listy.")
        messagebox.showerror("Błąd połączenia", str(e))

    def _ustaw_sortowanie(self, tryb: str):
        self._sortowanie = tryb
        self._odswiez_liste()

    def _odswiez_liste(self):
        if self._sortowanie == "nazwa":
            self._posortowane = sorted(self._pokemony, key=lambda p: p[1])
        else:
            self._posortowane = sorted(self._pokemony, key=lambda p: p[0])
        self.lista.delete(0, "end")
        for id_pokemona, nazwa in self._posortowane:
            self.lista.insert("end", f"#{id_pokemona:>5} {nazwa.capitalize()}")

    def _wybrano_z_listy(self, event):
        zaznaczenie = self.lista.curselection()
        if not zaznaczenie:
            return
        _id, nazwa = self._posortowane[zaznaczenie[0]]
        self.wpis.set(nazwa)
        self._pokaz_pokemona(nazwa)

    def _szukaj(self):
        nazwa = self.wpis.get().strip().lower()
        if not nazwa:
            return
        self._pokaz_pokemona(nazwa)

    def _pokaz_pokemona(self, nazwa_lub_numer: str):
        self._numer_zapytania += 1
        moj_numer = self._numer_zapytania
        self.status.set(f"Wczytywanie: {nazwa_lub_numer}...")
        watek = threading.Thread(
            target=self._pobierz_pokemona_watek,
            args=(nazwa_lub_numer, moj_numer),
            daemon=True,
        )
        watek.start()

    def _pobierz_pokemona_watek(self, nazwa_lub_numer: str, moj_numer: int):
        try:
            dane = pobierz_json(f"{API_URL}/pokemon/{nazwa_lub_numer}")
            opis = pobierz_opis(dane["species"]["url"])
            obrazek = pobierz_obrazek(dane)
        except requests.exceptions.HTTPError:
            self.after(0, self._blad_szukania, moj_numer, nazwa_lub_numer, None)
            return
        except requests.exceptions.RequestException as e:
            self.after(0, self._blad_szukania, moj_numer, nazwa_lub_numer, e)
            return

        self.after(0, self._aktualizuj_pokemona, moj_numer, dane, opis, obrazek)

    def _blad_szukania(self, moj_numer: int, nazwa_lub_numer: str, blad):
        if moj_numer != self._numer_zapytania:
            return  # przyszła odpowiedź na nieaktualne zapytanie - ignorujemy
        self.status.set("Gotowe.")
        if blad is None:
            messagebox.showerror("Nie znaleziono", f"Nie znaleziono Pokémona: {nazwa_lub_numer}")
        else:
            messagebox.showerror("Błąd połączenia", str(blad))

    def _aktualizuj_pokemona(self, moj_numer: int, dane: dict, opis: str, obrazek):
        if moj_numer != self._numer_zapytania:
            return  # przyszła odpowiedź na nieaktualne zapytanie - ignorujemy

        if obrazek is not None:
            obrazek = obrazek.resize((300, 300), Image.LANCZOS)
            self.obrazek_tk = ImageTk.PhotoImage(obrazek)
            self.etykieta_obrazka.configure(image=self.obrazek_tk)
        else:
            self.etykieta_obrazka.configure(image="")

        self.etykieta_naglowek.configure(
            text=f"#{dane['id']} {dane['name'].capitalize()}"
        )

        typy = ", ".join(t["type"]["name"] for t in dane["types"])
        linie_staty = [
            f"Wzrost: {dane['height'] / 10} m    Waga: {dane['weight'] / 10} kg",
            f"Typy: {typy}",
            "",
        ]
        for stat in dane["stats"]:
            linie_staty.append(f"{stat['stat']['name']:<16}: {stat['base_stat']}")
        self.etykieta_staty.configure(text="\n".join(linie_staty))

        self.etykieta_opis.configure(text=textwrap.fill(opis, width=60))
        self.status.set("Gotowe.")


if __name__ == "__main__":
    app = PokedexApp()
    app.mainloop()
