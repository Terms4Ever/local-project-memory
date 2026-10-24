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

## R006 - 22. 10. 2026 - Úplné uložení, omezené odpovědi

Limit 24 000 znaků nesmí ořezávat data při importu ani zachycení hooku.
Verze 1.3.0 ukládá celé tělo a u legacy importu také úplný původní řádek
v komprimované soukromé tabulce. Model dostává stránkovaný obsah se stejnou
filtrací přihlašovacích údajů jako doposud. Počet řádků ani uložený otisk
nenahrazují kontrolu skutečně uloženého plného obsahu.

Schéma 3 rozšiřuje schéma 2 bez přejmenování projektů a ID. Oprava legacy
záznamů respektuje již provedené přiřazení složek, používá transakční dávky
a lze ji opakovat po přerušení. Report označí dokončení až po ověření
plných textů, dekomprimovaných originálů, vazeb a indexu. Tato dávka
je místní oprava; sama nezakládá vydání ani nezveřejňuje uživatelská data.

## R007 - 24. 10. 2026 - Zdroj 1.3.0 na hlavní větvi

Vlastník v dialogu zvolil nahrát lokální verzi 1.3.0 na GitHub. Zdroj byl jen
v nainstalované aplikaci, kam instalátor nekopíruje testy, a nainstalovaný
`test_memory.py` zůstal z 1.2.x: jeden test na něm padal, protože čekal
odmítnutí poznámky nad 24 000 znaků, které 1.3.0 podle R006 už nedělá.
Testy 1.3.0 se proto napsaly znovu podle R006: pět nových a jeden nahrazený,
celkem 55 místo dříve uváděných 56. Každý nový test byl ověřen sabotáží.
Commit nese jen zdroj a dokumentaci; vydání se ZIPem a tagem je samostatný krok.

## R008 - 24. 10. 2026 - Odpověď na dialog Codexu je samostatný prompt

V instalaci leželo ve složce `failed` 43 událostí, všechny `UserPromptSubmit`
z Codexu. Klíč promptu bez ID události byl `turn_id`. Codex ale posílá odpověď
na svůj dialog jako druhý prompt ve stejném tahu, tedy se stejným klíčem
a jiným textem; uložení to odmítlo jako konflikt idempotence a událost
přesunulo do `failed`. Ověřeno čtením databáze: u všech 43 klíč existuje
s jiným tělem, v ukázaném páru je druhé tělo odpověď na dialog.

Klíč promptu s `turn_id` proto nese i otisk textu. Opakovaný pokus se stejným
textem zůstává idempotentní, jiný text v tomtéž tahu se uloží. Uložené klíče
se nemění. Nasazení do instalace a doplnění 43 odložených událostí je
samostatný krok se zálohou databáze podle dokumentu 02.

