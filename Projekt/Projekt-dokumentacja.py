"""
DOKUMENTACJA KODU - SYMULACJA DWUETAPOWEJ LINII PRODUKCYJNEJ
Projekt z przedmiotu: Symulacja komputerowa
Autorzy: Janusz Andrzejewski, Igor Lis
Semestr: Zimowy 2025/26
"""

import simpy
import random
import statistics
from typing import Dict, List, Tuple

# ============================================================================
# PARAMETRY SYSTEMU (zgodnie z Etapem I)
# ============================================================================

ZAKRES_CZASU_A = (2, 15)      # Czas przetwarzania etapu A [min], rozkład jednostajny
ZAKRES_CZASU_B = (10, 20)     # Czas przetwarzania etapu B [min], rozkład jednostajny
ZAKRES_MTBF = (120, 180)      # Średni czas między awariami [min], rozkład wykładniczy
ZAKRES_MTTR = (3, 10)         # Średni czas naprawy [min], rozkład wykładniczy
ZAKRES_LAMBDA = (10, 20)      # Średni czas między przybyciami elementów [min], wykładniczy

LICZBA_MASZYN_A = 3           # Liczba maszyn w etapie A
LICZBA_MASZYN_B = 2           # Liczba maszyn w etapie B
CZAS_SYMULACJI = 50000        # Czas trwania symulacji [min]

# ============================================================================
# KLASY
# ============================================================================

class StatystykiSymulacji:
    """Klasa do zbierania statystyk z przebiegu symulacji."""

    def __init__(self):
        self.czasy_realizacji = []        # Lista czasów przebywania elementów w systemie (List[float])
        self.czasy_oczekiwania_a_b = []   # Lista czasów oczekiwania między etapami A i B (List[float])
        self.elementy_ukonczone = 0       # Licznik ukończonych elementów (int)

    def resetuj(self):
        """Resetuje statystyki do wartości początkowych."""
        self.czasy_realizacji = []
        self.czasy_oczekiwania_a_b = []
        self.elementy_ukonczone = 0


class ZasobProdukcyjny:
    """Klasa reprezentująca maszynę z mechanizmem losowej awaryjności.
    Maszyna może ulec awarii podczas pracy i wymagać naprawy.
    Klasa zbiera statystyki dotyczące czasu pracy i napraw.
    """

    def __init__(self, srodowisko: simpy.Environment, nazwa: str,
                 zakres_czasu_przetwarzania: Tuple[float, float],
                 zakres_czasu_naprawy: Tuple[float, float],
                 zakres_mtbf: Tuple[float, float]):
        """
        Inicjalizacja maszyny.

        Args:
            srodowisko: Środowisko symulacyjne SimPy
            nazwa: Identyfikator maszyny (np. 'A_0', 'B_1')
            zakres_czasu_przetwarzania: Zakres czasu przetwarzania (min, max)
            zakres_czasu_naprawy: Zakres czasu naprawy MTTR (min, max)
            zakres_mtbf: Zakres czasu między awariami MTBF (min, max)
            czas_pracy_sumaryczny (float): Sumaryczny czas pracy
            czas_naprawy_sumaryczny (float): Sumaryczny czas napraw
            zepsuta (bool): Flaga wskazująca czy maszyna jest zepsuta
            ostatnia_zmiana_stanu (float): Czas ostatniej zmiany stanu
            liczba_awarii (int): Liczba awarii maszyny
        """
        self.srodowisko = srodowisko
        self.nazwa = nazwa
        self.zasob = simpy.Resource(srodowisko, capacity=1)  # Pojedynczy zasób SimPy

        # Parametry czasowe
        self.zakres_czasu_przetwarzania = zakres_czasu_przetwarzania
        self.zakres_czasu_naprawy = zakres_czasu_naprawy
        self.zakres_mtbf = zakres_mtbf

        # Statystyki maszyny
        self.czas_pracy_sumaryczny = 0.0
        self.czas_naprawy_sumaryczny = 0.0
        self.liczba_awarii = 0

        # Stan maszyny
        self.zepsuta = False
        self.ostatnia_zmiana_stanu = srodowisko.now

        # Uruchomienie procesu awarii w tle
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
                # Losowanie czasu do następnej awarii
                # MTBF jest losowany z rozkładu jednostajnego, a czas awarii z wykładniczego

                srednia_mtbf = random.uniform(*self.zakres_mtbf)
                czas_do_awarii = random.expovariate(1.0 / srednia_mtbf)
                yield self.srodowisko.timeout(czas_do_awarii)

                # Awaria - aktualizacja stanu i statystyk
                self.zepsuta = True
                self.liczba_awarii += 1
                self.czas_pracy_sumaryczny += self.srodowisko.now - self.ostatnia_zmiana_stanu
                self.ostatnia_zmiana_stanu = self.srodowisko.now

                # Losowanie czasu naprawy
                # MTTR jest losowany z rozkładu jednostajnego, a czas naprawy z wykładniczego

                sredni_mttr = random.uniform(*self.zakres_czasu_naprawy)
                czas_naprawy = random.expovariate(1.0 / sredni_mttr)
                yield self.srodowisko.timeout(czas_naprawy)

                # Naprawa zakończona - powrót do pracy
                self.zepsuta = False
                self.czas_naprawy_sumaryczny += self.srodowisko.now - self.ostatnia_zmiana_stanu
                self.ostatnia_zmiana_stanu = self.srodowisko.now

            except simpy.Interrupt:
                break  # Przerwanie symulacji

    def uzyj_zasobu(self, id_elementu: int, czas_przetwarzania: float):
        """
        Proces użycia maszyny przez element produkcyjny.

        Args:
            id_elementu: Identyfikator elementu
            czas_przetwarzania: Wymagany czas przetwarzania [min]
        Yields:
            simpy.events: Zdarzenia symulacyjne

        Proces:
            1. Oczekiwanie na dostępność maszyny
            2. Oczekiwanie na naprawę jeśli maszyna jest zepsuta
            3. Przetwarzanie elementu
            4. Aktualizacja statystyk czasu pracy

        """
        with self.zasob.request() as req:
            yield req  # Oczekiwanie na dostępność maszyny

            # Jeśli maszyna zepsuta, czekaj na naprawę
            while self.zepsuta:
                yield self.srodowisko.timeout(1)  # Sprawdzaj co 1 minutę

            # Przetwarzanie elementu
            start = self.srodowisko.now
            yield self.srodowisko.timeout(czas_przetwarzania)
            koniec = self.srodowisko.now

            # Aktualizacja czasu pracy
            self.czas_pracy_sumaryczny += koniec - start

# ============================================================================
# PROCESY SYMULACYJNE
# ============================================================================

def proces_elementu(srodowisko: simpy.Environment, id_elementu: int,
                   zasoby_etapu_a: List[ZasobProdukcyjny],
                   zasoby_etapu_b: List[ZasobProdukcyjny],
                   czas_przybycia: float, statystyki: StatystykiSymulacji):
    """
    Proces opisujący przepływ pojedynczego elementu przez system.
    Element przechodzi przez
    1. Etap A (obróbka)
    2. Etap B (montaż)

    Args:
        srodowisko: Środowisko symulacyjne
        id_elementu: Unikalny identyfikator elementu
        zasoby_etapu_a: Lista maszyn dostępnych w etapie A
        zasoby_etapu_b: Lista maszyn dostępnych w etapie B
        czas_przybycia: Moment przybycia elementu do systemu
        statystyki: Obiekt do zbierania statystyk
    """
    # Losowanie czasów przetwarzania (rozkład jednostajny)
    czas_przetwarzania_a = random.uniform(*ZAKRES_CZASU_A)
    czas_przetwarzania_b = random.uniform(*ZAKRES_CZASU_B)

    # --- ETAP A: OBRÓBKA WSTĘPNA ---
    # Wybór maszyny (strategia round-robin)
    indeks_a = id_elementu % len(zasoby_etapu_a)
    zasob_a = zasoby_etapu_a[indeks_a]
    yield srodowisko.process(zasob_a.uzyj_zasobu(id_elementu, czas_przetwarzania_a))

    # --- ETAP B: MONTAŻ ---
    # Wybór maszyny (strategia round-robin)
    indeks_b = id_elementu % len(zasoby_etapu_b)
    zasob_b = zasoby_etapu_b[indeks_b]

    czas_przed_etapem_b = srodowisko.now
    yield srodowisko.process(zasob_b.uzyj_zasobu(id_elementu, czas_przetwarzania_b))
    czas_po_etapie_b = srodowisko.now

    # Obliczenie czasu oczekiwania między etapami
    czas_oczekiwania = czas_po_etapie_b - czas_przed_etapem_b - czas_przetwarzania_b
    if czas_oczekiwania > 0:
        statystyki.czasy_oczekiwania_a_b.append(czas_oczekiwania)

    # Obliczenie całkowitego czasu w systemie
    czas_w_systemie = srodowisko.now - czas_przybycia
    statystyki.czasy_realizacji.append(czas_w_systemie)
    statystyki.elementy_ukonczone += 1


def zrodlo_elementow(srodowisko: simpy.Environment,
                    zasoby_etapu_a: List[ZasobProdukcyjny],
                    zasoby_etapu_b: List[ZasobProdukcyjny],
                    zakres_lambda: Tuple[float, float],
                    statystyki: StatystykiSymulacji):
    """
    Generator nowych elementów - proces źródłowy.
    Elementy przybywają w losowych odstępach czasu (rozkład wykładniczy).

    Args:
        srodowisko: Środowisko symulacyjne
        zasoby_etapu_a: Lista maszyn etapu A
        zasoby_etapu_b: Lista maszyn etapu B
        zakres_lambda: Zakres średniego czasu między przybyciami
        statystyki: Obiekt do zbierania statystyk
    """
    id_elementu = 0

    while True:
        # Losowanie czasu do następnego przybycia (rozkład wykładniczy)
        srednia_miedzy_przybyciami = random.uniform(*zakres_lambda)
        czas_miedzy_przybyciami = random.expovariate(1.0 / srednia_miedzy_przybyciami)
        yield srodowisko.timeout(czas_miedzy_przybyciami)

        # Utworzenie nowego elementu
        id_elementu += 1
        srodowisko.process(
            proces_elementu(srodowisko, id_elementu, zasoby_etapu_a,
                          zasoby_etapu_b, srodowisko.now, statystyki)
        )

# ============================================================================
# FUNKCJA GŁÓWNA SYMULACJI
# ============================================================================

def uruchom_symulacje(czas_symulacji: float, 
                     statystyki: StatystykiSymulacji) -> Dict:
    """
    Główna funkcja inicjalizująca i uruchamiająca symulację.

    Args:
        czas_symulacji: Czas trwania symulacji [min]
        statystyki: Obiekt do zbierania statystyk

    Returns:
        Dict: Słownik z wynikami symulacji (przepustowość, czasy, wykorzystanie)
    """
    # Inicjalizacja środowiska SimPy
    srodowisko = simpy.Environment()

    # Utworzenie maszyn w etapie A
    zasoby_etapu_a = [
        ZasobProdukcyjny(srodowisko, f'A_{i}', ZAKRES_CZASU_A, 
                        ZAKRES_MTTR, ZAKRES_MTBF)
        for i in range(LICZBA_MASZYN_A)
    ]

    # Utworzenie maszyn w etapie B
    zasoby_etapu_b = [
        ZasobProdukcyjny(srodowisko, f'B_{i}', ZAKRES_CZASU_B, 
                        ZAKRES_MTTR, ZAKRES_MTBF)
        for i in range(LICZBA_MASZYN_B)
    ]

    # Uruchomienie generatora elementów
    srodowisko.process(
        zrodlo_elementow(srodowisko, zasoby_etapu_a, zasoby_etapu_b,
                        ZAKRES_LAMBDA, statystyki)
    )

    # Uruchomienie symulacji
    srodowisko.run(until=czas_symulacji)

    # --- OBLICZENIE WSKAŹNIKÓW ---

    # Przepustowość systemu [elem/min]
    przepustowosc = statystyki.elementy_ukonczone / czas_symulacji

    # Średni czas realizacji [min]
    sredni_czas_realizacji = (statistics.mean(statystyki.czasy_realizacji)
                              if statystyki.czasy_realizacji else 0)

    # Średni czas oczekiwania między etapami [min]
    sredni_czas_oczekiwania = (statistics.mean(statystyki.czasy_oczekiwania_a_b)
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

    # Zwrócenie wyników
    return {
        "Przepustowość (elem/min)": przepustowosc,
        "Średni Czas Realizacji (min)": sredni_czas_realizacji,
        "Średni Czas Oczekiwania A->B (min)": sredni_czas_oczekiwania,
        "Wykorzystanie Maszyn": wykorzystanie,
        "Liczba ukończonych elementów": statystyki.elementy_ukonczone
    }

# ============================================================================
# FUNKCJE WERYFIKACJI MODELU
# ============================================================================

def weryfikacja_modelu():
    """
    Weryfikacja modelu poprzez uruchomienie testów deterministycznych.

    Przeprowadza testy:
    1. Symulację bez awarii maszyn (deterministyczna weryfikacja)
    2. Analizę stabilności (wielokrotne uruchomienia)
    3. Test wydajności konfiguracjii
    """
    print("=" * 60)
    print("WERYFIKACJA MODELU")
    print("=" * 60)

    # --- TEST 1: Symulacja bez awarii ---
    print("\n--- TEST 1: Symulacja bez awarii maszyn ---")

    global ZAKRES_MTBF, ZAKRES_MTTR
    oryginalne_mtbf = ZAKRES_MTBF
    oryginalne_mttr = ZAKRES_MTTR

    # Eliminacja awarii (bardzo długi MTBF, zerowy MTTR)
    ZAKRES_MTBF = (1000000, 1000000)
    ZAKRES_MTTR = (0, 0)

    statystyki = StatystykiSymulacji()
    wyniki = uruchom_symulacje(10000, statystyki)

    print(f"Przepustowość: {wyniki['Przepustowość (elem/min)']:.4f} elem/min")
    print(f"Średni czas realizacji: {wyniki['Średni Czas Realizacji (min)']:.2f} min")
    print(f"Liczba ukończonych elementów: {wyniki['Liczba ukończonych elementów']}")

    # Przywrócenie oryginalnych parametrów
    ZAKRES_MTBF = oryginalne_mtbf
    ZAKRES_MTTR = oryginalne_mttr

    # --- TEST 2: Analiza stabilności ---
    print("\n--- TEST 2: Analiza stabilności wyników ---")
    wyniki_wielokrotne = []

    for i in range(5):
        statystyki = StatystykiSymulacji()
        wyniki = uruchom_symulacje(10000, statystyki)
        wyniki_wielokrotne.append(wyniki["Przepustowość (elem/min)"])
        print(f"Uruchomienie {i + 1}: {wyniki['Przepustowość (elem/min)']:.4f} elem/min")

    srednia = statistics.mean(wyniki_wielokrotne)
    odchylenie = statistics.stdev(wyniki_wielokrotne) if len(wyniki_wielokrotne) > 1 else 0

    print(f"\nŚrednia przepustowość: {srednia:.4f} elem/min")
    print(f"Odchylenie standardowe: {odchylenie:.4f}")
    print(f"Współczynnik zmienności: {(odchylenie / srednia) * 100:.2f}%")

    if odchylenie / srednia < 0.1:
        print("✓ Wyniki są stabilne")
    else:
        print("⚠ Wyniki wykazują dużą zmienność")

def test_wydajnosci_konfiguracji():
    """
    Testowanie różnych konfiguracji maszyn w celu weryfikacji logiki systemu.
    """
    print("\n--- TEST 3: Porównanie konfiguracji maszyn ---")

    # Definicja testowanych konfiguracji (maszyny_A, maszyny_B, opis)
    konfiguracje = [
        (2, 2, "Minimalna konfiguracja"),
        (3, 2, "Zwiększony etap A"),
        (2, 3, "Zwiększony etap B"),
        (3, 3, "Zrównoważona konfiguracja")
    ]

    for ka, kb, opis in konfiguracje:
        # Zmiana konfiguracji maszyn
        global LICZBA_MASZYN_A, LICZBA_MASZYN_B
        LICZBA_MASZYN_A, LICZBA_MASZYN_B = ka, kb

        # Uruchomienie symulacji dla danej konfiguracji
        statystyki = StatystykiSymulacji()
        wyniki = uruchom_symulacje(5000, statystyki)

        # Prezentacja wyników
        print(f"\n{opis} (K_A={ka}, K_B={kb}):")
        print(f"  Przepustowość: {wyniki['Przepustowość (elem/min)']:.4f} elem/min")
        print(f"  Czas realizacji: {wyniki['Średni Czas Realizacji (min)']:.2f} min")


# GŁÓWNA FUNKCJA SYMULACJI

def main():
    """
    Główna funkcja uruchamiająca symulację i prezentująca wyniki.

    Przeprowadza:
    1. Weryfikację modelu
    2. Testy konfiguracji
    3. Główną symulację z oryginalnymi parametrami
    """
    print("SYMULACJA KOMPUTEROWA - PROJEKT")
    print("Dwuetapowa linia produkcyjna z awariami maszyn")

    # Weryfikacja modelu
    weryfikacja_modelu()
    test_wydajnosci_konfiguracji()

    print("\n" + "=" * 60)
    print("GŁÓWNA SYMULACJA")
    print("=" * 60)

    # Główna symulacja z oryginalnymi parametrami
    global LICZBA_MASZYN_A, LICZBA_MASZYN_B
    LICZBA_MASZYN_A, LICZBA_MASZYN_B = 3, 2  # Przywróć oryginalną konfigurację

    # Uruchomienie głównej symulacji
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
    """
    Uruchamianie główną funkcję symulacji.
    """