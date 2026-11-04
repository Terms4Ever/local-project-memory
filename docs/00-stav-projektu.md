# Stav projektu

Aktualizováno 4. 11. 2026. Verze 1.5.2 doplňuje i výsledek nástroje zapsaný
v transcriptu před voláním, včetně dříve přeskočených případů. Zachovává oddělené
potvrzení zápisu a čerstvost předání i kontroly při práci na pozadí. Kontext upřednostňuje úplné aktuální
poznámky před starým syrovým výstupem a nezaměňuje staré vlastní předání
za poslední stav projektu. Celé záznamy a původní importované řádky
zůstávají uložené; schéma 3 se nemění. Distribuční vydání této verze:
[v1.5.2](https://github.com/Terms4Ever/local-project-memory/releases/tag/v1.5.2).
Číslo aplikace je konstanta VERSION v memory.py. Společný generátor zatím
Python verzi nečte, proto jeho blok obsahuje pouze údaje, které umí zjistit.

<!-- generovano nastroji, needitovat -->
```
hlavní větev:     main
```
<!-- konec generovaneho bloku -->

## Hotové

- Lokální SQLite paměť s FTS5, diskovou frontou a pěti nástroji MCP.
- Rozlišení Git projektů, registrovaných složek a samostatných sessions.
- Instalace pro Claude, Codex nebo oba hosty s návratem konfigurace.
- Přenos soukromého snapshotu na čistý počítač s výslovným mapováním cest.
- Import podporovaného schématu claude-mem bez změny zdrojové databáze.
- Veřejná distribuce obsahuje pouze program, návody a syntetická data testů.
- Sada nastroje: profil plny, pokyny agenta, šablona issue a sdílené kontroly.

## Ověřeno

Verze 1.2.0 prošla 51 testy z čistého ZIPu a na Windows v CI s Pythonem
3.11 i 3.13: [běh testů](https://github.com/Terms4Ever/local-project-memory/actions/runs/39789719618).
Hooky a MCP byly přímo ověřeny na Windows; běžná desktop session není totéž
co přímé vyvolání příkazu. Konkrétní verzi hosta je potřeba ověřit po instalaci.
Rozsah a příkazy kontrol nové dávky popisuje dokument 04; stav CI je vždy u
konkrétního commitu, ne odhad podle staršího výsledku.

## Další práce

- Sbírat důkazy z běžných desktop sessions pro podporované verze hostů.
- Vydávání verzí včetně tagu, ZIPu a kontroly stažené přílohy upravuje dokument 02;
  sjednocení distribuce se sleduje v [issue #3](https://github.com/Terms4Ever/local-project-memory/issues/3).
- Automatické aktualizace a synchronizace PC nejsou zadáním této verze.

## Na co si dát pozor

Instalátor je pro Windows a výchozí uživatelské profily. Ne-Git složka potřebuje
registraci, má-li sdílet paměť mezi chaty. Starý plugin claude-mem se automaticky
nevypíná. Filtr tajemství není úplný, databáze není šifrovaná programem a nepatří
do veřejného repozitáře. GitHub Release ani push neaktualizuje instalace na PC.
