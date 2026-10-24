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

Schéma 1 se čte přes existující migraci do 2, která doplňuje branch/git_commit.
Příští migrace musí mít samostatný neměnný krok, transakci, test staré databáze,
plán zálohy a důkaz zachování dat. Vydaná migrační logika se zpětně nepřepisuje.
Verze 1.3.0 přidává samostatnou transakční migraci 2 na 3: tabulku originálů
a trigger pro údržbu FTS při změně obsahu. ID, projekty a záznamy se nemění.
Starší spuštěný MCP proces může dokončit práci se stávajícími tabulkami,
ale nové parametry čtení načte až nové připojení. Nové procesy verze 1.2.x
schéma 3 odmítnou; návrat vyžaduje odpovídající zálohu, ne slepé přepsání
programu. Pozdější události se nesmějí přepsat starou zálohou.
