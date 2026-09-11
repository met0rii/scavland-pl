# Budowanie i działanie poprawki

## Zawartość repozytorium

- `translation/*.pl.json`: tłumaczenia; edytuj pole `pl`.
- `source/*.json`: oryginalne teksty do sprawdzania identyfikatorów i formatowania.
- `config/game-build.json`: rozmiary i SHA256 oryginalnych plików oraz mała poprawka czcionki.
- `tools/patch_core.py`: nanoszenie tekstów i poprawki na lokalne pliki.
- `tools/installer.py`: sprawdzanie zgodności, instalacja, lokalna kopia, cofanie i przywracanie.
- `tools/build_distribution.py`: budowa samodzielnego programu Windows.
- `tools/release.py`: kontrola tłumaczeń, numerowanie i paczkowanie.
- `docs`: wspólne instrukcje; `{{VERSION}}` jest zastępowane podczas budowania.

Repozytorium i wydanie nie potrzebują żadnego oryginalnego ani gotowego, zmodyfikowanego archiwum gry. Do programu trafiają jedynie identyfikatory i polskie teksty, bez angielskich pól referencyjnych.

## Budowanie na Windows

Wymagany Python 3.12. Nie trzeba instalować Steam ani Scavland.

```sh
python -m pip install -r requirements-build.txt
python tools/release.py validate
python -m unittest discover -s tests -v
python tools/release.py build --out dist
```

Opcjonalnie: `--version 1.2.0`. Domyślna wersja pochodzi z `VERSION`. Kontrole i testy jednostkowe działają również na Linuxie; program Windows jest budowany na Windows przez PyInstaller.

ZIP zawiera dokładnie trzy pliki: `Scavland-PL-Instalator.exe`, instrukcję i `LICENCJE.txt`. Obok ZIP-a zapisują się suma SHA256, raport, opis wydania i opis na Nexus. Nie są dołączane pliki gry ani backupy.

## Dlaczego nie wysyłamy data.unity3d

To duże archiwum gry, w którym zmieniamy jeden obiekt: listę czcionek rezerwowych `NotoSansJP-VariableFont_wght SDF`. Poprawka odsyła do istniejącej w grze czcionki `LiberationSans SDF - Fallback`. Nie dostarcza żadnej nowej czcionki.

Dla Build ID 25222006 wystarcza wstawienie **12 bajtów** w surowym obiekcie o ID 11118, w `sharedassets0.assets`. Konfiguracja przechowuje pozycję i bajty oraz sumy kontrolne obiektu przed i po zmianie. Installer odczytuje lokalne archiwum, zmienia obiekt i zapisuje wynik.

SHA256 całego wyniku musi być identyczne z wcześniej zweryfikowaną poprawką. W poprzednim etapie porównano wszystkie 207580 obiektów i potwierdzono zmianę jednego obiektu czcionki. Nowy mechanizm odtwarza ten sam plik bez jego dystrybucji.

## Instalacja i zgodność

Na komputerze gracza powstają trzy zmienione pliki: angielska paczka tekstów, `catalog.bin` z jednym poprawionym rekordem CRC/rozmiaru i `data.unity3d` z poprawką czcionki. Oryginalna lista języków jest sprawdzana, lecz pozostaje bez zmian.

Przed zapisem są sprawdzane źródłowe SHA256, kompletność tabel, ponowny odczyt paczki tekstów i SHA256 poprawki czcionki. Kopie oryginałów powstają lokalnie. Podmiana zachowuje kopie stanu sprzed operacji i cofa zakończone podmiany, jeśli kolejna operacja zgłosi błąd. Przywracanie odmówi nadpisania nieznanych zmian innych modów.

Aktualizacje instalatora 1.2+ korzystają z jego lokalnej kopii. Po dawnych ręcznych paczkach 1.0/1.1 najpierw przywróć oryginały w Steam. Po aktualizacji gry trzeba zweryfikować nową wersję i opracować właściwe sumy/parametry; sam wzrost `VERSION` nie wystarczy.

Do lokalnej kontroli programu można używać:
```sh
Scavland-PL-Instalator.exe check --game "D:/Steam/steamapps/common/Scavland"
Scavland-PL-Instalator.exe install --game "D:/Steam/steamapps/common/Scavland"
Scavland-PL-Instalator.exe restore --game "D:/Steam/steamapps/common/Scavland"
```

Testy instalacji wykonuj na osobnej kopii własnych plików gry. CI sprawdza kod i gotowy program, ale nie ma zasobów gry do takiego testu.

[UnityPy](https://pypi.org/project/UnityPy/1.25.3/) · [PyInstaller — budowanie pojedynczego programu](https://www.pyinstaller.org/en/stable/usage.html)
