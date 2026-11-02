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

## R009 - 24. 10. 2026 - 1.3.1 nasazená a odložené prompty doplněné

Vlastník v dialogu zvolil nasadit 1.3.1 a doplnit 43 odložených událostí.
Postup podle dokumentu 02: záloha databáze přes SQLite backup API
(quick_check ok), záloha aplikace, atomická náhrada dokumentace a nakonec
`memory.py`. Události z `failed` dostaly klíč podle 1.3.1 (původní klíč
a otisk textu), vrátily se do `pending` a `memory.py replay` je uložil:
43 nových záznamů, `failed` i `pending` prázdné, odpověď na dialog jde
najít fulltextem. Zůstává souběh popsaný ve stavu projektu.

## R010 - 25. 10. 2026 - Obsah paměti při každém promptu

Pouhé ID záznamů nepomáhá, pokud model nezavolá čtení. Verze 1.3.2 proto
předává vybrané znění aktivních poznámek, posledních předání a relevantní historie
také při UserPromptSubmit. Obnova tak nezávisí pouze na SessionStart po kompakci.
Právě ukládaný prompt se vyloučí podle source_key, systémová oznámení zůstávají
uložená, ale nevybírají se jako uživatelské požadavky. Poznámky se hledají
odděleně od syrových logů. Výběr je lexikální a omezený, nikoli AI souhrn.

Fronta zůstává idempotentní a beze změny formátu. Chybějící soubor po zásahu
druhého konzumenta je normální souběh; dočasný zákaz smazání otevřeného souboru
ve Windows nechá již potvrzenou událost ve frontě k opakování. Jiné chyby se
nepotlačují. Selhání replay starších událostí nesmí potlačit kontext nového
promptu; varování a soubor chyby zůstávají viditelné. Zápis blokovaný SQLite
zůstane v diskové frontě a výstup jej výslovně označí jako nepotvrzený.

Zachovává se také nasazená oprava 1.3.1: dvě odlišné odpovědi uživatele uvnitř
stejného Codex turn ID mají rozdílný klíč. Tato dávka nepublikuje soukromá data.

Živá kontrola stejné dávky ukázala, že příliš dlouhý additionalContext host
odloží do souboru. Kontext proto používá rozpočet JSON/UTF-8, ne pouze počet
znaků, a samotné vzpomínky řadí před pokyny k nástrojům. Plná těla na disku
zůstávají beze změny; kratší přenosový výběr není zkrácení uložené historie.

## R011 - 28. 10. 2026 - Úplné poznámky, dohledatelné chyby a textový index

Verze 1.4.0 přijímá jednoznačné kompatibilní obaly MEMORY_SCOPE a alias
content; rozporné identity odmítá. Chyby MCP jsou viditelné ve statusu i
kontextu. Kontext upřednostňuje vlastní rozpracovaný úkol a jednu celou
poznámku před několika úryvky. Celkový limit hosta se nezvyšuje; žádný program
nevynutí správné použití každého faktu modelem.

Odvozený index má samostatnou migraci text_index_v1 se stavem a kurzorem.
Základní schéma zůstává 3 pro běžící procesy 1.3.x. Index vzniká vedle starého,
SQL fronta zachytí souběžné zápisy a jména se přepnou atomicky. Dlouhé binární
řetězce se neindexují, ale původní těla a originály se nemění. Starý index
zůstává pro výslovný návrat. Návrat ho sestaví z aktuálních dat, nesmí obnovit
starou databázi přes novější práci. Zmenšování živého souboru není součástí kroku.

Chybějící dokončené nástroje lze doplnit z místních transcriptů. Obnova má
vlastní provenienci, kontroluje session/projekt a je idempotentní. Pozdější
nativní událost nahrazuje aktivní rekonstruovanou reprezentaci. Neúspěšný
historický pokus o poznámku si ponechá původní datum a označení obnovy;
nepřepisuje novější poznámku agenta. Nezpracovatelné položky zůstávají k opakování.
Krátký volitelný pomocný proces spouštěný hooky je místní; nevzniká cloudová
automatizace, nové chaty ani trvale běžící služba.

## R012 - 2. 11. 2026 - Kontrolované předání práce v Claude

Zdravé ukládání událostí samo nezajišťuje, že agent vytvoří stručné aktuální
předání. Proto Stop v 1.5.0 jednou požádá Claude o skutečný zápis přes MCP,
pokud po použití nástrojů chybí nové vlastní předání nebo rozhodnutí.
Trvalý marker na požadavek spolu se stop_hook_active brání nekonečnému
pokračování. Úspěch se potvrzuje podle databáze, ne podle tvrzení modelu.
Nedostupný nástroj není důvod opakovaně blokovat dokončení.

Výběr kontextu dává poznámkám až 3 500 znaků v původním celkovém rozpočtu.
Vlastní předání pokrývající poslední požadavek předchází sdílenému stavu;
starší vlastní předání nemá vytlačit novější projektovou poznámku.
Zachovává se oddělení projektů, sessions i hostů a úplná uložená historie.
Nemění se schéma ani konfigurace hostů; nové chování Stop má pouze Claude.

## R013 - 2. 11. 2026 - Potvrzený zápis a čerstvé předání jsou různé stavy

Verze 1.5.1 zachovává důkaz uložené poznámky i po další práci. Kontrolní soubor
se potvrzuje podle request_id v databázi, včetně již nahrazené poznámky, takže
nový prompt ani chybějící druhý Stop nesmějí popřít provedený zápis. Čerstvost
se hodnotí zvlášť podle posledního zaznamenaného nástroje vlastní session.

Práce na pozadí může trvat hodiny. Namísto úplného vynechání dovoluje Stop
průběžné předání: při chybějícím ihned, při existujícím po 10 minutách a nové
práci. Jedna výzva na doručený prompt včetně oznámení dokončené úlohy spolu
se stop_hook_active brání smyčce. Nejde o souhlas s novou prací ani pokyn
ukončit běžící úlohy. Důvod každého rozhodnutí je viditelný ve statusu;
historické Stop záznamy nově obsahují pouze bezpečné počty a příznaky.

## R014 - 2. 11. 2026 - Publikace dosavadních místních oprav

Vlastník požádal o doplnění oprav na GitHub. [Issue #1](https://github.com/Terms4Ever/local-project-memory/issues/1)
sleduje tuto publikaci, nikoli zpětně vytvořenou historii předchozí práce.
Zdroj 1.5.1 se slučuje s hlavní větví 1.3.1: zůstává kontrola délky uloženého
originálu i šest dříve publikovaných testů. Původní rozhodnutí R001 až R009
zůstávají zachovaná; dosud nepublikované záznamy navazují jako R010 až R013.
Publikace zahrnuje program, dokumentaci a syntetické testy. Skutečná paměť,
profily a zálohy zůstávají mimo repozitář. Push zdrojů není nové vydání ZIPu
ani automatická aktualizace uživatelských instalací.
