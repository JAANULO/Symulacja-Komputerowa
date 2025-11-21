import simpy
import random
import statistics
import matplotlib.pyplot as plt
from scipy import stats
from typing import Dict, List, Tuple

# --- 1. PARAMETRY SYSTEMU (Z Etapu I) ---

ZAKRES_CZASU_A = (2, 15)  # min - rozkład jednostajny
ZAKRES_CZASU_B = (10, 20)  # min - rozkład jednostajny
ZAKRES_MTBF = (120, 180)  # min - średni czas między awariami
ZAKRES_MTTR = (3, 10)  # min - średni czas naprawy
CZAS_SYMULACJI = 10000  # min (krótszy czas dla pojedynczej replikacji w pętli)


# --- 2. KLASY I LOGIKA SYMULACJI (Z Etapu II) ---

class StatystykiSymulacji:
    def __init__(self):
        self.czasy_realizacji = []
        self.czasy_oczekiwania_a_b = []
        self.elementy_ukonczone = 0


class ZasobProdukcyjny:
    def __init__(self, srodowisko, nazwa, zakres_czasu, zakres_naprawy, zakres_mtbf):
        self.srodowisko = srodowisko
        self.nazwa = nazwa
        self.zasob = simpy.Resource(srodowisko, capacity=1)
        self.zakres_czasu = zakres_czasu
        self.zakres_naprawy = zakres_naprawy
        self.zakres_mtbf = zakres_mtbf
        self.zepsuta = False
        # Uruchomienie procesu awarii
        self.srodowisko.process(self._proces_awarii())

    def _proces_awarii(self):
        while True:
            try:
                # Czas do awarii
                mtbf = random.uniform(*self.zakres_mtbf)
                yield self.srodowisko.timeout(random.expovariate(1.0 / mtbf))

                # Awaria
                self.zepsuta = True

                # Czas naprawy
                mttr = random.uniform(*self.zakres_naprawy)
                yield self.srodowisko.timeout(random.expovariate(1.0 / mttr))

                # Koniec awarii
                self.zepsuta = False
            except simpy.Interrupt:
                break

    def uzyj_zasobu(self, id_elem, czas_przetwarzania):
        with self.zasob.request() as req:
            yield req
            # Jeśli maszyna zepsuta, czekaj na naprawę
            while self.zepsuta:
                yield self.srodowisko.timeout(1)

            # Przetwarzanie
            yield self.srodowisko.timeout(czas_przetwarzania)


def proces_elementu(env, id_el, res_a, res_b, czas_start, stats):
    # --- ETAP A ---
    czas_a = random.uniform(*ZAKRES_CZASU_A)
    # Wybór zasobu Round-Robin
    zasob_a = res_a[id_el % len(res_a)]
    yield env.process(zasob_a.uzyj_zasobu(id_el, czas_a))

    # --- ETAP B ---
    czas_b = random.uniform(*ZAKRES_CZASU_B)
    zasob_b = res_b[id_el % len(res_b)]

    start_oczekiwania = env.now
    yield env.process(zasob_b.uzyj_zasobu(id_el, czas_b))

    # Logowanie czasu kolejki przed B
    czas_w_kolejce = env.now - start_oczekiwania - czas_b
    if czas_w_kolejce > 0:
        stats.czasy_oczekiwania_a_b.append(czas_w_kolejce)

    # Statystyki końcowe
    stats.czasy_realizacji.append(env.now - czas_start)
    stats.elementy_ukonczone += 1


def zrodlo_elementow(env, res_a, res_b, lam_range, stats):
    i = 0
    while True:
        # Generowanie przybycia
        lam = random.uniform(*lam_range)
        yield env.timeout(random.expovariate(1.0 / lam))
        i += 1
        env.process(proces_elementu(env, i, res_a, res_b, env.now, stats))


# --- 3. FUNKCJE POMOCNICZE DO EKSPERYMENTÓW ---

def uruchom_pojedyncza_symulacje(liczba_a, liczba_b, lambda_range, seed=None):
    """
    Uruchamia jedną symulację z zadanym seedem.
    Kluczowe dla metody Common Random Numbers.
    """
    # Ustawienie ziarna losowości dla tej konkretnej symulacji
    if seed is not None:
        random.seed(seed)

    env = simpy.Environment()
    stats = StatystykiSymulacji()

    # Inicjalizacja zasobów
    res_a = [ZasobProdukcyjny(env, f'A{i}', ZAKRES_CZASU_A, ZAKRES_MTTR, ZAKRES_MTBF)
             for i in range(liczba_a)]
    res_b = [ZasobProdukcyjny(env, f'B{i}', ZAKRES_CZASU_B, ZAKRES_MTTR, ZAKRES_MTBF)
             for i in range(liczba_b)]

    # Start źródła
    env.process(zrodlo_elementow(env, res_a, res_b, lambda_range, stats))

    # Start symulacji
    env.run(until=CZAS_SYMULACJI)

    # Zbieranie wyników
    sredni_czas = statistics.mean(stats.czasy_realizacji) if stats.czasy_realizacji else 0
    return sredni_czas


# --- 4. ETAP III: BADANIA I ANALIZA WYNIKÓW ---

def przeprowadz_badania_statystyczne():
    print("=" * 60)
    print("ETAP III: Badania symulacyjne z wykorzystaniem Common Random Numbers")
    print("=" * 60)

    # Ustalenie warunków eksperymentu
    N = 30  # Liczba replikacji (zgodnie z teorią małych prób n>30 jest zalecane)
    MASTER_SEED = 424242  # Główne ziarno dla powtarzalności całego badania
    random.seed(MASTER_SEED)

    # Generowanie listy seedów dla poszczególnych replikacji
    # Każda para symulacji (Scenariusz 1 i 2) dostanie ten sam seed z tej listy
    lista_seedow = [random.randint(1, 1000000) for _ in range(N)]

    # Parametry badane
    # Zwiększamy obciążenie (lambda 8-12), aby uwypuklić różnice w wydajności
    TEST_LAMBDA = (8, 12)

    wyniki_s1 = []  # Scenariusz 1: 3 Maszyny A, 2 Maszyny B (Wąskie gardło)
    wyniki_s2 = []  # Scenariusz 2: 3 Maszyny A, 3 Maszyny B (Rozbudowa)

    print(f"Rozpoczynam symulację {N} par scenariuszy...")

    for i, seed_iteracji in enumerate(lista_seedow):
        # Scenariusz 1 (Obecny)
        t1 = uruchom_pojedyncza_symulacje(3, 2, TEST_LAMBDA, seed=seed_iteracji)
        wyniki_s1.append(t1)

        # Scenariusz 2 (Zoptymalizowany) - Ten sam seed!
        t2 = uruchom_pojedyncza_symulacje(3, 3, TEST_LAMBDA, seed=seed_iteracji)
        wyniki_s2.append(t2)

        if (i + 1) % 5 == 0:
            print(f"  -> Ukończono replikację {i + 1}/{N}")

    # --- ANALIZA WYNIKÓW ---

    avg1 = statistics.mean(wyniki_s1)
    avg2 = statistics.mean(wyniki_s2)
    diff = avg1 - avg2  # O ile skrócił się czas

    print("\n--- WYNIKI ZBIORCZE ---")
    print(f"Średni czas realizacji (3A+2B): {avg1:.2f} min")
    print(f"Średni czas realizacji (3A+3B): {avg2:.2f} min")
    print(f"Średnia redukcja czasu: {diff:.2f} min")

    # --- WERYFIKACJA HIPOTEZ (TEST T-STUDENTA DLA PAR ZALEŻNYCH) ---
    # Używamy ttest_rel, ponieważ próbki są zależne przez wspólny seed (CRN)
    t_stat, p_val = stats.ttest_rel(wyniki_s1, wyniki_s2)

    print("\n--- WERYFIKACJA STATYSTYCZNA ---")
    print("Hipoteza H0: Średnie czasy realizacji w obu konfiguracjach są równe.")
    print("Hipoteza H1: Dodanie maszyny skraca czas realizacji (średnie są różne).")
    print(f"Test: t-Studenta dla par zależnych (Paired T-Test)")
    print(f"Wartość p (p-value): {p_val:.10f}")

    alpha = 0.05
    if p_val < alpha:
        print("WNIOSEK: Odrzucamy H0. Różnica jest ISTOTNA STATYSTYCZNIE.")
    else:
        print("WNIOSEK: Brak podstaw do odrzucenia H0.")

    # --- WYKRESY ---
    try:
        # Wykres pudełkowy
        plt.figure(figsize=(10, 6))
        plt.boxplot([wyniki_s1, wyniki_s2], labels=['3A + 2B', '3A + 3B'])
        plt.title(f'Porównanie czasu realizacji (Metoda CRN, N={N})')
        plt.ylabel('Średni czas realizacji zlecenia [min]')
        plt.grid(True, alpha=0.3)
        plt.savefig('wykres_pudelkowy.png')
        print("\nWykres zapisano jako 'wykres_pudelkowy.png'")

        # Wykres różnic (pokazuje zysk dla każdego seeda)
        roznice = [s1 - s2 for s1, s2 in zip(wyniki_s1, wyniki_s2)]
        plt.figure(figsize=(10, 6))
        plt.bar(range(N), roznice, color='green', alpha=0.7)
        plt.title('Zysk czasowy w każdej replikacji (S1 - S2)')
        plt.xlabel('Numer replikacji (Seed)')
        plt.ylabel('Skrócenie czasu realizacji [min]')
        plt.axhline(y=statistics.mean(roznice), color='r', linestyle='--', label='Średnia redukcja')
        plt.legend()
        plt.savefig('wykres_roznic.png')
        print("Wykres różnic zapisano jako 'wykres_roznic.png'")

        plt.show()
    except Exception as e:
        print(f"Błąd generowania wykresu: {e}")


if __name__ == "__main__":
    przeprowadz_badania_statystyczne()