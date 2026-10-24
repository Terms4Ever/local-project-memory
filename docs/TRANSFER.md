# Přenos paměti na druhý počítač

Program a jeho data jsou oddělené. GitHub slouží k distribuci programu;
osobní paměť přenes soukromě, například přes zabezpečené úložiště nebo USB.
Nesdílej databázi ani zálohu v issue, Pull Requestu nebo příloze GitHub Release.

## Začít na druhém PC bez historie

Stáhni program a spusť instalaci podle README. Vznikne nová prázdná databáze.
Účty Claude/Codex se přihlašují nezávisle; program jejich tokeny nepřenáší.

## Přenést dosavadní historii

Obnova je určena pro **čerstvý počítač bez existující databáze project-memory**.
Neumí bezpečně sloučit dvě rozpracované databáze a existující cílová data
odmítne přepsat. Na novém PC obnovu proveď před první instalací/aktivací hooků.

### 1. Původní počítač

Dokonči probíhající práci, aby během přenosu nevznikaly další nezachycené změny.
Ve složce programu nebo s plnou cestou k instalovanému programu spusť:

```powershell
py "$env:USERPROFILE\.project-memory\app\memory.py" replay
py "$env:USERPROFILE\.project-memory\app\memory.py" backup
```

Zkontroluj pending/failed ve výstupu replay; chyby před přenosem vyřeš.
Přenes pouze cestu k vytvořenému snapshotu `memory-....sqlite3` uvedenou
ve výstupu backup. Je to úplná konzistentní kopie databáze. Události vytvořené
po snapshotu na novém PC nebudou; nejde o průběžnou synchronizaci.

Nepřenášej celé `.claude`, `.codex` ani konfigurační zálohy. Obsahují místní
cesty a mohou obsahovat přihlašovací údaje. Samotné projekty přenes nebo
naklonuj zvlášť - paměť neobsahuje jejich zdrojové soubory.

### 2. Nový počítač: vybrat mapování

Stáhni repozitář programu, nainstaluj Python/Git a připrav projektové složky.
V rozbalené složce programu spusť například:

```powershell
py transfer.py list "D:\private-transfer\memory-snapshot.sqlite3"
```

Výstup ukáže ID, názvy, původní cesty a počty záznamů, nikoli konverzace.
Vyber, které původní projektové ID patří ke které nové skutečné složce.

```powershell
py transfer.py restore "D:\private-transfer\memory-snapshot.sqlite3" --map "PUVODNI_ID_PROJEKTU=C:\work\my-project"
```

Pro více projektů opakuj `--map "ID=CESTA"`. Nová složka musí existovat. Git
repozitáře se přiřadí podle své nové Git identity, ostatní složky se zaregistrují.
Dva staré projekty nelze bez dalšího namapovat na jeden nový - program to odmítne.

Příkaz ověří integritu, počty a vazby, připraví kopii stranou a teprve potom ji
zveřejní jako novou místní databázi. Snapshot nemění. Při chybě nevytvoří částečně
obnovenou cílovou databázi. Existující databázi nepřepisuje ani tehdy, je-li prázdná.

### 3. Instalace a kontrola

```powershell
py install.py --host both
py memory.py check
py memory.py search "C:\work\my-project" "známé rozhodnutí"
```

Dokonči důvěru hooků Codexu podle README a ověř nový lokální chat. Konfigurace
se vytvoří s Pythonem a cestami nového PC; původní host konfigurace se neobnovují.

## Co se nepřiřadí automaticky

- Nenamapované projekty jsou oddělené **archivy**, aby se nezaměnila stejná
  cesta na dvou počítačích. Neztrácejí se a nevkládají se do nových projektů.
- Session paměť si zachová původní host + session ID. Nový chat má jiné ID,
  proto historii automaticky nepřevezme. Samotné chaty hosta tento program
  nepřenáší. K původní session lze výslovně přistoupit přes MCP s původním ID.
- Původní cwd/větev/commit v záznamech zůstávají historickými údaji o zdroji.
- Databáze na jednotlivých PC se po obnově vyvíjejí nezávisle.

Obnova vypíše nová ID archivů. Archiv lze výslovně prohledat:

```powershell
py memory.py archive-search "ID_ARCHIVU_Z_OBNOVY" "hledaný výraz"
```

Vrací omezené úryvky. Pozdější přiřazení existujícího archivu k projektu není
automatizované; nezkoušej znovu obnovovat snapshot přes živou databázi.

## Import z claude-mem

Volitelný importer podporuje schéma s tabulkami `sdk_sessions`, `observations`,
`session_summaries`, `user_prompts`, `tool_uses`. Používá konzistentní SQLite
snapshot, původní databázi nemění a ověřuje každý importovaný řádek.
Nekompatibilní schéma se může odmítnout; nejde o univerzální import všech verzí.

```powershell
py import_legacy.py "C:\private\claude-mem.db" --home "$env:USERPROFILE\.project-memory" --map "historicky-nazev=C:\work\my-project"
```

Přiřazuj jen jednoznačně ověřené projekty. Ostatní zůstanou historickými archivy.
Opakovaný import stejné cesty a stejných záznamů je idempotentní; změněný řádek
stejného zdrojového ID vyvolá konflikt. Neměň cestu zdroje mezi opakovanými importy,
protože je součástí identity importu. Pro přenos již importované paměti použij
snapshot project-memory a `transfer.py`, nikoli opětovný import pod jinou cestou.

## Doplnění úplného obsahu staršího importu

Verze před 1.3.0 zkracovaly uložený text na 24 000 znaků. Otisk zdrojového
řádku sám o sobě nepotvrzuje úplnost uloženého textu. repair_legacy.py
pracuje s původní cestou zdroje, vytvoří konzistentní snapshot i zálohu
cíle a doplní obsah po transakčních dávkách. Ověří celé uložené texty
i skutečně dekomprimované původní řádky. Přiřazení existujících záznamů
k projektům a sessions zůstane beze změny.

```powershell
py repair_legacy.py "C:\private\claude-mem.db" --home "$env:USERPROFILE\.project-memory" --map "historicky-nazev=C:\work\my-project"
```

Mapování platí jen pro dosud neimportované záznamy. Nový nerozpoznaný projekt
zůstane archivem. Změněný zdrojový řádek vyvolá konflikt, nikoli přepsání.
Report full-content-report.json uvádí průběh a complete=true až po všech
obsahových kontrolách. Přerušený běh lze opakovat; již opravené řádky se
neduplikují. Zálohy obsahují soukromá data a nesmějí na GitHub.

Oprava importu neobnovuje výstup, který chyběl už v původním claude-mem.
Starší zkrácené nativní hooky vyžadují samostatný doložený původní záznam
hosta; program neodhadne chybějící obsah.
