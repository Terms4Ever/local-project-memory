# Identita a ukládání paměti

## Výběr paměti

MCP přijímá scope project, session nebo auto. Hook předává MEMORY_SCOPE a agent
má stejné hodnoty používat při kontextu, hledání, čtení i zápisu. Požadavek pouze
s cwd je z důvodu kompatibility výslovný přístup k paměti složky.

V automatickém režimu Git projekt určuje normalizovaná skutečná cesta
git-common-dir. Worktrees sdílejí identitu, jiný klon ji má jinou. Ne-Git kořeny
se mohou výslovně zaregistrovat. Jinak je scope podle hosta claude/codex a session
ID. Není bezpečné odhadovat projekt podle jména složky nebo textu zadání.
Nerozpoznané existující Git metadata jsou chyba, ne důvod vytvořit náhradní scope.

Jiný výslovný workdir nástroje má při záznamu přednost před původní cwd.
Stejná výchozí cesta nepřepíná session na projekt. Shell příkazy cd se
neinterpretují. Změna přiřazení neprovádí automatickou migraci starých záznamů.

## Databáze

Verze schématu je SQLite user_version 3. Tabulky:

| Tabulka | Účel |
|---|---|
| projects | identity Git projektů, složek, sessions a archivů |
| aliases | výslovně registrované kořeny |
| entries | historické události a strukturované poznámky |
| entries_fts | fulltext title/body s odkazy na entries |
| imports | manifesty provedených importů |
| entry_originals | úplné původní řádky, komprimovaný JSON, SHA-256 a délka |

Události uchovávají zdroj, unikátní source_key, otisk obsahu, čas, session,
původní cwd a dostupnou větev/commit. Poznámky se přidávají; nahrazení aktivní
poznámky je transakce se supersedes. Cizí scope či již nahrazený záznam se odmítne.
Při přenosu se může změnit příslušnost projektu, původní metadata zůstávají
historickým dokladem. Identita scope není přístupové oprávnění mezi uživateli OS.

## Fronta a odolnost

Hook nejdřív uloží úplný redigovaný JSON do pending přes fsync a atomické
přejmenování. Pak provede SQLite zápis a odstraní přijatý soubor. Stejný zdrojový
klíč se stejným obsahem nevytvoří duplicitu. Kolize obsahu nebo scope je chyba.
Po úspěchu hook zkouší omezenou dávku starých událostí. Vadné se přesunou do
failed a vznikne informace o chybě; nic se nemá tiše zahodit.

SQLite má WAL, synchronous FULL a čekání na zámek. Tyto mechanismy nezaručují
zápis na plný či poškozený disk. Není trvale běžící worker, který by zpracoval
frontu při zavřených aplikacích. Snapshot se vytváří přes SQLite backup API,
aby zachoval i zapsaná data z WAL.

## Limity kontextu a změny schématu

Fulltext hledá slovní shodu, ne význam. Úryvky a počet poznámek
v kontextu jsou omezené; uložené tělo záznamu se nezkracuje. Dlouhý obsah
se čte přes offset a next_offset, nikoli jednou neomezenou odpovědí. Není automatická
AI sumarizace. Pokyny aktuálního uživatele a projektu mají přednost před historií.

Od 1.3.2 dostává každý SessionStart i UserPromptSubmit obsah vybraných aktivních
poznámek a posledních předání. Výběr dodržuje rozpočet 5 000 znaků a 6 000
bajtů UTF-8 po JSON escapování, s rezervou pro varování. Od 1.5.0 má poznámka
rozpočet až 3 500 znaků a vlastní syrové předání až 850 znaků; ostatní historie 650.
Poznámka, která se vejde, se předává celá. Delší obsah má příznak excerpt a
ID pro úplné čtení. Poslední předání a požadavek se vybírají z vlastní session.
Obsah vzpomínek předchází delším pokynům. Živý Claude Desktop totiž výstup
o velikosti 13,5 KB odložil do souboru a zobrazil pouze začátek. Úplná data
na disku tato ochrana proti odložení výstupu nekrátí.
Hledání podle dotazu přednostně vybírá poznámky a historii požadavků, teprve
jako záložní zdroj syrové výstupy nástrojů. Aktuální source_key je vyloučen.
Oznámení dokončených podúkolů nejsou vydávána za uživatelská rozhodnutí.
Následující prompt obnoví výběr i tehdy, když host po kompakci nespustí SessionStart.
Úryvek s excerpt=true může vynechat podmínku rozhodnutí; pro závazné použití
je potřeba načíst plný záznam. Výběr neznamená zaručené vybavení každého faktu.

## Kontrola předání v Claude

Verze 1.5.0 řadí poznámky před syrový Stop. Vlastní strukturované předání má
přednost pouze tehdy, když pokrývá poslední známý požadavek této session.
Jinak se nejprve vybírá nejnovější sdílená poznámka projektu. Dávno staré
vlastní předání tak nevytlačí aktuálnější společný stav. Platí původní celkový
rozpočet: každá poznámka do 3 500 znaků nemá zaručené místo ve stejném výstupu.

Po odpovědi s použitím nástrojů Stop kontroluje, zda v daném scope a session
vzniklo předání nebo rozhodnutí až po posledním zaznamenaném nástroji.
Pokud ne, vrátí jednou za pracovní krok decision=block s pokynem použít project_memory_remember.
Claude má uložit vlastní stručné shrnutí cíle, rozhodnutí, ověření a dalšího
kroku, ideálně do 1 800 znaků. Text nepíše deterministický hook; píše ho model
v jednom dodatečném pokračování, které může spotřebovat další tokeny.

Od 1.5.1 soubor v handoff-checks váže kontrolu na projekt, session a poslední
doručený prompt, včetně dokončení úlohy na pozadí nebo zprávy jiné session.
Tyto zprávy nejsou vydávány za nové oprávnění uživatele; pouze oddělují kroky.
Stavy requested, saved a not_confirmed rozlišují výzvu od skutečného zápisu.
Potvrzení se odvozuje také z databáze podle request_id a platí i po nahrazení
poznámky. Další použití nástroje nesmaže důkaz již provedeného zápisu.
Čerstvost a důvod poslední kontroly ukazuje samostatné handoff_sessions.
Opakovaný Stop ani stop_hook_active nevytvoří další výzvu pro stejný krok.

Čekající background_tasks nebo session_crons už nejsou důvod kontrolu úplně
vynechat. Bez poznámky se vyžádá průběžné předání; při existující poznámce
nejdřív po 10 minutách a další práci. Jde o kontrolu při Stop, nikoli časovač
s garantovaným intervalem. Pokyn výslovně zakazuje kvůli předání rušit nebo
vyčkávat běžící úkoly a požaduje označit nedokončenou práci. Kontext připomíná
uložení jako poslední nástroj před odpovědí. Po uložení a dalších nástrojích
může čerstvost opět klesnout; nová výzva je možná až v dalším pracovním kroku.
Codex tuto Stop kontrolu nepoužívá. Náhrada supersedes nabízí jen vlastní předchozí handoff,
nikoli předání jiné session. Bez doloženého nástroje či závěrečné odpovědi
kontrola neběží; při selhání MCP nehlásí úspěšný zápis. Přerušený chat nemusí
Stop vůbec vyvolat. Automatické zachycení událostí zůstává samostatné.
Stop ukládá verzi kontroly, stop_hook_active a počty běžících či plánovaných
úloh, bez jejich textů. Vynechání tak má dohledatelný důvod místo tichého {}.

Protokol vychází z [oficiální dokumentace hooků Claude](https://code.claude.com/docs/en/hooks).
Správné použití uložených faktů modelem nelze zaručit samotným hookem.

Souběžní konzumenti mohou stejnou událost potvrdit opakovaně, ale unikátní
klíč vytvoří jediný řádek. Zmizelý soubor mezi výpisem a čtením či smazáním
není poškozená událost. Windows sharing violation 32/33 odloží úklid do dalšího
replay; obecné problémy oprávnění se dál hlásí. Chyba staršího replay neodebere
kontext z UserPromptSubmit, ale vrátí varování a zapíše last-error.json.

Schéma 1 se čte přes existující migraci do 2, která doplňuje branch/git_commit.
Příští migrace musí mít samostatný neměnný krok, transakci, test staré databáze,
plán zálohy a důkaz zachování dat. Vydaná migrační logika se zpětně nepřepisuje.
Verze 1.3.0 přidává samostatnou transakční migraci 2 na 3: tabulku originálů
a trigger pro údržbu FTS při změně obsahu. ID, projekty a záznamy se nemění.
Starší spuštěný MCP proces může dokončit práci se stávajícími tabulkami,
ale nové parametry čtení načte až nové připojení. Nové procesy verze 1.2.x
schéma 3 odmítnou; návrat vyžaduje odpovídající zálohu, ne slepé přepsání
programu. Pozdější události se nesmějí přepsat starou zálohou.

Verze 1.4.0 přidává kompatibilní, samostatně verzovaný textový index nad
nezměněnými tabulkami schématu 3. Přechod se spouští příkazem optimize,
nikoli dlouhou implicitní migrací v hooku. Nové prázdné úložiště ho má rovnou.
Zápisy starých procesů zachytí search_dirty a nové čtení je doplní.
Status ukazuje stav migrace a chyby MCP; prázdná disková fronta sama
nepotvrzuje úplnost událostí dodaných hostem.

Volitelná rekonciliace čte skutečné dokončené nástroje Claude a Codex.
Claude API snapshoty a zděděné cizí sessions se nepočítají znovu. Codex používá
item_completed, nikoli opakované reprezentace odpovědí. Čtení pokračuje po
bajtových kurzorech, neúplný poslední řádek počká. Obsah se nikdy nespouští.
Práce dobíhá při další aktivitě hosta; u zavřených aplikací není slíbena
okamžitá obnova. Podporované jsou hlavní místní transcript soubory hostů.
