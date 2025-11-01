import simpy
import random
import statistics

# --- 1. PARAMETRY SYSTEMU (zgodnie z Etapem I) ---

ZAKRES_CZASU_A = (2, 15)     # min - jednostajny
ZAKRES_CZASU_B = (10, 20)    # min - jednostajny
ZAKRES_MTBF = (120, 180)     # min - wykładniczy
ZAKRES_MTTR = (3, 10)        # min - wykładniczy
ZAKRES_LAMBDA = (10, 20)     # min - wykładniczy

LICZBA_MASZYN_A = 3
LICZBA_MASZYN_B = 2

CZAS_SYMULACJI = 50000

# --- 2. ZBIERANIE WYNIKÓW ---
CZASY_REALIZACJI = []
CZASY_OCZEKIWANIA_A_B = []
ELEMENTY_UKONCZONE = 0


# --- 3. KLASA MASZYNY Z AWARIĄ ---

class ZasobProdukcyjny:
    """Reprezentuje maszynę produkcyjną z losową awaryjnością."""

    def __init__(self, srodowisko, nazwa, zakres_czasu_przetwarzania, zakres_czasu_naprawy, zakres_mtbf):
        self.srodowisko = srodowisko
        self.nazwa = nazwa
        self.zasob = simpy.Resource(srodowisko, capacity=1)
        self.zakres_czasu_przetwarzania = zakres_czasu_przetwarzania
        self.zakres_czasu_naprawy = zakres_czasu_naprawy
        self.zakres_mtbf = zakres_mtbf

        # Statystyki
        self.czas_pracy_sumaryczny = 0.0
        self.czas_naprawy_sumaryczny = 0.0

        # Stan maszyny
        self.zepsuta = False
        self.ostatnia_zmiana_stanu = srodowisko.now

        # Proces awarii w tle
        self.srodowisko.process(self.proces_awarii())

    def proces_awarii(self):
        """Symuluje cykliczne awarie i naprawy maszyny."""
        while True:
            # Losowy czas do awarii (MTBF)
            srednia_mtbf = random.uniform(*self.zakres_mtbf)
            czas_do_awarii = random.expovariate(1.0 / srednia_mtbf)
            yield self.srodowisko.timeout(czas_do_awarii)

            # Awaria!
            self.zepsuta = True
            self.czas_pracy_sumaryczny += self.srodowisko.now - self.ostatnia_zmiana_stanu
            self.ostatnia_zmiana_stanu = self.srodowisko.now

            # Czas naprawy (MTTR)
            sredni_mttr = random.uniform(*self.zakres_czasu_naprawy)
            czas_naprawy = random.expovariate(1.0 / sredni_mttr)
            yield self.srodowisko.timeout(czas_naprawy)

            # Naprawa zakończona
            self.zepsuta = False
            self.czas_naprawy_sumaryczny += self.srodowisko.now - self.ostatnia_zmiana_stanu
            self.ostatnia_zmiana_stanu = self.srodowisko.now

    def uzyj_zasobu(self, id_elementu, czas_przetwarzania):
        """Użycie maszyny przez element produkcyjny."""
        with self.zasob.request() as req:
            yield req

            # Jeśli maszyna jest zepsuta — czekaj na naprawę
            while self.zepsuta:
                yield self.srodowisko.timeout(1)

            start = self.srodowisko.now
            yield self.srodowisko.timeout(czas_przetwarzania)
            koniec = self.srodowisko.now

            self.czas_pracy_sumaryczny += koniec - start


# --- 4. PROCES ELEMENTU ---

def proces_elementu(srodowisko, id_elementu, zasoby_etapu_a, zasoby_etapu_b, czas_przybycia):
    """Opisuje przepływ elementu przez dwuetapową linię produkcyjną."""
    global ELEMENTY_UKONCZONE

    czas_przetwarzania_a = random.uniform(*ZAKRES_CZASU_A)
    czas_przetwarzania_b = random.uniform(*ZAKRES_CZASU_B)

    # --- ETAP A ---
    indeks_a = id_elementu % LICZBA_MASZYN_A
    zasob_a = zasoby_etapu_a[indeks_a]
    yield srodowisko.process(zasob_a.uzyj_zasobu(id_elementu, czas_przetwarzania_a))

    # --- ETAP B ---
    indeks_b = id_elementu % LICZBA_MASZYN_B
    zasob_b = zasoby_etapu_b[indeks_b]
    czas_przed_oczekiwaniem_b = srodowisko.now

    yield srodowisko.process(zasob_b.uzyj_zasobu(id_elementu, czas_przetwarzania_b))

    czas_oczekiwania_b = srodowisko.now - czas_przed_oczekiwaniem_b - czas_przetwarzania_b
    if czas_oczekiwania_b > 0:
        CZASY_OCZEKIWANIA_A_B.append(czas_oczekiwania_b)

    # --- ZAKOŃCZENIE ---
    czas_zakonczenia = srodowisko.now
    czas_w_systemie = czas_zakonczenia - czas_przybycia
    CZASY_REALIZACJI.append(czas_w_systemie)
    ELEMENTY_UKONCZONE += 1


# --- 5. GENERATOR ELEMENTÓW ---

def zrodlo(srodowisko, zasoby_etapu_a, zasoby_etapu_b, zakres_lambda):
    """Generuje nowe elementy do systemu w losowych odstępach."""
    id_elementu = 0
    while True:
        srednia_miedzy_przybyciami = random.uniform(*zakres_lambda)
        czas_miedzy_przybyciami = random.expovariate(1.0 / srednia_miedzy_przybyciami)
        yield srodowisko.timeout(czas_miedzy_przybyciami)

        id_elementu += 1
        srodowisko.process(proces_elementu(srodowisko, id_elementu, zasoby_etapu_a, zasoby_etapu_b, srodowisko.now))


# --- 6. GŁÓWNA FUNKCJA SYMULACJI ---

def uruchom_symulacje(czas_symulacji):
    """Inicjalizuje i uruchamia symulację."""
    global CZASY_REALIZACJI, CZASY_OCZEKIWANIA_A_B, ELEMENTY_UKONCZONE

    CZASY_REALIZACJI = []
    CZASY_OCZEKIWANIA_A_B = []
    ELEMENTY_UKONCZONE = 0

    srodowisko = simpy.Environment()

    # Zasoby etapu A
    zasoby_etapu_a = [
        ZasobProdukcyjny(srodowisko, f'A_{i}', ZAKRES_CZASU_A, ZAKRES_MTTR, ZAKRES_MTBF)
        for i in range(LICZBA_MASZYN_A)
    ]

    # Zasoby etapu B
    zasoby_etapu_b = [
        ZasobProdukcyjny(srodowisko, f'B_{i}', ZAKRES_CZASU_B, ZAKRES_MTTR, ZAKRES_MTBF)
        for i in range(LICZBA_MASZYN_B)
    ]

    # Generator elementów
    srodowisko.process(zrodlo(srodowisko, zasoby_etapu_a, zasoby_etapu_b, ZAKRES_LAMBDA))

    # Uruchomienie symulacji
    srodowisko.run(until=czas_symulacji)

    # --- WYNIKI ---
    przepustowosc = ELEMENTY_UKONCZONE / czas_symulacji
    sredni_czas_realizacji = statistics.mean(CZASY_REALIZACJI) if CZASY_REALIZACJI else 0
    sredni_czas_oczekiwania_a_b = statistics.mean(CZASY_OCZEKIWANIA_A_B) if CZASY_OCZEKIWANIA_A_B else 0

    wykorzystanie = {}
    wszystkie_zasoby = zasoby_etapu_a + zasoby_etapu_b

    for zasob in wszystkie_zasoby:
        czas_aktywny = zasob.czas_pracy_sumaryczny + zasob.czas_naprawy_sumaryczny
        wykorzystanie[zasob.nazwa] = czas_aktywny / czas_symulacji

    return {
        "Przepustowość (elem/min)": przepustowosc,
        "Średni Czas Realizacji (min)": sredni_czas_realizacji,
        "Średni Czas Oczekiwania A->B (min)": sredni_czas_oczekiwania_a_b,
        "Wykorzystanie Maszyn (Praca + Naprawa)": wykorzystanie
    }


# --- 7. URUCHOMIENIE SYMULACJI ---

wyniki = uruchom_symulacje(CZAS_SYMULACJI)

print("\n--- WYNIKI SYMULACJI (K_A={}, K_B={}, Czas: {} min) ---".format(
    LICZBA_MASZYN_A, LICZBA_MASZYN_B, CZAS_SYMULACJI
))
for klucz, wartosc in wyniki.items():
    if klucz == "Wykorzystanie Maszyn (Praca + Naprawa)":
        print(f"\n{klucz}:")
        for nazwa_zasobu, wykorzystanie_procent in wartosc.items():
            print(f"  {nazwa_zasobu}: {wykorzystanie_procent * 100:.2f}%")
    else:
        print(f"{klucz}: {wartosc:.4f}")
