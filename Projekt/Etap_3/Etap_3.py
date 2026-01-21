import simpy
import random
import statistics
import csv
import matplotlib.pyplot as plt
from scipy import stats
from dataclasses import dataclass

# - 1. PARAMETRY BAZOWE SYSTEMU -
# zakresy czasów (min) - zgodne z etapami 1 i 2
ZAKRES_CZASU_A = (2, 15)      #min (rozkład jednostajny)
ZAKRES_CZASU_B = (10, 20)     # min (rozkład jednostajny)
ZAKRES_MTTR = (3, 10)         #czas naprawy (średnio)
BAZOWE_MTBF = (120, 180)      #standardowa awaryjność (czas między awariami)

# parametry symulacji
CZAS_SYMULACJI = 10000  #minuty
PLIK_WYNIKOW = 'wyniki_surowe_etap3.csv'

# - 2. STRUKTURY DANYCH -

@dataclass
class Zadanie:
    """Struktura przechowywująca dane o zadaniu wygenerowane PRZED symulacją (CRN)"""
    id: int
    czas_przyjscia: float
    czas_obslugi_a: float
    czas_obslugi_b: float

class MonitorDanych:
    """zbieranie surowych danych do analizy i pliku CSV"""

    def __init__(self):
        self.rekordy = []
        self.czasy_realizacji = []

    def dodaj_rekord(self, id_zad, scenariusz, czas_wej, czas_wyj, czas_oczek_a, czas_oczek_b):
        czas_realizacji = czas_wyj - czas_wej
        self.czasy_realizacji.append(czas_realizacji)
        self.rekordy.append({
            "Scenariusz": scenariusz,
            "ID_Zadania": id_zad,
            "Czas_Wejscia": round(czas_wej, 2),
            "Czas_Wyjscia": round(czas_wyj, 2),
            "Czas_Realizacji": round(czas_realizacji, 2),
            "Czas_Oczekiwania_A": round(czas_oczek_a, 2),
            "Czas_Oczekiwania_B": round(czas_oczek_b, 2)
        })

class ZasobProdukcyjny:
    def __init__(self, srodowisko, nazwa, param_mtbf, param_mttr):
        self.env = srodowisko
        self.nazwa = nazwa
        self.zasob = simpy.Resource(srodowisko, capacity=1)
        self.param_mtbf = param_mtbf
        self.param_mttr = param_mttr
        self.zepsuta = False
        #proces awarii działa w tle niezależnie od obsługi
        self.env.process(self._proces_awarii())

    def _proces_awarii(self):
        while True:
            try:
                #obsługa parametru MTBF
                #testowania "sztywnych" wartości
                if isinstance(self.param_mtbf, tuple):
                    mtbf = random.uniform(*self.param_mtbf)
                else:
                    mtbf = self.param_mtbf  #wartość "na sztywno"

                #czekanie na zepsucie się maszyny
                yield self.env.timeout(random.expovariate(1.0 / mtbf))

                self.zepsuta = True

                #czas naprawy
                if isinstance(self.param_mttr, tuple):
                    mttr = random.uniform(*self.param_mttr)
                else:
                    mttr = self.param_mttr

                yield self.env.timeout(random.expovariate(1.0 / mttr))
                self.zepsuta = False

            except simpy.Interrupt:
                break

    def get_obciazenie(self):
        """zwracanie długości kolejki + liczbę zajętych stanowisk"""
        return len(self.zasob.queue) + self.zasob.count

# - 3. LOGIKA PROCESU (Shortest Queue) -

def wybierz_maszyne(maszyny):
    """wybieranie maszyny z najmniejszym obciążeniem (Shortest Queue)"""
    return min(maszyny, key=lambda m: m.get_obciazenie())

def proces_obslugi(env, zadanie, maszyny_a, maszyny_b, monitor, nazwa_scenariusza):
    start_wejscia = env.now

    # - ETAP A -
    wybrana_a = wybierz_maszyne(maszyny_a)
    start_wait_a = env.now

    with wybrana_a.zasob.request() as req:
        yield req
        koniec_wait_a = env.now

        #symulacja pracy z uwzględnieniem awarii (Active Waiting)
        pozostalo = zadanie.czas_obslugi_a
        while pozostalo > 0:
            if wybrana_a.zepsuta:
                yield env.timeout(1)  #czekanie minutę na naprawę
            else:
                krok = min(pozostalo, 1)
                yield env.timeout(krok)
                pozostalo -= krok

    # - ETAP B -
    wybrana_b = wybierz_maszyne(maszyny_b)
    start_wait_b = env.now

    with wybrana_b.zasob.request() as req:
        yield req
        koniec_wait_b = env.now

        pozostalo = zadanie.czas_obslugi_b
        while pozostalo > 0:
            if wybrana_b.zepsuta:
                yield env.timeout(1)
            else:
                krok = min(pozostalo, 1)
                yield env.timeout(krok)
                pozostalo -= krok

    #zapis statystyk
    monitor.dodaj_rekord(
        id_zad=zadanie.id,
        scenariusz=nazwa_scenariusza,
        czas_wej=start_wejscia,
        czas_wyj=env.now,
        czas_oczek_a=koniec_wait_a - start_wait_a,
        czas_oczek_b=koniec_wait_b - start_wait_b
    )

def generator_zadan(env, lista_zadan, maszyny_a, maszyny_b, monitor, scenariusz):
    """wpuszczanie do systemu zadania poprzedniego (CRN)"""
    for zadanie in lista_zadan:
        if zadanie.czas_przyjscia > env.now:
            yield env.timeout(zadanie.czas_przyjscia - env.now)
        env.process(proces_obslugi(env, zadanie, maszyny_a, maszyny_b, monitor, scenariusz))

# - 4. PRE-GENEROWANIE (CRN) -

def przygotuj_wspolne_zadania(seed, lambda_range, czas_max):
    """generowanie identycznego zestawu zadań dla porównywanych scenariuszy"""
    random.seed(seed)
    zadania = []
    czas = 0
    i = 0
    while czas < czas_max:
        interwal = random.expovariate(1.0 / random.uniform(*lambda_range))
        czas += interwal
        if czas > czas_max: break

        #losowanie czasu obsługi raz, przypisujemy je do zadania
        t_a = random.uniform(*ZAKRES_CZASU_A)
        t_b = random.uniform(*ZAKRES_CZASU_B)
        zadania.append(Zadanie(i, czas, t_a, t_b))
        i += 1
    return zadania

# - 5. RUNNER -

def uruchom_pojedynczy_przebieg(zadania, n_a, n_b, mtbf_val, nazwa_scenariusza):
    env = simpy.Environment()
    monitor = MonitorDanych()

    #maszyny z zadanym parametrem MTBF
    maszyny_a = [ZasobProdukcyjny(env, f'A{i}', mtbf_val, ZAKRES_MTTR) for i in range(n_a)]
    maszyny_b = [ZasobProdukcyjny(env, f'B{i}', mtbf_val, ZAKRES_MTTR) for i in range(n_b)]

    env.process(generator_zadan(env, zadania, maszyny_a, maszyny_b, monitor, nazwa_scenariusza))
    env.run(until=CZAS_SYMULACJI + 2000)  #bufor na opróżnienie systemu

    return monitor

# - 6. GŁÓWNA ANALIZA -

def analizuj_i_rysuj(tytul, dane1, dane2, etykieta1, etykieta2, plik_wykresu):
    """słownik ze statystykami."""
    sr1 = statistics.mean(dane1)
    sr2 = statistics.mean(dane2)
    std1 = statistics.stdev(dane1)
    std2 = statistics.stdev(dane2)

    #test t-Studenta dla par zależnych
    t_stat, p_val = stats.ttest_rel(dane1, dane2)

    print(f"\n--- WYNIKI: {tytul} ---")
    print(f"{etykieta1}: średni czas = {sr1:.2f} min (std = {std1:.2f})")
    print(f"{etykieta2}: średni czas = {sr2:.2f} min (std = {std2:.2f})")
    print(f"Różnica średnich: {sr1 - sr2:.2f} min")
    print(f"Test t-Studenta (pary zależne): t = {t_stat:.4f}, p-value: {p_val:.5e}")
    if p_val < 0.05:
        print("-> Różnica JEST istotna statystycznie.")
    else:
        print("-> Różnica NIE JEST istotna statystycznie.")

    #wykres (boxplot)
    plt.figure(figsize=(8, 6))
    bp = plt.boxplot([dane1, dane2], tick_labels=[etykieta1, etykieta2], patch_artist=True)
    bp['boxes'][0].set_facecolor('lightcoral')
    bp['boxes'][1].set_facecolor('lightgreen')
    plt.title(f"{tytul}\nRozkład czasów realizacji")
    plt.ylabel("Średni czas realizacji [min]")
    plt.grid(axis='y', alpha=0.3)
    plik_boxplot = plik_wykresu.replace('.png', '_boxplot.png')
    plt.savefig(plik_boxplot)
    print(f"Wykres pudełkowy zapisano jako {plik_boxplot}")

    #wykres różnic (słupkowy)
    delta = [v1 - v2 for v1, v2 in zip(dane1, dane2)]
    kolory = ['green' if d > 0 else 'red' for d in delta]

    plt.figure(figsize=(10, 5))
    plt.bar(range(len(delta)), delta, color=kolory)
    plt.title(f"{tytul}\nZysk czasowy (pozytywny słupek = {etykieta2} lepsze)")
    plt.xlabel("Numer symulacji (Seed)")
    plt.ylabel("Skrócenie czasu [min]")
    plt.axhline(0, color='black')
    plt.savefig(plik_wykresu)
    print(f"Wykres różnic zapisano jako {plik_wykresu}")

    #statystyki do zapisu
    return {
        'tytul': tytul,
        'etykieta1': etykieta1,
        'etykieta2': etykieta2,
        'srednia1': sr1,
        'srednia2': sr2,
        'std1': std1,
        'std2': std2,
        't_stat': t_stat,
        'p_value': p_val,
        'roznica': sr1 - sr2,
        'istotna': p_val < 0.05
    }

def main():
    N_REPLIKACJI = 30
    MASTER_SEED = 999
    random.seed(MASTER_SEED)
    seedy = [random.randint(1, 1000000) for _ in range(N_REPLIKACJI)]
    LAMBDA = (8, 12)

    wszystkie_dane = []

    #zbiory średnich do testów
    wyniki_scen_1a = []  # 2A+3B
    wyniki_scen_1b = []  # 3A+2B

    wyniki_scen_2_base = []  #baza (3 maszyny, MTBF 150)
    wyniki_scen_2_maszyny = []  #inwestycja w maszyny (4 maszyny, MTBF 150)
    wyniki_scen_2_jakosc = []  #inwestycja w jakość (3 maszyny, MTBF 300)


    for i, seed in enumerate(seedy):
        #generowanie WSPÓLNY wsad zadań (CRN)
        zadania = przygotuj_wspolne_zadania(seed, LAMBDA, CZAS_SYMULACJI)

        # - BADANIE 1: Konfiguracja (Bottleneck) -
        # 2A+3B (optymalna) vs 3A+2B (bazowa)
        mon1 = uruchom_pojedynczy_przebieg(zadania, 2, 3, BAZOWE_MTBF, "S1_2A_3B")
        mon2 = uruchom_pojedynczy_przebieg(zadania, 3, 2, BAZOWE_MTBF, "S1_3A_2B")

        wyniki_scen_1a.append(statistics.mean(mon1.czasy_realizacji))
        wyniki_scen_1b.append(statistics.mean(mon2.czasy_realizacji))
        wszystkie_dane.extend(mon1.rekordy)
        wszystkie_dane.extend(mon2.rekordy)

        # -BADANIE 2: Inwestycja -

        #Baza 3A, 2B
        wyniki_scen_2_base.append(statistics.mean(mon2.czasy_realizacji))

        #OPCJA: więcej maszyn (3A, 3B, MTBF standard)
        mon_maszyny = uruchom_pojedynczy_przebieg(zadania, 3, 3, BAZOWE_MTBF, "S2_WiecejMaszyn")
        wyniki_scen_2_maszyny.append(statistics.mean(mon_maszyny.czasy_realizacji))
        wszystkie_dane.extend(mon_maszyny.rekordy)

        #OPCJA: lepsza niezawodność (3A, 2B, MTBF = 300 na sztywno)
        mon_jakosc = uruchom_pojedynczy_przebieg(zadania, 3, 2, 300, "S2_LepszeMTBF")
        wyniki_scen_2_jakosc.append(statistics.mean(mon_jakosc.czasy_realizacji))
        wszystkie_dane.extend(mon_jakosc.rekordy)

    # - ZAPIS CSV -
    pola = ["Scenariusz", "ID_Zadania", "Czas_Wejscia", "Czas_Wyjscia",
            "Czas_Realizacji", "Czas_Oczekiwania_A", "Czas_Oczekiwania_B"]
    with open(PLIK_WYNIKOW, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=pola)
        writer.writeheader()
        writer.writerows(wszystkie_dane)
    print(f"\nZapisano surowe dane do {PLIK_WYNIKOW}")

    # - ANALIZA I WYKRESY -

    # 1. porównanie konfiguracji
    stat1 = analizuj_i_rysuj(
        "Badanie 1: Konfiguracja 2A+3B vs 3A+2B",wyniki_scen_1a, wyniki_scen_1b,
        "2A+3B", "3A+2B","wykres_konfiguracja.png"
    )

    # 2. porównanie inwestycji (co daje lepszy efekt?)
    stat2 = analizuj_i_rysuj(
        "Badanie 2: Inwestycja w ilość (3A+3B) vs jakość (rzadsze awarie)",wyniki_scen_2_maszyny, wyniki_scen_2_jakosc,
        "Więcej Maszyn (3A+3B)", "Rzadsze Awarie (3A+2B)","wykres_inwestycja.png"
    )

    # - ZAPIS STATYSTYK DO PLIKU -
    with open('statystyki_etap3.txt', 'w', encoding='utf-8') as f:
        f.write("STATYSTYKI BADAŃ SYMULACYJNYCH - ETAP 3\n")
        f.write("=" * 60 + "\n\n")
        
        for stat in [stat1, stat2]:
            f.write(f"--- {stat['tytul']} ---\n")
            f.write(f"{stat['etykieta1']}: średnia = {stat['srednia1']:.2f} min, std = {stat['std1']:.2f} min\n")
            f.write(f"{stat['etykieta2']}: średnia = {stat['srednia2']:.2f} min, std = {stat['std2']:.2f} min\n")
            f.write(f"Różnica średnich: {stat['roznica']:.2f} min\n")
            f.write(f"Test t-Studenta: t = {stat['t_stat']:.4f}, p = {stat['p_value']:.5e}\n")
            f.write(f"Istotność statystyczna (α=0.05): {'TAK' if stat['istotna'] else 'NIE'}\n\n")
        
    print("\nStatystyki zapisano do pliku: statystyki_etap3.txt")

    plt.show()

if __name__ == "__main__":
    main()