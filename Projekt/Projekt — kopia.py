import simpy
import random
import statistics

# --- 1. PARAMETRY SYSTEMU (zgodnie z Etapem I) ---
# Zakresy do generowania rozkładów losowych
ZAKRES_CZASU_A = (2, 15)  # min - jednostajny
ZAKRES_CZASU_B = (10, 20)  # min - jednostajny
ZAKRES_MTBF = (120, 180)  # min - parametr dla losowania średniej MTBF
ZAKRES_MTTR = (3, 10)  # min - parametr dla losowania średniej MTTR
ZAKRES_LAMBDA = (10, 20)  # min - parametr dla losowania średniego czasu między przybyciami

# Wybrana konfiguracja
LICZBA_MASZYN_A = 3
LICZBA_MASZYN_B = 2

# Czas symulacji (wystarczająco długi, aby uzyskać stabilne wyniki)
CZAS_SYMULACJI = 50000

# --- 2. ZBIERANIE WYNIKÓW ---
CZASY_REALIZACJI = []
CZASY_OCZEKIWANIA_A_B = []
ELEMENTY_UKONCZONE = 0


# --- 3. KLASA MASZYNY Z AWARIĄ (ZASOB PRODUKCYJNY) ---

class ZasobProdukcyjny:
    """Reprezentuje maszynę produkcyjną z losową awaryjnością."""

    def __init__(self, srodowisko, nazwa, zakres_czasu_przetwarzania, zakres_czasu_naprawy, zakres_mtbf):
        self.srodowisko = srodowisko
        self.nazwa = nazwa
        self.zasob = simpy.Resource(srodowisko, capacity=1)
        self.zakres_czasu_przetwarzania = zakres_czasu_przetwarzania

        # przechowujemy przekazane zakresy jako atrybuty
        self.zakres_czasu_naprawy = zakres_czasu_naprawy
        self.zakres_mtbf = zakres_mtbf

        # Statystyki
        self.czas_pracy_sumaryczny = 0.0
        self.czas_naprawy_sumaryczny = 0.0

        # Stan
        self.zepsuta = False
        self.ostatnia_zmiana_stanu = srodowisko.now

        # Uruchamiamy proces awarii
        self.srodowisko.process(self.proces_awarii())

    def proces_awarii(self):
        """Proces, który losowo psuje maszynę i ją naprawia."""
        while True:
            # 1. Najpierw losujemy "średnią" MTBF z zadanego zakresu (można interpretować jako niepewność)
            srednia_mtbf = random.uniform(*self.zakres_mtbf)
            # Czas do awarii: rozkład wykładniczy o średniej = srednia_mtbf
            czas_do_awarii = random.expovariate(1.0 / srednia_mtbf)

            yield self.srodowisko.timeout(czas_do_awarii)

            # --- Maszyna ulega awarii ---
            self.zepsuta = True
            self.ostatnia_zmiana_stanu = self.srodowisko.now

            # Jeśli ktoś aktualnie używa zasobu — spróbuj przerwać ten proces
            if self.zasob.users:
                # request = self.zasob.users[0]  # typ: Request
                req = self.zasob.users[0]
                # Niektóre wersje SimPy mają .proc, więc zabezpieczamy się
                proc = getattr(req, 'proc', None)
                if proc is not None:
                    try:
                        proc.interrupt()
                    except Exception:
                        # jeśli przerwanie się nie powiedzie, po prostu kontynuujemy — i tak czekamy na naprawę
                        pass

            # 2. Czas naprawy: najpierw losujemy średni MTTR z zadanego zakresu, potem próbka wykładnicza
            srednia_mttr = random.uniform(*self.zakres_czasu_naprawy)
            czas_naprawy = random.expovariate(1.0 / srednia_mttr)

            start_naprawy = self.srodowisko.now
            yield self.srodowisko.timeout(czas_naprawy)
            self.czas_naprawy_sumaryczny += (self.srodowisko.now - start_naprawy)

            # Maszyna naprawiona
            self.zepsuta = False
            self.ostatnia_zmiana_stanu = self.srodowisko.now

    def uzyj_zasobu(self, id_elementu, oryginalny_czas_przetwarzania):
        """Użycie maszyny do przetworzenia elementu, z obsługą przerwań (awarii)."""
        with self.zasob.request() as zgloszenie:
            yield zgloszenie

            # Jeśli maszyna jest zepsuta w momencie rozpoczęcia, czekamy aż będzie sprawna
            while self.zepsuta:
                yield self.srodowisko.timeout(1)

            # Przetwarzamy element; jeśli nastąpi przerwanie to obsłużymy je i poczekamy na naprawę
            czas_pozostaly = oryginalny_czas_przetwarzania
            while czas_pozostaly > 0:
                start_czasu_przetwarzania = self.srodowisko.now
                try:
                    # próbujemy przetworzyć pozostały czas
                    yield self.srodowisko.timeout(czas_pozostaly)
                    # jeśli doszliśmy tutaj bez przerwania — zapisujemy czas pracy
                    czas_pracy = self.srodowisko.now - start_czasu_przetwarzania
                    self.czas_pracy_sumaryczny += czas_pracy
                    czas_pozostaly = 0
                except simpy.Interrupt:
                    # przerwane wskutek awarii — naliczamy przetworzony fragment
                    czas_przetworzony = self.srodowisko.now - start_czasu_przetwarzania
                    if czas_przetworzony > 0:
                        self.czas_pracy_sumaryczny += czas_przetworzony
                    czas_pozostaly -= czas_przetworzony

                    # czekamy aż maszyna zostanie naprawiona
                    while self.zepsuta:
                        yield self.srodowisko.timeout(1)


# --- 4. PROCES ELEMENTU ---

def proces_elementu(srodowisko, id_elementu, zasoby_etapu_a, zasoby_etapu_b, czas_przybycia):
    """Opisuje przepływ elementu przez dwuetapową linię produkcyjną."""
    global ELEMENTY_UKONCZONE

    # Losowanie czasu przetwarzania dla Etapu A i B
    czas_przetwarzania_a = random.uniform(*ZAKRES_CZASU_A)
    czas_przetwarzania_b = random.uniform(*ZAKRES_CZASU_B)

    # ------------------- ETAP A (Obróbka wstępna) -------------------
    indeks_a = id_elementu % LICZBA_MASZYN_A
    zasob_a = zasoby_etapu_a[indeks_a]

    yield srodowisko.process(zasob_a.uzyj_zasobu(id_elementu, czas_przetwarzania_a))

    # ------------------- ETAP B (Montaż) -------------------

    indeks_b = id_elementu % LICZBA_MASZYN_B
    zasob_b = zasoby_etapu_b[indeks_b]

    czas_przed_oczekiwaniem_b = srodowisko.now

    # Użycie zasobu B
    yield srodowisko.process(zasob_b.uzyj_zasobu(id_elementu, czas_przetwarzania_b))

    # Czas oczekiwania między etapami (przybliżony)
    czas_oczekiwania_b = srodowisko.now - czas_przed_oczekiwaniem_b - czas_przetwarzania_b
    if czas_oczekiwania_b > 0:
        CZASY_OCZEKIWANIA_A_B.append(czas_oczekiwania_b)

    # ------------------- ZAKOŃCZENIE -------------------
    czas_zakonczenia = srodowisko.now

    czas_w_systemie = czas_zakonczenia - czas_przybycia
    CZASY_REALIZACJI.append(czas_w_systemie)
    ELEMENTY_UKONCZONE += 1


# --- 5. GENERATOR ELEMENTÓW ---

def zrodlo(srodowisko, zasoby_etapu_a, zasoby_etapu_b, zakres_lambda):
    """Generuje elementy do systemu."""
    id_elementu = 0
    while True:
        # Losowy czas przybycia (średnia losowana z zakresu, potem próbka wykładnicza)
        srednia_miedzy_przybyciami = random.uniform(*zakres_lambda)
        czas_miedzy_przybyciami = random.expovariate(1.0 / srednia_miedzy_przybyciami)

        yield srodowisko.timeout(czas_miedzy_przybyciami)

        id_elementu += 1
        srodowisko.process(proces_elementu(srodowisko, id_elementu, zasoby_etapu_a, zasoby_etapu_b, srodowisko.now))


# --- 6. GŁÓWNA FUNKCJA SYMULACJI I WYNIKI ---

def uruchom_symulacje(czas_symulacji):
    """Inicjalizuje i uruchamia symulację."""
    global CZASY_REALIZACJI, CZASY_OCZEKIWANIA_A_B, ELEMENTY_UKONCZONE

    # Resetowanie danych dla każdego uruchomienia
    CZASY_REALIZACJI = []
    CZASY_OCZEKIWANIA_A_B = []
    ELEMENTY_UKONCZONE = 0

    srodowisko = simpy.Environment()

    # Inicjalizacja zasobów Etapu A
    zasoby_etapu_a = [
        ZasobProdukcyjny(srodowisko, f'A_{i}', ZAKRES_CZASU_A, ZAKRES_MTTR, ZAKRES_MTBF)
        for i in range(LICZBA_MASZYN_A)
    ]

    # Inicjalizacja zasobów Etapu B
    zasoby_etapu_b = [
        ZasobProdukcyjny(srodowisko, f'B_{i}', ZAKRES_CZASU_B, ZAKRES_MTTR, ZAKRES_MTBF)
        for i in range(LICZBA_MASZYN_B)
    ]

    # Uruchomienie generatora elementów
    srodowisko.process(zrodlo(srodowisko, zasoby_etapu_a, zasoby_etapu_b, ZAKRES_LAMBDA))

    # Uruchomienie symulacji
    srodowisko.run(until=czas_symulacji)

    # --- Zbieranie wskaźników ---
    przepustowosc = ELEMENTY_UKONCZONE / czas_symulacji
    sredni_czas_realizacji = statistics.mean(CZASY_REALIZACJI) if CZASY_REALIZACJI else 0
    sredni_czas_oczekiwania_a_b = statistics.mean(CZASY_OCZEKIWANIA_A_B) if CZASY_OCZEKIWANIA_A_B else 0

    wykorzystanie = {}
    wszystkie_zasoby = zasoby_etapu_a + zasoby_etapu_b
    for zasob in wszystkie_zasoby:
        # Wykorzystanie maszyn (sumaryczny czas pracy + czas naprawy podzielony przez czas symulacji)
        czas_aktywny = zasob.czas_pracy_sumaryczny + zasob.czas_naprawy_sumaryczny
        wykorzystanie[zasob.nazwa] = czas_aktywny / czas_symulacji

    return {
        "Przepustowość (elem/min)": przepustowosc,
        "Średni Czas Realizacji (min)": sredni_czas_realizacji,
        "Średni Czas Oczekiwania A->B (min)": sredni_czas_oczekiwania_a_b,
        "Wykorzystanie Maszyn (Praca + Naprawa)": wykorzystanie
    }


# Uruchomienie i wyświetlenie wyników
if __name__ == "__main__":
    wyniki = uruchom_symulacje(CZAS_SYMULACJI)

    print("\n--- WYNIKI SYMULACJI (K_A={}, K_B={}, Czas: {} min) ---".format(
        LICZBA_MASZYN_A, LICZBA_MASZYN_B, CZAS_SYMULACJI))
    for klucz, wartosc in wyniki.items():
        if klucz == "Wykorzystanie Maszyn (Praca + Naprawa)":
            print(f"\n{klucz}:")
            for nazwa_zasobu, wykorzystanie_procent in wartosc.items():
                print(f"  {nazwa_zasobu}: {wykorzystanie_procent * 100:.2f}%")
        else:
            print(f"{klucz}: {wartosc:.4f}")
