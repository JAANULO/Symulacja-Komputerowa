# WERYFIKACJA MODELU SYMULACJI
## Dwuetapowa linia produkcyjna z awariami maszyn

**Autorzy:** Janusz Andrzejewski, Igor Lis  
**Przedmiot:** Symulacja komputerowa - Projekt  
**Semestr:** Zimowy 2025/26  
**Data:** 15 listopada 2025

---

## 1. DOKUMENTACJA KODU

### 1.1. Struktura modelu

Model symulacyjny został zaimplementowany w języku Python z wykorzystaniem biblioteki SimPy. Składa się z następujących komponentów:

**Klasy:**
- `StatystykiSymulacji` - zbiera dane z przebiegu symulacji
- `ZasobProdukcyjny` - reprezentuje maszynę z losową awaryjnością

**Funkcje:**
- `proces_elementu()` - opisuje przepływ elementu przez system
- `zrodlo_elementow()` - generator nowych elementów do systemu
- `uruchom_symulacje()` - inicjalizuje i uruchamia symulację

### 1.2. Parametry systemu

| Parametr | Typ | Zakres | Rozkład | Opis |
|----------|-----|--------|---------|------|
| T_A | Losowy | (2-15) min | Jednostajny | Czas przetwarzania w etapie A |
| T_B | Losowy | (10-20) min | Jednostajny | Czas przetwarzania w etapie B |
| T_awaria | Losowy | (120-180) min | Wykładniczy | Średni czas między awariami (MTBF) |
| T_naprawa | Losowy | (3-10) min | Wykładniczy | Średni czas naprawy (MTTR) |
| λ | Losowy | (10-20) min | Wykładniczy | Średni czas między przybyciami |
| K_A | Deterministyczny | 3 | - | Liczba maszyn w etapie A |
| K_B | Deterministyczny | 2 | - | Liczba maszyn w etapie B |

### 1.3. Kluczowe mechanizmy

**Proces awarii maszyny:**
- Każda maszyna ma proces działający w tle (`_proces_awarii()`)
- Losuje czas do awarii z rozkładu wykładniczego (MTBF)
- Po awarii losuje czas naprawy z rozkładu wykładniczego (MTTR) !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
- Zbiera statystyki czasu pracy i naprawy

**Alokacja maszyn:**
- Strategia round-robin: element i-ty trafia do maszyny (i mod K)
- Zapewnia równomierne rozłożenie obciążenia

**Zbieranie statystyk:**
- Czasy realizacji (czas w systemie)
- Czasy oczekiwania między etapami
- Wykorzystanie maszyn (czas pracy, naprawy, liczba awarii)

Pełna dokumentacja kodu znajduje się w załączonym pliku: **Projekt-dokumentacja.py**

---

## 2. SPRAWDZENIE PROSTEGO PRZYKŁADU

### 2.1. Konfiguracja testu deterministycznego

Aby zweryfikować poprawność implementacji, przeprowadzono symulację **bez awarii maszyn**:
- MTBF = 1 000 000 min (praktycznie brak awarii)
- MTTR = 0 min (natychmiastowa naprawa)
- Czas symulacji = 10 000 min
- Pozostałe parametry bez zmian

### 2.2. Obliczenia teoretyczne

**Średnie czasy przetwarzania:**
- Średni czas w etapie A: E[T_A] = (2 + 15) / 2 = **8.5 min**
- Średni czas w etapie B: E[T_B] = (10 + 20) / 2 = **15.0 min**

**Teoretyczny minimalny czas realizacji:**
- T_min = E[T_A] + E[T_B] = 8.5 + 15.0 = **23.5 min**

**Teoretyczna maksymalna przepustowość:**
- Etap A (3 maszyny): μ_A = 3 / 8.5 = **0.3529 elem/min**
- Etap B (2 maszyny): μ_B = 2 / 15.0 = **0.1333 elem/min**
- **Wąskie gardło:** Etap B z przepustowością **0.1333 elem/min**

**Intensywność przybyć:**
- Średni czas między przybyciami: E[λ] = (10 + 20) / 2 = 15.0 min
- Intensywność: λ = 1 / 15.0 = **0.0667 elem/min**

### 2.3. Wyniki symulacji

**TEST 1: Symulacja bez awarii maszyn**

| Wskaźnik | Wartość |
|----------|---------|
| Przepustowość | 0.0666 elem/min |
| Średni czas realizacji | 26.25 min |
| Liczba ukończonych elementów | 666 |

### 2.4. Porównanie z teorią

| Wskaźnik | Symulacja | Teoria | Różnica | Stosunek |
|----------|-----------|--------|---------|----------|
| Przepustowość | 0.0666 | 0.1333 (max) | 0.0667 | 49.95% |
| | | 0.0667 (λ) | 0.0001 | 99.85% |
| Czas realizacji | 26.25 min | 23.5 min (min) | 2.75 min | 111.7% |

### 2.5. Wytłumaczenie różnic

**1. Przepustowość systemu**

Przepustowość symulacji (0.0666 elem/min) jest **praktycznie identyczna** z teoretyczną intensywnością przybyć (0.0667 elem/min). Różnica wynosi zaledwie 0.15%, co mieści się w granicach błędu statystycznego.

System nie osiąga maksymalnej teoretycznej przepustowości (0.1333 elem/min), ponieważ:
- Intensywność przybyć (λ = 0.0667) jest **niższa** niż maksymalna przepustowość wąskiego gardła
- System jest **niedociążony** - maszyny w etapie B pracują tylko w ~50% czasu
- To poprawne zachowanie: przepustowość jest ograniczona przez mniejszą z wartości: λ i μ_B

**2. Średni czas realizacji**

Czas realizacji z symulacji (26.25 min) jest o 2.75 min **dłuższy** niż teoretyczny minimalny (23.5 min).

Przyczyny różnicy:
- **Kolejkowanie**: elementy muszą czekać na dostępność maszyn
- **Losowość**: zmienność czasów przetwarzania powoduje nierównomierne obciążenie
- **Strategia round-robin**: nie zawsze optymalna alokacja przy różnych czasach
- Różnica 2.75 min stanowi ~12% i jest **akceptowalna** dla systemu kolejkowego

**Wniosek:** Model działa **poprawnie**. Wyniki są zgodne z oczekiwaniami teoretycznymi dla systemu kolejkowego z losowymi przybyciami i czasami obsługi.

---

## 3. ANALIZA STATYSTYCZNA - WIELOKROTNE URUCHOMIENIA

### 3.1. Metodologia

Przeprowadzono **5 niezależnych uruchomień** symulacji bez awarii z następującymi parametrami:
- MTBF = 1 000 000 min (praktycznie brak awarii)
- MTTR = 0 min
- Czas symulacji = 10 000 min
- Każde uruchomienie z innym ziarnem generatora losowego

### 3.2. Wyniki pięciu uruchomień

**TEST 2: Analiza stabilności wyników**

| Uruchomienie | Przepustowość [elem/min] |
|--------------|--------------------------|
| 1 | 0.0673 |
| 2 | 0.0656 |
| 3 | 0.0654 |
| 4 | 0.0690 |
| 5 | 0.0699 |

### 3.3. Statystyki opisowe

| Miara | Wartość |
|-------|---------|
| **Średnia** | **0.0674 elem/min** |
| **Odchylenie standardowe** | 0.0020 |
| **Współczynnik zmienności** | **2.97%** |
| **Minimum** | 0.0654 elem/min |
| **Maksimum** | 0.0699 elem/min |
| **Rozstęp** | 0.0045 elem/min |
| **95% przedział ufności** | [0.0650, 0.0699] |

### 3.4. Interpretacja wyników

**Stabilność modelu:**
- Współczynnik zmienności **2.97% < 10%** → wyniki są **bardzo stabilne**
- Odchylenie standardowe jest małe (0.0020) w stosunku do średniej (0.0674)
- Wszystkie wartości mieszczą się w wąskim przedziale ±3.3% od średniej

**Zgodność z teorią:**
- Średnia przepustowość (0.0674) jest bardzo bliska teoretycznej (0.0667)
- Różnica wynosi 1.05%, co jest **doskonałym wynikiem**
- Teoretyczna wartość mieści się w 95% przedziale ufności

**Wnioski:**
1. ✓ Model wykazuje **wysoką powtarzalność** wyników
2. ✓ Losowość jest **prawidłowo zaimplementowana** (różne wyniki przy różnych ziarnach)
3. ✓ Zbieżność do wartości teoretycznych potwierdza **poprawność implementacji**
4. ✓ Przy dłuższych symulacjach spodziewamy się jeszcze lepszej zgodności

---

## 4. DODATKOWA WERYFIKACJA - PORÓWNANIE KONFIGURACJI

### 4.1. Cel testu

Sprawdzenie czy model **logicznie reaguje** na zmianę liczby maszyn w poszczególnych etapach.

### 4.2. Testowane konfiguracje

**TEST 3: Porównanie konfiguracji maszyn** (czas symulacji: 5000 min, bez awarii)

| Konfiguracja | K_A | K_B | Przepustowość [elem/min] | Czas realizacji [min] |
|--------------|-----|-----|--------------------------|----------------------|
| Minimalna | 2 | 2 | 0.0644 | 28.09 |
| Zwiększony etap A | 3 | 2 | 0.0660 | 27.79 |
| Zwiększony etap B | 2 | 3 | 0.0672 | 26.01 |
| Zrównoważona | 3 | 3 | 0.0712 | 24.98 |

### 4.3. Obserwacje i wnioski

**1. Wpływ dodatkowej maszyny w etapie A (2→3):**
- Przepustowość: +2.5% (0.0644 → 0.0660)
- Czas realizacji: -1.1% (28.09 → 27.79)
- **Mały wpływ**, ponieważ etap A nie jest wąskim gardłem

**2. Wpływ dodatkowej maszyny w etapie B (2→3):**
- Przepustowość: +4.3% (0.0644 → 0.0672)
- Czas realizacji: -7.4% (28.09 → 26.01)
- **Większy wpływ**, ponieważ etap B jest wąskim gardłem

**3. Konfiguracja zrównoważona (3+3):**
- Najwyższa przepustowość: 0.0712 elem/min
- Najniższy czas realizacji: 24.98 min
- **Potwierdzenie**: więcej maszyn = lepsza wydajność

**Wniosek weryfikacyjny:**
Model **poprawnie** identyfikuje wąskie gardło systemu (etap B) i **adekwatnie** reaguje na zmiany konfiguracji. Zwiększenie liczby maszyn w wąskim gardle ma większy wpływ niż w etapie nadmiarowym.

---

## 5. WALIDACJA (OPCJONALNA)

### 5.1. Status walidacji

Walidacja modelu z danymi rzeczywistymi **nie została przeprowadzona** z następujących przyczyn:

1. **Brak danych rzeczywistych** - symulacja modeluje hipotetyczną linię produkcyjną
2. **Charakter projektu** - model stworzony w celach edukacyjnych
3. **Niemożliwość porównania** - brak dostępu do rzeczywistej linii produkcyjnej o analogicznych parametrach

### 5.2. Możliwości walidacji w przyszłości

Gdyby dostępne były dane rzeczywiste, można by przeprowadzić:
- **Walidację historyczną** - porównanie z danymi z przeszłości
- **Walidację bieżącą** - równoległe uruchomienie modelu i systemu rzeczywistego
- **Walidację ekspercką** - ocena przez specjalistów z przemysłu

---

## 6. PODSUMOWANIE WERYFIKACJI

### 6.1. Kryteria weryfikacji - status

| Kryterium | Status | Opis |
|-----------|--------|------|
| Dokumentacja kodu | ✓ Spełnione | Kod z komentarzami w pliku Projekt-dokumentacja.py |
| Przykład deterministyczny | ✓ Spełnione | Symulacja bez awarii, porównanie z teorią |
| Wytłumaczenie różnic | ✓ Spełnione | Różnice wyjaśnione i uzasadnione |
| Analiza statystyczna | ✓ Spełnione | 5 uruchomień, statystyki opisowe |
| Walidacja | - Opcjonalna | Nie przeprowadzona (brak danych rzeczywistych) |

### 6.2. Główne wnioski

1. **Poprawność implementacji**
   - Wyniki symulacji są zgodne z obliczeniami teoretycznymi
   - Różnice mieszczą się w granicach oczekiwanych dla systemów stochastycznych

2. **Stabilność modelu**
   - Współczynnik zmienności 2.97% potwierdza wysoką powtarzalność
   - Model daje spójne wyniki przy różnych ziarnach generatora losowego

3. **Logika systemu**
   - Model poprawnie identyfikuje wąskie gardło (etap B)
   - Reaguje adekwatnie na zmiany konfiguracji maszyn

