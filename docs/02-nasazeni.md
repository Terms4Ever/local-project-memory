# Nasazení a vydávání

Program nemá webovou produkci. Distribuce je veřejný zdrojový repozitář a
ruční GitHub Release; instalace běží místně v uživatelském profilu Windows.
Push nic automaticky nenahrává na počítače uživatelů.

## Příprava vydání

1. Změň VERSION v memory.py a odpovídající instalační dokumentaci.
2. Aktualizuj stav a rozhodovací deník. Generovaný blok obnov přes
   `php ../nastroje/stav-projektu.php . --zapsat`; společný nástroj nečte Python
   konstantu, proto blok není náhradou za ověření VERSION.
3. Proveď testy, pravidla a kontrolu dokumentace podle dokumentu 04.
4. Prohlédni všechny trackované soubory. Do balíčku nepatří databáze, journal,
   soukromé logy, profily hostů, konfigurace účtů ani zálohy.
5. Commit a push musí projít místními hooky. Vyčkej na zelené workflow Kontroly
   přesného commitu, včetně Pravidla nastroje a obou testovacích verzí Pythonu.

## Sestavení a publikace

ZIP sestav z ověřeného commitu mimo zdrojovou složku:

```powershell
git archive --format=zip --prefix=local-project-memory/ --output=../local-project-memory.zip HEAD
```

Rozbal do nové složky, ověř shodu souborů s git ls-files a spusť všech 51 testů.
Nevytvářej ZIP kopií uživatelského profilu nebo pracovního adresáře s ignored
soubory. Teprve po kontrole publikuj nové vydání a jeho ZIP pod novým tagem.
Poznámky k vydání se předávají souborem; uvádějí změnu, požadavky a důkazy.
Ověř viditelnost vydání, správný cílový commit, velikost a SHA-256 přílohy.

Pro publikaci se používá přihlášení gh. Přihlašovací údaje se do repozitáře
neukládají. GitHub Actions pro tuto distribuci nepotřebují žádný vlastní secret.
Společné kontroly mají contents:read a issues:read; kontrola tvaru issues má
issues:write pouze pro vlastníka/spolupracovníky podle sdíleného workflow.

## Instalace a aktualizace PC

Postup je v dokumentu 06. Installer kopíruje vybrané programové soubory, README
a Markdown návody z docs do místní aplikace, aby její odkazy zůstaly funkční.
Celý zdrojový checkout nebo rozbalený ZIP ponech pro testy a vývojová pravidla.
Dokumenty ani pravidla nejsou vstupem běžícího MCP.

Před aktualizací udělej snapshot databáze a kopii app. Instalace zachovává cizí
hooky a zálohuje host konfigurace, ale sama nezálohuje předchozí programové
soubory. Po změně spustit nový MCP proces, zkontrolovat verzi a ověřit hooky.
Existující server stejného jména s jinou konfigurací se odmítne přepsat.

Pro první přenos historie je nutná obnova před instalací podle TRANSFER.md.
Stávající živá databáze se neobnovuje přes novější zápisy.

## Návrat a selhání

Konfiguraci vrací `py install.py --rollback <manifest>`, pokud od instalace
neproběhla další změna. Při rozdílu se návrat zastaví; musí se selektivně
odebrat pouze naše položky. Program lze vrátit z kopie app a znovu připojit MCP.
Databázi nemaž ani nenahrazuj starší kopií, jinak se ztratí novější poznámky.
Verze 1.2.1 ponechává schéma 2; její změna dokumentace nevyžaduje datovou migraci.

Selhané ověření znamená nevydávat. Automatické aktualizace, plánované zálohy,
obsluha výpadku ani vzdálené nasazení nejsou zapnuté.
