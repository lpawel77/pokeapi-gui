import io
import textwrap
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import requests
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from PIL import Image, ImageTk

KOLOR_SIATKI = "#e1e0d9"
KOLOR_OSI = "#c3c2b7"
KOLOR_OPISOW = "#898781"
KOLOR_TEKSTU = "#0b0b0b"
KOLOR_TLA_WYKRESU = "#fcfcfb"

NAZWY_STATYSTYK = {
    "hp": "HP",
    "attack": "Atak",
    "defense": "Obrona",
    "special-attack": "Sp. Atak",
    "special-defense": "Sp. Obrona",
    "speed": "Szybkość",
}

KOLORY_STATYSTYK = {
    "hp": "#008300",              # zielony
    "attack": "#e34948",          # czerwony
    "special-attack": "#e34948",  # czerwony
    "defense": "#2a78d6",         # niebieski
    "special-defense": "#2a78d6",  # niebieski
    "speed": "#eda100",           # żółty
}

API_URL = "https://pokeapi.co/api/v2"

_cache_umiejetnosci = {}


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


def wyciagnij_opis(gatunek: dict) -> str:
    for wpis in gatunek["flavor_text_entries"]:
        if wpis["language"]["name"] == "en":
            return wpis["flavor_text"].replace("\x0c", " ").replace("\n", " ")
    return "Brak opisu."


def wyciagnij_kategorie(gatunek: dict) -> str:
    for wpis in gatunek["genera"]:
        if wpis["language"]["name"] == "en":
            return wpis["genus"]
    return "-"


def opis_plci(gender_rate: int) -> str:
    if gender_rate == -1:
        return "Bezpłciowy"
    procent_samica = gender_rate / 8 * 100
    procent_samiec = 100 - procent_samica
    return f"{procent_samiec:.0f}% samiec / {procent_samica:.0f}% samica"


def wyciagnij_przedmioty(dane: dict) -> str:
    nazwy = sorted({h["item"]["name"].replace("-", " ").title() for h in dane["held_items"]})
    return ", ".join(nazwy) if nazwy else "Brak"


def pobierz_efekt_umiejetnosci(url: str) -> str:
    if url in _cache_umiejetnosci:
        return _cache_umiejetnosci[url]
    dane = pobierz_json(url)
    efekt = "Brak opisu."
    for wpis in dane["effect_entries"]:
        if wpis["language"]["name"] == "en":
            efekt = wpis["short_effect"]
            break
    _cache_umiejetnosci[url] = efekt
    return efekt


def pobierz_umiejetnosci_z_efektami(dane: dict) -> list:
    wynik = []
    for a in dane["abilities"]:
        nazwa = a["ability"]["name"].replace("-", " ").title()
        if a["is_hidden"]:
            nazwa += " (ukryta)"
        efekt = pobierz_efekt_umiejetnosci(a["ability"]["url"])
        wynik.append(f"{nazwa} — {efekt}")
    return wynik


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
        self.geometry("1150x800")
        self.minsize(1000, 700)

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

        prawy_kontener = ttk.Frame(self)
        prawy_kontener.pack(side="left", fill="both", expand=True)

        canvas_prawy = tk.Canvas(prawy_kontener, highlightthickness=0)
        scroll_prawy = ttk.Scrollbar(prawy_kontener, orient="vertical", command=canvas_prawy.yview)
        canvas_prawy.configure(yscrollcommand=scroll_prawy.set)
        scroll_prawy.pack(side="right", fill="y")
        canvas_prawy.pack(side="left", fill="both", expand=True)

        prawy = ttk.Frame(canvas_prawy, padding=10)
        okno_prawy = canvas_prawy.create_window((0, 0), window=prawy, anchor="nw")

        def _na_zmiane_ramki(event):
            canvas_prawy.configure(scrollregion=canvas_prawy.bbox("all"))

        def _na_zmiane_canvas(event):
            canvas_prawy.itemconfig(okno_prawy, width=event.width)

        def _scroll_kolko(event):
            canvas_prawy.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_kolko(event):
            canvas_prawy.bind_all("<MouseWheel>", _scroll_kolko)

        def _unbind_kolko(event):
            canvas_prawy.unbind_all("<MouseWheel>")

        prawy.bind("<Configure>", _na_zmiane_ramki)
        canvas_prawy.bind("<Configure>", _na_zmiane_canvas)
        canvas_prawy.bind("<Enter>", _bind_kolko)
        canvas_prawy.bind("<Leave>", _unbind_kolko)

        self.etykieta_obrazka = ttk.Label(prawy)
        self.etykieta_obrazka.pack(pady=(0, 10))

        self.etykieta_naglowek = ttk.Label(prawy, font=("Segoe UI", 14, "bold"))
        self.etykieta_naglowek.pack(anchor="w")

        ttk.Label(prawy, text="Opis:", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(5, 0))
        self.etykieta_opis = ttk.Label(prawy, justify="left", wraplength=650, font=("Segoe UI", 12))
        self.etykieta_opis.pack(anchor="w", pady=(0, 10))

        self.etykieta_staty = ttk.Label(prawy, justify="left", font=("Consolas", 10))
        self.etykieta_staty.pack(anchor="w", pady=(0, 10))

        ramka_wykres_szczegoly = ttk.Frame(prawy)
        ramka_wykres_szczegoly.pack(anchor="w", fill="x", pady=(0, 10))

        kolumna_wykres = ttk.Frame(ramka_wykres_szczegoly)
        kolumna_wykres.pack(side="left", padx=(0, 25))

        self.figura_staty = Figure(figsize=(4.4, 2.4), dpi=90)
        self.figura_staty.patch.set_facecolor(KOLOR_TLA_WYKRESU)
        self.wykres_staty = FigureCanvasTkAgg(self.figura_staty, master=kolumna_wykres)
        self.wykres_staty.get_tk_widget().pack()

        kolumna_szczegoly = ttk.Frame(ramka_wykres_szczegoly)
        kolumna_szczegoly.pack(side="left", anchor="n", fill="both", expand=True)

        ttk.Label(kolumna_szczegoly, text="Informacje o gatunku:", font=("Segoe UI", 11, "bold")).pack(
            anchor="w"
        )
        self.etykieta_szczegoly = ttk.Label(kolumna_szczegoly, justify="left", font=("Consolas", 9))
        self.etykieta_szczegoly.pack(anchor="w")

        ttk.Label(prawy, text="Umiejętności:", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.etykieta_umiejetnosci = ttk.Label(prawy, justify="left", wraplength=650)
        self.etykieta_umiejetnosci.pack(anchor="w", pady=(0, 10))

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
            gatunek = pobierz_json(dane["species"]["url"])
            umiejetnosci = pobierz_umiejetnosci_z_efektami(dane)
            obrazek = pobierz_obrazek(dane)
        except requests.exceptions.HTTPError:
            self.after(0, self._blad_szukania, moj_numer, nazwa_lub_numer, None)
            return
        except requests.exceptions.RequestException as e:
            self.after(0, self._blad_szukania, moj_numer, nazwa_lub_numer, e)
            return

        self.after(0, self._aktualizuj_pokemona, moj_numer, dane, gatunek, umiejetnosci, obrazek)

    def _blad_szukania(self, moj_numer: int, nazwa_lub_numer: str, blad):
        if moj_numer != self._numer_zapytania:
            return  # przyszła odpowiedź na nieaktualne zapytanie - ignorujemy
        self.status.set("Gotowe.")
        if blad is None:
            messagebox.showerror("Nie znaleziono", f"Nie znaleziono Pokémona: {nazwa_lub_numer}")
        else:
            messagebox.showerror("Błąd połączenia", str(blad))

    def _aktualizuj_pokemona(
        self, moj_numer: int, dane: dict, gatunek: dict, umiejetnosci: list, obrazek
    ):
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
            f"Typy: {typy}    Doświadczenie bazowe: {dane['base_experience']}",
        ]
        self.etykieta_staty.configure(text="\n".join(linie_staty))

        self._rysuj_wykres_staty(dane["stats"])

        self.etykieta_umiejetnosci.configure(text="\n".join(umiejetnosci))

        habitat = gatunek["habitat"]["name"] if gatunek["habitat"] else "-"
        egg_groups = ", ".join(g["name"] for g in gatunek["egg_groups"])
        linie_szczegoly = [
            f"Kategoria:       {wyciagnij_kategorie(gatunek)}",
            f"Kolor:           {gatunek['color']['name']}",
            f"Kształt:         {gatunek['shape']['name'] if gatunek['shape'] else '-'}",
            f"Środowisko:      {habitat}",
            f"Legendarny:      {'Tak' if gatunek['is_legendary'] else 'Nie'}",
            f"Mityczny:        {'Tak' if gatunek['is_mythical'] else 'Nie'}",
            f"Baby:            {'Tak' if gatunek['is_baby'] else 'Nie'}",
            f"Grupy jaj:       {egg_groups}",
            f"Płeć:            {opis_plci(gatunek['gender_rate'])}",
            f"Licznik wylęgu:  {gatunek['hatch_counter']}",
            f"Wskaźnik złapania: {gatunek['capture_rate']}/255",
            f"Bazowe szczęście: {gatunek['base_happiness']}",
            f"Tempo wzrostu:   {gatunek['growth_rate']['name']}",
            f"Przedmioty:      {wyciagnij_przedmioty(dane)}",
        ]
        self.etykieta_szczegoly.configure(text="\n".join(linie_szczegoly))

        opis = wyciagnij_opis(gatunek)
        self.etykieta_opis.configure(text=textwrap.fill(opis, width=60))
        self.status.set("Gotowe.")

    def _rysuj_wykres_staty(self, staty: list):
        self.figura_staty.clear()
        ax = self.figura_staty.add_subplot(111)
        ax.set_facecolor(KOLOR_TLA_WYKRESU)

        etykiety = [NAZWY_STATYSTYK.get(s["stat"]["name"], s["stat"]["name"]) for s in staty]
        wartosci = [s["base_stat"] for s in staty]
        kolory = [KOLORY_STATYSTYK.get(s["stat"]["name"], "#2a78d6") for s in staty]

        # odwracamy kolejność, zeby HP wyladowalo na gorze wykresu
        etykiety = etykiety[::-1]
        wartosci = wartosci[::-1]
        kolory = kolory[::-1]

        slupki = ax.barh(etykiety, wartosci, height=0.6, color=kolory)

        for slupek, wartosc in zip(slupki, wartosci):
            ax.text(
                slupek.get_width() + max(wartosci) * 0.02,
                slupek.get_y() + slupek.get_height() / 2,
                str(wartosc),
                va="center",
                ha="left",
                fontsize=9,
                color=KOLOR_TEKSTU,
            )

        ax.set_xlim(0, max(wartosci) * 1.15)
        ax.tick_params(axis="y", colors=KOLOR_TEKSTU, labelsize=9, length=0)
        ax.tick_params(axis="x", colors=KOLOR_OPISOW, labelsize=8)
        ax.grid(axis="x", color=KOLOR_SIATKI, linewidth=0.8)
        ax.set_axisbelow(True)
        for spina in ("top", "right", "left"):
            ax.spines[spina].set_visible(False)
        ax.spines["bottom"].set_color(KOLOR_OSI)

        self.figura_staty.tight_layout()
        self.wykres_staty.draw()


if __name__ == "__main__":
    app = PokedexApp()
    app.mainloop()
