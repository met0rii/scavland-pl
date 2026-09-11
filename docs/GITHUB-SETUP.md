# Pierwsza publikacja na GitHubie

1. Utwórz puste repozytorium i podłącz lokalny projekt.
2. Zatwierdź przygotowane pliki i wyślij gałąź **master**.
3. W zakładce **Actions** sprawdź przebieg „Validate and release Polish translation”.
4. Po przejściu kontroli ZIP pojawi się w **Releases**.

Nie wgrywaj dawnych paczek 1.0/1.1 ani pliku `scavland-build-inputs-25222006.zip`. Zawierały całe archiwa gry. **Nowe CI ich nie używa i nie wymaga żadnego załącznika bazowego.**

Nie dodawaj zignorowanych katalogów `backup`, `build`, `publish`, `dist`, `reports`, `local_tools`, bibliotek ani wyodrębnionych czcionek.

## Co robi CI

- Sprawdza 44 tabele i testy narzędzi na Windows oraz Linux.
- Na Windows tworzy samodzielny instalator zawierający kod, biblioteki, polskie teksty i metadane poprawki.
- Sprawdza uruchamianie instalatora i brak archiwów gry w jego zawartości.
- Pakuje instalator, instrukcję oraz licencje. Publikuje ZIP i jego sumę SHA256.

CI nie uruchamia gry i nie testuje instalacji na jej rzeczywistych zasobach. Taki test wykonuje się lokalnie na osobnej, posiadanej kopii gry.

## Numery i uprawnienia

Każdy push lub merge na `master` tworzy wydanie testowe, np. `v1.2.0-ci.12.1`. Baza to `VERSION`, następne liczby oznaczają uruchomienie CI i próbę. Ponowienie nie nadpisuje wcześniejszego wydania.

Zwykłe pull requesty niczego nie publikują. Zadanie publikujące używa standardowego `GITHUB_TOKEN` z prawem zapisu wydań. Własny token w Secrets nie jest potrzebny. Jeżeli organizacja wyłączyła Actions lub ograniczyła uprawnienia, musi je dopuścić dla tego repozytorium.

Źródła mechanizmu: [GitHub Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax), [GitHub CLI Releases](https://cli.github.com/manual/gh_release_create).
