# Rozhodovací deník

Nové rozhodnutí je nový záznam. Starší důvod se nepřepisuje; změna se odkáže
na předchozí záznam. Tento deník obsahuje rozhodnutí o programu, ne paměť uživatelů.

## R001 - 22. 10. 2026 - Ukládání bez vzdáleného modelu

Paměť používá standardní knihovnu Pythonu, SQLite FTS5 a diskovou frontu.
Ukládání a hledání nemají záviset na obnově OAuth, modelových kvótách ani Chroma.
Cena je lexikální hledání a absence automatických AI souhrnů. Strukturované
poznámky ukládá pracující agent přes MCP; není slib úplného zapamatování.

## R002 - 22. 10. 2026 - Identita projektu a session

Git projekty se rozlišují podle skutečné společné Git databáze, ne názvu nebo
remote URL. Ostatní společné kořeny se registrují výslovně. Bez rozpoznaného
projektu je paměť podle hosta a session/thread ID. Nová session nesmí převzít
cizí historii jen proto, že host používá stejnou výchozí cwd. Připojení projektu
není souhlas ke sloučení dosavadní session historie.

## R003 - 22. 10. 2026 - Veřejný program, soukromá data

Vlastník zvolil veřejný repozitář. Publikuje se jen kód, návody a syntetické
testy. Přenos skutečných záznamů probíhá soukromým snapshotem mimo GitHub.
Obnova na novém PC vyžaduje čerstvou databázi a explicitní mapování cest;
nenamapované projekty zůstávají archivy. Automatické slučování dvou aktivních
databází ani synchronizace mezi PC nejsou součástí první verze.

## R004 - 22. 10. 2026 - Stejná dokumentace a pravidla jako osobní projekty

Na žádost vlastníka se zapojuje jediná sada nastroje: profil plny, společné
workflow, topic pravidla-nastroje, pokyny AGENTS/CLAUDE, stav, deník a tematické
návody. Šablona a kontrola issues se přebírají ze stejného zdroje; nevzniká
druhá místní kopie validátorů ani směs s pracovní sadou nastroje-prace.

Dlouhý instalační návod se přesouvá do dokumentu 06, README má předepsanou
strukturu a tabulku všech dokumentů. Installer kopíruje i Markdown návody,
aby odkazy v instalovaném README fungovaly. Existující TRANSFER.md zůstává na původní
adrese kvůli odkazům ve vydání 1.2.0. Licence je popsána stejně jako u osobních
projektů: proprietární, bez udělení nové otevřené licence.

Balíček s dokumentací dostává patch verzi 1.2.1; již zveřejněný ZIP 1.2.0 se
nemění. Historie publikovaného commitu se kvůli doplnění pravidel nepřepisuje;
další commity používají úplné jméno autora a jeho GitHub noreply adresu.

## R005 - 22. 10. 2026 - Tabulka dokumentace ukazuje skutečné cesty

Vlastník upřesnil vzhled tabulky podle ostatních projektů. První sloupec
proto uvádí skutečné cesty souborů ve formátu kódu, nikoli pojmenované odkazy.
Stejně jako ve Steelsetu obsahuje i AGENTS.md. Popisy vysvětlují účel dokumentu;
informace o zachování staré URL zůstává v R004, ne v přehledové tabulce.
Jde o úpravu README na hlavní větvi, bez změny programu nebo vydaných ZIPů.
