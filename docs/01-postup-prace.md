# Postup práce

Projekt patří do osobní sady [nastroje](https://github.com/Terms4Ever/nastroje).
Výběr deklarují .pravidla.json, úvod README a AGENTS; na GitHubu jej potvrzuje
topic pravidla-nastroje. Pracovní sada nastroje-prace se nepřidává.

## Než začneš

Přečti stav projektu, deník a dokument k měněné oblasti. Zjisti čistotu pracovní
kopie. Změna paměti se nejdřív reprodukuje na syntetické databázi; skutečné
uživatelské záznamy nejsou testovací fixture. Před údržbou živé instalace vytvoř
SQLite snapshot i kopii aplikace a zaznamenej aktuální konfiguraci.

## Při práci

Zdrojový repozitář a instalovaná aplikace jsou dvě kopie. Úprava memory.py zde
neaktualizuje běžící MCP proces ani instalaci v profilu. Neinstaluj pracovní
kopii do skutečného profilu jen kvůli testům. Installer testuj přes jeho parametry
home/user v dočasném adresáři nebo izolovaný proces s testovacím profilem.

Při změně scope ověř dva chaty se stejnou cwd, stejné ID ve dvou hostech,
Git worktree i nezávislý klon. Při změně zápisu ověř přerušení transakce,
opakování stejné události a frontu při zámku. Podrobná pravidla jsou v dokumentu 07.

## Dokumentace a issues

README je přehled; návod a omezení patří do tematických dokumentů. Každý dokument
je uveden v tabulce README. Stav se přepisuje, rozhodnutí v deníku se přidávají.
Při změně kódu se změní i odpovídající dokument v docs, nikoli jen datum stavu.

Pro skutečný úkol použij šablonu .github/ISSUE_TEMPLATE/ukol.md podle
[standardu issues](https://github.com/Terms4Ever/nastroje/blob/main/docs/05-standard-issues.md).
Tvar před odesláním ověř centrálním kontrolorem. Druh a odpovědný se doplní při
založení. Automatická kontrola je napojená na události issues vlastníka a
spolupracovníků. U veřejného hlášení nedávej do těla obsah paměti ani snapshot.
Zapojení pravidel samo o sobě není důvod vytvářet zpětné issues.

## Než řekneš hotovo

Spusť testy a kontroly podle dokumentu 04. Zkontroluj seznam souborů v commitu
a diff proti zadání. Po pushi vyčkej na všechny kontroly konkrétního commitu.
Vydávaný ZIP otestuj po rozbalení do prázdné složky. Výsledek uvádí i neověřené
části, například chybějící skutečný desktop průchod na druhém PC.

## Pasti z praxe

- 22. 10. 2026: další hook umí zpracovat starší čekající událost. Test nesmí
  předpokládat, že frontu vyprázdní až jeho poslední explicitní replay.
- 22. 10. 2026: proměnná OS nemusí být v procesu nastavená. PowerShell launcher
  rozpoznává Windows pomocí systémového API, ověřeno v izolovaném profilu.
- Kontrola pouze běžícího serveru nedokazuje fungující hooky ani ukládání.
- Vydaný ZIP se nepřepisuje. Dokumentační změna distribuovaného balíčku má novou
  patch verzi, aby staré odkazy zůstaly důkazem konkrétního obsahu.
