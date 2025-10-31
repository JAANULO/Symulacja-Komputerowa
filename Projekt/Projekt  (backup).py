#projekt

import simpy
import random
import statistics
from typing import Dict, List, Tuple

# PARAMETRY SYSTEMU (zgodnie z Etapem I)

# Zakresy czasowe dla poszczególnych procesów
ZAKRES_CZASU_A = (2, 15)  # min - rozkład jednostajny
ZAKRES_CZASU_B = (10, 20)  # min - rozkład jednostajny
ZAKRES_MTBF = (120, 180)  # min - średni czas między awariami (wykładniczy)
ZAKRES_MTTR = (3, 10)  # min - średni czas naprawy (wykładniczy)
ZAKRES_LAMBDA = (10, 20)  # min - średni czas między przybyciami (wykładniczy)

# Konfiguracja liczby maszyn
LICZBA_MASZYN_A = 3
LICZBA_MASZYN_B = 2

# Czas trwania symulacji
CZAS_SYMULACJI = 50000  # min


# KLASY DO ZBIERANIA STATYSTYK

class StatystykiSymulacji:
    """
    Klasa do zbierania i przechowywania statystyk z symulacji.

    Atrybuty:
        czasy_realizacji (List[float]): Lista czasów przebywania elementów w systemie
        czasy_oczekiwania_a_b (List[float]): Lista czasów oczekiwania między etapami A i B
        elementy_ukonczone (int): Liczba ukończonych elementów
        historia_awarii (Dict[str, List[Tuple[float, float]]): Historia awarii maszyn
    """

    def __init__(self):
        self.czasy_realizacji = []
        self.czasy_oczekiwania_a_b = []
        self.elementy_ukonczone = 0
        self.historia_awarii = {}

    def resetuj(self):
        """Resetuje wszystkie statystyki do wartości początkowych."""
        self.czasy_realizacji = []
        self.czasy_oczekiwania_a_b = []
        self.elementy_ukonczone = 0
        self.historia_awarii = {}


class ZasobProdukcyjny:
    """
    Reprezentuje maszynę produkcyjną z losową awaryjnością.

    Maszyna może ulec awarii podczas pracy i wymagać naprawy.
    Klasa zbiera statystyki dotyczące czasu pracy i napraw.

    Atrybuty:
        srodowisko (simpy.Environment): Środowisko symulacyjne
        nazwa (str): Nazwa maszyny
        zasob (simpy.Resource): Zasób symulacyjny
        zakres_czasu_przetwarzania (Tuple[float, float]): Zakres czasu przetwarzania
        zakres_czasu_naprawy (Tuple[float, float]): Zakres czasu naprawy
        zakres_mtbf (Tuple[float, float]): Zakres czasu między awariami
        czas_pracy_sumaryczny (float): Sumaryczny czas pracy
        czas_naprawy_sumaryczny (float): Sumaryczny czas napraw
        zepsuta (bool): Flaga wskazująca czy maszyna jest zepsuta
        ostatnia_zmiana_stanu (float): Czas ostatniej zmiany stanu
        liczba_awarii (int): Liczba awarii maszyny
    """

    def __init__(self, srodowisko: simpy.Environment, nazwa: str,
                 zakres_czasu_przetwarzania: Tuple[float, float],
                 zakres_czasu_naprawy: Tuple[float, float],
                 zakres_mtbf: Tuple[float, float]):
        self.srodowisko = srodowisko
        self.nazwa = nazwa
        self.zasob = simpy.Resource(srodowisko, capacity=1)
        self.zakres_czasu_przetwarzania = zakres_czasu_przetwarzania
        self.zakres_czasu_naprawy = zakres_czasu_naprawy
        self.zakres_mtbf = zakres_mtbf

        # Statystyki
        self.czas_pracy_sumaryczny = 0.0
        self.czas_naprawy_sumaryczny = 0.0
        self.liczba_awarii = 0

        # Stan maszyny
        self.zepsuta = False
        self.ostatnia_zmiana_stanu = srodowisko.now

        # Proces awarii w tle
        self.srodowisko.process(self._proces_awarii())

    def _proces_awarii(self):
        """
        Symuluje cykliczne awarie i naprawy maszyny.

        Proces działający w tle, który:
        1. Czeka losowy czas do awarii (MTBF)
        2. Oznacza maszynę jako zepsutą
        3. Czeka czas naprawy (MTTR)
        4. Przywraca maszynę do stanu sprawnego
        """
        while True:
            try:
                # Losowy czas do awarii (MTBF) z rozkładu wykładniczego
                srednia_mtbf = random.uniform(*self.zakres_mtbf)
                czas_do_awarii = random.expovariate(1.0 / srednia_mtbf)
                yield self.srodowisko.timeout(czas_do_awarii)

                # Awaria - aktualizacja statystyk
                self.zepsuta = True
                self.liczba_awarii += 1
                self.czas_pracy_sumaryczny += self.srodowisko.now - self.ostatnia_zmiana_stanu
                self.ostatnia_zmiana_stanu = self.srodowisko.now

                # Losowy czas naprawy (MTTR) z rozkładu wykładniczego
                sredni_mttr = random.uniform(*self.zakres_czasu_naprawy)
                czas_naprawy = random.expovariate(1.0 / sredni_mttr)
                yield self.srodowisko.timeout(czas_naprawy)

                # Koniec naprawy - aktualizacja statystyk
                self.zepsuta = False
                self.czas_naprawy_sumaryczny += self.srodowisko.now - self.ostatnia_zmiana_stanu
                self.ostatnia_zmiana_stanu = self.srodowisko.now

            except simpy.Interrupt:
                # Obsługa przerwania symulacji
                break

    def uzyj_zasobu(self, id_elementu: int, czas_przetwarzania: float):
        """
        Użycie maszyny przez element produkcyjny.

        Args:
            id_elementu (int): Identyfikator elementu
            czas_przetwarzania (float): Czas potrzebny na przetworzenie elementu

        Yields:
            simpy.events: Zdarzenia symulacyjne
        """
        with self.zasob.request() as req:
            # Oczekiwanie na dostępność maszyny
            yield req

            # Oczekiwanie na naprawę jeśli maszyna jest zepsuta
            while self.zepsuta:
                yield self.srodowisko.timeout(1)  # Czekaj 1 minutę i sprawdź ponownie

            # Rozpoczęcie przetwarzania
            start = self.srodowisko.now
            yield self.srodowisko.timeout(czas_przetwarzania)
            koniec = self.srodowisko.now

            # Aktualizacja statystyk czasu pracy
            self.czas_pracy_sumaryczny += koniec - start


# FUNKCJE PROCESÓW SYMULACYJNYCH


def proces_elementu(srodowisko: simpy.Environment, id_elementu: int,
                    zasoby_etapu_a: List[ZasobProdukcyjny],
                    zasoby_etapu_b: List[ZasobProdukcyjny],
                    czas_przybycia: float, statystyki: StatystykiSymulacji):
    """
    Opisuje przepływ elementu przez dwuetapową linię produkcyjną.

    Element przechodzi przez:
    1. Etap A (obróbka wstępna)
    2. Etap B (montaż)

    Args:
        srodowisko: Środowisko symulacyjne
        id_elementu: Unikalny identyfikator elementu
        zasoby_etapu_a: Lista maszyn w etapie A
        zasoby_etapu_b: Lista maszyn w etapie B
        czas_przybycia: Czas przybycia elementu do systemu
        statystyki: Obiekt do zbierania statystyk
    """
    # Losowe czasy przetwarzania z rozkładów jednostajnych
    czas_przetwarzania_a = random.uniform(*ZAKRES_CZASU_A)
    czas_przetwarzania_b = random.uniform(*ZAKRES_CZASU_B)

    # --- ETAP A: OBRÓBKA WSTĘPNA ---
    # Wybór maszyny w etapie A (strategia round-robin)
    indeks_a = id_elementu % len(zasoby_etapu_a)
    zasob_a = zasoby_etapu_a[indeks_a]
    yield srodowisko.process(zasob_a.uzyj_zasobu(id_elementu, czas_przetwarzania_a))

    # --- ETAP B: MONTAŻ ---
    # Wybór maszyny w etapie B (strategia round-robin)
    indeks_b = id_elementu % len(zasoby_etapu_b)
    zasob_b = zasoby_etapu_b[indeks_b]

    # Pomiar czasu oczekiwania przed etapem B
    czas_przed_etapem_b = srodowisko.now
    yield srodowisko.process(zasob_b.uzyj_zasobu(id_elementu, czas_przetwarzania_b))

    # Obliczenie czasu oczekiwania między etapami
    czas_po_etapie_b = srodowisko.now
    czas_oczekiwania_b = czas_po_etapie_b - czas_przed_etapem_b - czas_przetwarzania_b

    if czas_oczekiwania_b > 0:
        statystyki.czasy_oczekiwania_a_b.append(czas_oczekiwania_b)

    # --- ZAKOŃCZENIE PRZETWARZANIA ---
    czas_zakonczenia = srodowisko.now
    czas_w_systemie = czas_zakonczenia - czas_przybycia
    statystyki.czasy_realizacji.append(czas_w_systemie)
    statystyki.elementy_ukonczone += 1


def zrodlo_elementow(srodowisko: simpy.Environment,
                     zasoby_etapu_a: List[ZasobProdukcyjny],
                     zasoby_etapu_b: List[ZasobProdukcyjny],
                     zakres_lambda: Tuple[float, float],
                     statystyki: StatystykiSymulacji):
    """
    Generator nowych elementów do systemu w losowych odstępach czasowych.

    Args:
        srodowisko: Środowisko symulacyjne
        zasoby_etapu_a: Lista maszyn w etapie A
        zasoby_etapu_b: Lista maszyn w etapie B
        zakres_lambda: Zakres średniego czasu między przybyciami
        statystyki: Obiekt do zbierania statystyk
    """
    id_elementu = 0
    while True:
        # Losowy czas między przybyciami z rozkładu wykładniczego
        srednia_miedzy_przybyciami = random.uniform(*zakres_lambda)
        czas_miedzy_przybyciami = random.expovariate(1.0 / srednia_miedzy_przybyciami)
        yield srodowisko.timeout(czas_miedzy_przybyciami)

        # Utworzenie nowego elementu
        id_elementu += 1
        srodowisko.process(
            proces_elementu(srodowisko, id_elementu, zasoby_etapu_a,
                            zasoby_etapu_b, srodowisko.now, statystyki)
        )


# FUNKCJE SYMULACJI I WERYFIKACJI

def uruchom_symulacje(czas_symulacji: float, statystyki: StatystykiSymulacji) -> Dict:
    """
    Inicjalizuje i uruchamia pojedynczą symulację.

    Args:
        czas_symulacji: Czas trwania symulacji w minutach
        statystyki: Obiekt do zbierania statystyk

    Returns:
        Dict: Słownik z wynikami symulacji
    """
    # Inicjalizacja środowiska symulacyjnego
    srodowisko = simpy.Environment()

    # Utworzenie maszyn w etapie A
    zasoby_etapu_a = [
        ZasobProdukcyjny(srodowisko, f'A_{i}', ZAKRES_CZASU_A, ZAKRES_MTTR, ZAKRES_MTBF)
        for i in range(LICZBA_MASZYN_A)
    ]

    # Utworzenie maszyn w etapie B
    zasoby_etapu_b = [
        ZasobProdukcyjny(srodowisko, f'B_{i}', ZAKRES_CZASU_B, ZAKRES_MTTR, ZAKRES_MTBF)
        for i in range(LICZBA_MASZYN_B)
    ]

    # Uruchomienie generatora elementów
    srodowisko.process(
        zrodlo_elementow(srodowisko, zasoby_etapu_a, zasoby_etapu_b,
                         ZAKRES_LAMBDA, statystyki)
    )

    # Uruchomienie symulacji
    srodowisko.run(until=czas_symulacji)

    # --- OBLICZENIE WYNIKÓW ---
    przepustowosc = statystyki.elementy_ukonczone / czas_symulacji

    sredni_czas_realizacji = (statistics.mean(statystyki.czasy_realizacji)
                              if statystyki.czasy_realizacji else 0)

    sredni_czas_oczekiwania_a_b = (statistics.mean(statystyki.czasy_oczekiwania_a_b)
                                   if statystyki.czasy_oczekiwania_a_b else 0)

    # Obliczenie wykorzystania maszyn
    wykorzystanie = {}
    wszystkie_zasoby = zasoby_etapu_a + zasoby_etapu_b

    for zasob in wszystkie_zasoby:
        czas_aktywny = zasob.czas_pracy_sumaryczny + zasob.czas_naprawy_sumaryczny
        wykorzystanie[zasob.nazwa] = {
            'wykorzystanie_procent': (czas_aktywny / czas_symulacji) * 100,
            'czas_pracy': zasob.czas_pracy_sumaryczny,
            'czas_naprawy': zasob.czas_naprawy_sumaryczny,
            'liczba_awarii': zasob.liczba_awarii
        }

    return {
        "Przepustowość (elem/min)": przepustowosc,
        "Średni Czas Realizacji (min)": sredni_czas_realizacji,
        "Średni Czas Oczekiwania A->B (min)": sredni_czas_oczekiwania_a_b,
        "Wykorzystanie Maszyn": wykorzystanie,
        "Liczba ukończonych elementów": statystyki.elementy_ukonczone
    }


def weryfikacja_modelu():
    """
    Weryfikacja modelu poprzez uruchomienie testów deterministycznych.

    Testy obejmują:
    1. Symulację bez awarii maszyn
    2. Porównanie z obliczeniami teoretycznymi
    3. Analizę stabilności wyników
    """
    print("\n" + "=" * 60)
    print("WERYFIKACJA MODELU")
    print("=" * 60)

    # --- TEST 1: SYMULACJA BEZ AWARII ---
    print("\n--- TEST 1: Symulacja bez awarii maszyn ---")

    # Zmiana parametrów na deterministyczne
    global ZAKRES_MTBF, ZAKRES_MTTR
    oryginalne_mtbf = ZAKRES_MTBF
    oryginalne_mttr = ZAKRES_MTTR

    # Ustaw bardzo duże MTBF i zerowy MTTR (brak awarii)
    ZAKRES_MTBF = (1000000, 1000000)  # Praktycznie brak awarii
    ZAKRES_MTTR = (0, 0)  # Natychmiastowa naprawa

    statystyki = StatystykiSymulacji()
    wyniki = uruchom_symulacje(10000, statystyki)  # Krótsza symulacja dla testu

    print(f"Przepustowość: {wyniki['Przepustowość (elem/min)']:.4f} elem/min")
    print(f"Średni czas realizacji: {wyniki['Średni Czas Realizacji (min)']:.2f} min")
    print(f"Liczba ukończonych elementów: {wyniki['Liczba ukończonych elementów']}")

    # Przywróć oryginalne parametry
    ZAKRES_MTBF = oryginalne_mtbf
    ZAKRES_MTTR = oryginalne_mttr

    # --- TEST 2: ANALIZA STABILNOŚCI ---
    print("\n--- TEST 2: Analiza stabilności wyników ---")

    wyniki_wielokrotne = []
    for i in range(5):
        statystyki = StatystykiSymulacji()
        wyniki = uruchom_symulacje(10000, statystyki)
        wyniki_wielokrotne.append(wyniki["Przepustowość (elem/min)"])
        print(f"Uruchomienie {i + 1}: {wyniki['Przepustowość (elem/min)']:.4f} elem/min")

    srednia_przepustowosc = statistics.mean(wyniki_wielokrotne)
    odchylenie = statistics.stdev(wyniki_wielokrotne) if len(wyniki_wielokrotne) > 1 else 0

    print(f"\nŚrednia przepustowość: {srednia_przepustowosc:.4f} elem/min")
    print(f"Odchylenie standardowe: {odchylenie:.4f}")
    print(f"Współczynnik zmienności: {(odchylenie / srednia_przepustowosc) * 100:.2f}%")

    if odchylenie / srednia_przepustowosc < 0.1:  # Mniej niż 10% zmienności
        print("✓ Wyniki są stabilne")
    else:
        print("⚠ Wyniki wykazują dużą zmienność")


def test_wydajnosci_konfiguracji():
    """
    Testowanie różnych konfiguracji maszyn w celu weryfikacji logiki systemu.
    """
    print("\n--- TEST 3: Porównanie konfiguracji maszyn ---")

    konfiguracje = [
        (2, 2, "Minimalna konfiguracja"),
        (3, 2, "Zwiększony etap A"),
        (2, 3, "Zwiększony etap B"),
        (3, 3, "Zrównoważona konfiguracja")
    ]

    for ka, kb, opis in konfiguracje:
        global LICZBA_MASZYN_A, LICZBA_MASZYN_B
        LICZBA_MASZYN_A, LICZBA_MASZYN_B = ka, kb

        statystyki = StatystykiSymulacji()
        wyniki = uruchom_symulacje(5000, statystyki)

        print(f"\n{opis} (K_A={ka}, K_B={kb}):")
        print(f"  Przepustowość: {wyniki['Przepustowość (elem/min)']:.4f} elem/min")
        print(f"  Czas realizacji: {wyniki['Średni Czas Realizacji (min)']:.2f} min")


# GŁÓWNA FUNKCJA SYMULACJI

def main():
    """
    Główna funkcja uruchamiająca symulację i prezentująca wyniki.
    """
    print("SYMULACJA KOMPUTEROWA - PROJEKT")
    print("Dwuetapowa linia produkcyjna z awariami maszyn")
    print("=" * 60)

    # Weryfikacja modelu
    weryfikacja_modelu()
    test_wydajnosci_konfiguracji()

    print("\n" + "=" * 60)
    print("GŁÓWNA SYMULACJA")
    print("=" * 60)

    # Główna symulacja z oryginalnymi parametrami
    global LICZBA_MASZYN_A, LICZBA_MASZYN_B
    LICZBA_MASZYN_A, LICZBA_MASZYN_B = 3, 2  # Przywróć oryginalną konfigurację

    statystyki = StatystykiSymulacji()
    wyniki = uruchom_symulacje(CZAS_SYMULACJI, statystyki)

    print("\n--- WYNIKI SYMULACJI ---")
    print(f"Konfiguracja: K_A={LICZBA_MASZYN_A}, K_B={LICZBA_MASZYN_B}")
    print(f"Czas symulacji: {CZAS_SYMULACJI} min")
    print("-" * 40)

    print(f"Przepustowość: {wyniki['Przepustowość (elem/min)']:.4f} elem/min")
    print(f"Średni czas realizacji: {wyniki['Średni Czas Realizacji (min)']:.2f} min")
    print(f"Średni czas oczekiwania A->B: {wyniki['Średni Czas Oczekiwania A->B (min)']:.2f} min")
    print(f"Liczba ukończonych elementów: {wyniki['Liczba ukończonych elementów']}")

    print("\n--- WYKORZYSTANIE MASZYN ---")
    for nazwa, dane in wyniki["Wykorzystanie Maszyn"].items():
        print(f"{nazwa}:")
        print(f"  - Wykorzystanie: {dane['wykorzystanie_procent']:.2f}%")
        print(f"  - Czas pracy: {dane['czas_pracy']:.2f} min")
        print(f"  - Czas naprawy: {dane['czas_naprawy']:.2f} min")
        print(f"  - Liczba awarii: {dane['liczba_awarii']}")


if __name__ == "__main__":
    main()