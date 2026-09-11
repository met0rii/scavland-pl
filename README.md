# Scavland — Polish Translation / Spolszczenie PL

Nieoficjalne spolszczenie: interfejs, sterowanie, zadania, mapa, przedmioty, opisy, dialogi i radio. Opracowano **9980 wpisów w 44 tabelach**, w tym powtórzenia. Pełny zakres odnalezionych tabel, udostępniany do testów.

**Mod zastępuje angielski. W grze wybierz English. Nie dodaje osobnej pozycji Polski.**

## Pobieranie i instalacja

W **Releases** pobierz `Scavland-Polish-Translation-<wersja>.zip`.

1. Zamknij grę i rozpakuj ZIP.
2. Uruchom **Scavland-PL-Instalator.exe**.
3. Wybierz **1 — Zainstaluj / aktualizuj** i wskaż folder z `Scavland.exe`.
4. Po zakończeniu uruchom grę i wybierz **English**.

Instalator zawiera potrzebne biblioteki; nie trzeba instalować Pythona. [Pełna instrukcja](docs/INSTALL.txt).

**Paczka nie zawiera plików gry.** Polskie teksty i poprawka czcionki są nanoszone na pliki gracza. Nie dołączamy `data.unity3d`, paczek językowych, katalogu zasobów ani czcionek.

## Zgodność i przywracanie

- Windows / Steam, Build ID **25222006**. Pierwsza instalacja wymaga oryginalnych plików.
- Przed przejściem ze starszych paczek 1.0/1.1 przywróć oryginały przez sprawdzenie spójności w Steam. Instalator od 1.2 obsługuje aktualizacje własnych wydań.
- Opcja **2** sprawdza pliki, a **3** przywraca oryginały.
- Kopia zapasowa powstaje tylko lokalnie, w `Scavland_Data/ScavlandPL-backup`. Zachowaj ją do przywracania i aktualizacji.
- Przygotowanie plików wymaga około 1 GB wolnego miejsca. Inne mody zmieniające te same pliki mogą być niezgodne.

## Stan tłumaczenia

Bez dubbingu i zmiany napisów na grafikach. Nazwy własne i symbole mogą zachować oryginalny zapis. Tłumaczenie przygotowano z pomocą AI; pełna kontrola wizualna i kontekstowa podczas rozgrywki pozostaje do wykonania.

Błędy zgłaszaj w **Issues**, podając wersję gry i moda, miejsce wystąpienia i — jeśli to możliwe — zrzut ekranu.

## Praca nad tłumaczeniem

Edytuj pola `pl` w `translation/*.pl.json`. Zachowaj identyfikatory, klucze, źródłowe teksty, zmienne i znaczniki. `source/*.json` to tekstowy punkt odniesienia.

```sh
python tools/release.py validate
python -m unittest discover -s tests -v
```

Dawne pliki robocze, backupy, czcionki i wygenerowane paczki są wyłączone z Git.

## Automatyczne wydania

Każdy push na **master** uruchamia kontrole na Windows i Linux oraz buduje instalator Windows i publikuje ZIP w **Releases**. Numer wersji, np. `1.2.0-ci.12.1`, pochodzi z `VERSION`, numeru uruchomienia i próby CI. Pull requesty wykonują kontrole bez publikacji.

**CI nie potrzebuje gry, jej zasobów ani żadnego dodatkowego archiwum bazowego.** Buduje wyłącznie program instalatora, polskie teksty i drobne dane poprawki. Przy instalacji zasoby pochodzą z komputera gracza.

[Konfiguracja GitHub](docs/GITHUB-SETUP.md) · [Budowanie i działanie poprawki](docs/DEVELOPMENT.md) · [Opis na Nexus](docs/NEXUS.txt)
