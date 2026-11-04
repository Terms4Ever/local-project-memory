# Nasazení a vydávání

## Lokální přechod na 1.4.0

Před přechodem vytvořit konzistentní SQLite snapshot a kopii aplikace.
Na kopii ověřit příkaz `py memory.py optimize`, otisky autoritativních tabulek,
testy a starého souběžného čtenáře/zapisovatele. Potom spustit stejnou migraci
na živé databázi a atomicky vyměnit soubory ověřené aplikace.
Základní schéma 3 zůstává kompatibilní; konfigurace hostů se nemusí přepisovat.

Návrat odvozeného indexu je výslovný příkaz `py memory.py rollback-index`.
Sestaví ho z aktuálních záznamů včetně práce po aktualizaci; může trvat déle
a vyžadovat zapisovací zámek. Po ověření lze obnovit předchozí program.
Starým snapshotem se živá databáze nepřepisuje. Úklid ponechaného starého
indexu vyžaduje samostatný ověřený krok.

Nová instalace může zapnout doplňování událostí přepínačem
`py install.py --host both --enable-reconciliation`. Konfigurace v domově
paměti určuje místní kořeny transcriptů a počáteční datum. Pro dosavadní
instalaci se datum nastavuje vědomě podle obnovovaného období. Zdravotní
stav obsahuje poslední běh, frontu opakování a nevyřešené chyby.

Program nemá webovou produkci. Distribuce je veřejný zdrojový repozitář a
ruční GitHub Release; instalace běží místně v uživatelském profilu Windows.
Push nic automaticky nenahrává na počítače uživatelů.

Publikace nové verze je dokončená až po commitu, pushi, ověřeném tagu vX.Y.Z
a veřejném GitHub Release s balíčkem a SHA-256. Tento postup je součástí
zadání aktualizací; po pushi se nečeká na nové zadání vydání. Výslovný pokyn
uživatele pouze připravit změny nebo nevydávat má přednost.

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
6. Ověř shodu VERSION, očekávané verze v návodu, tagu vX.Y.Z a názvu balíčku.
   Před prvním vydáním dané verze lze opravit její dokumentaci bez zvýšení
   čísla; již vydaný balíček se nikdy nepřepisuje jiným obsahem.

## Sestavení a publikace

ZIP sestav z ověřeného commitu mimo zdrojovou složku:

```powershell
git archive --format=zip --prefix=local-project-memory/ --output=../local-project-memory.zip HEAD
```

Rozbal do nové složky, ověř shodu souborů s git ls-files a spusť celou sadu testů
podle dokumentu 04.
Nevytvářej ZIP kopií uživatelského profilu nebo pracovního adresáře s ignored
soubory. Teprve po kontrole publikuj nové vydání a jeho ZIP pod novým tagem.
Poznámky k vydání se předávají souborem; uvádějí změnu, požadavky a důkazy.
Ověř viditelnost vydání, správný cílový commit, velikost a SHA-256 přílohy.

Použij anotovaný tag vX.Y.Z na přesný commit, jehož CI prošlo. Push tagu
projde běžnými hooky; pokud vyvolá další CI, ověř i tento běh. GitHub Release
musí použít existující tag (gh release create --verify-tag), český název
„Lokální paměť X.Y.Z“ a poznámky se změnami od předchozího veřejného vydání.
Přilož local-project-memory-vX.Y.Z.zip a SHA256SUMS.txt; označ aktuální stabilní
vydání jako Latest. Předchozí tagy, přílohy a data vydání nepřepisuj.

Po publikaci stáhni přílohy do další složky, porovnej jejich otisky s ověřeným
balíčkem a ověř přes API tag, commit, veřejnou viditelnost a Latest. Do záznamu
o dokončení patří odkazy na Release a jeho kontroly. Pokud některé meziverze
existovaly jen lokálně, nevytvářej pro ně zpětně fiktivní tagy; jejich změny
popiš v následujícím skutečném vydání.

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


Verze 1.3.0 přechází ze schématu 2 na 3. Před aktualizací zálohuj databázi
přes SQLite backup API a soubory aplikace. Ověř napřed izolovanou kopii.
Měň program atomickou náhradou jednotlivých souborů, hlavní memory.py až
po podpůrných souborech; host konfigurace nemusí být změněna. Spusť kontrolu
novým procesem a při obnově legacy dat použij repair_legacy.py.
Staré MCP připojení nezná stránkování, nové session musí načíst verzi 1.3.0.
Návrat na starší program bez návratu schématu není podporovaný. Nikdy
neobnovuj předchozí databázi přes novější práci bez odděleného zachování
všech mezitím zapsaných událostí.

## Přechod na 1.4.0

Základní schéma zůstává 3. Nový textový index má vlastní stav a příkaz
`py memory.py optimize`; převod lze přerušit a dokončit. Původní záznamy
a importované originály se nemění. Starý odvozený index zůstává pro návrat,
takže soubor databáze se po převodu automaticky nezmenší. Návrat indexu přes
`py memory.py rollback-index` vychází ze současných dat, nikoli ze staré zálohy.

Instalátor přijímá `--enable-reconciliation` pro průběžnou kontrolu místních
přepisů. Vlastní reconcile-config.json obsahuje enabled, since v ISO formátu
a roots pro claude/codex. Existující konfigurace se nepřepisuje. První instalace
začíná aktuálním datem; starší historii lze zahrnout výslovným posunem since.
Příkaz `py memory.py reconcile --seconds 8` provede omezený průchod. Při běžné
aktivitě hosta se spouští krátký skrytý proces, nikoli trvalá služba.

Staré MCP procesy mohou dál číst a zapisovat do kompatibilních tabulek.
Nové chování API načte až nové připojení; nové hooky se používají hned při
dalším vyvolání. Běžící uživatelské chaty kvůli aktualizaci násilně neukončovat.
Ověřit verzi nového MCP, skutečný výstup hooku, frontu obnovy a diagnostiku;
samotné zkopírování souborů není důkaz aktivace všech otevřených připojení.

## Přechod na 1.5.0

Schéma i formát původních záznamů zůstávají beze změny. Zálohuj složku app;
aktualizace nedělá datovou migraci ani obnovu databáze. Zachovej existující
ověřenou datovou zálohu. Nový modul memory_use.py musí být nasazen před
memory.py; instalátor zveřejňuje soubory atomickou náhradou v tomto pořadí.
Konfiguraci hostů není potřeba měnit, pokud již volá aktuální app/memory.py.

Nové procesy hooků používají kontrolu Stop ihned. Staré MCP připojení stále
umí požadovaný zápis, ale nové pořadí kontextu a položku handoff_checks ve
statusu načte až při novém spojení. Přímý běh nainstalovaného hooku a MCP
ověří mechanismus; skutečné vytvoření poznámky modelem je zvláštní kontrola.
Návrat spočívá v obnově předchozího app, bez přepisování živé databáze.

## Přechod na 1.5.1

Před výměnou zálohuj app a malé adresáře handoff-checks a handoff-sessions,
pokud existují. Schéma ani původní záznamy se nemění. Podpůrný memory_use.py
nasadit před memory.py. Nové záznamy kontroly mají verzi 2 a samostatný klíč;
staré soubory zůstávají čitelné. Status ověřuje potvrzení podle databáze,
takže čekající či chybný starý marker nepopře již existující poznámku.
Pomocná funkce memory_use.repair_receipts opravuje jen tyto malé soubory
podle existujícího request_id; nemění poznámky ani jejich historii.

Návrat používá zálohu programu. Ani při návratu nepřepisovat živou databázi
starou kopií. Nové diagnostické soubory starší program ignoruje. Rozpracované
chaty není nutné násilně restartovat; nový MCP status vyžaduje nové spojení.

## Přechod na 1.5.2

Před nasazením vytvoř konzistentní SQLite snapshot a kopii app. Při souběžných
zápisech drž pro backup API jednu čtecí transakci, aby se velká kopie nezačínala
opakovaně od začátku. Ověř snapshot a otisky konfigurace hostů.

Nejdřív atomicky vyměň reconcile.py, nakonec memory.py. Pod zámkem pracovníka
se při prepare doplní tabulka transcript_results a sloupec result_order_version;
základní schéma zůstává 3 a původní záznamy se nemění. Staré procesy zůstávají
kompatibilní. Chybějící historické páry se obnoví při dalším průchodu, dlouhé
soubory postupně po částech. Ověř konkrétní doplněný záznam a druhý průchod
bez duplicity. Nové hooky používají opravu ihned, otevřené chaty se neukončují.

Případný návrat obnovuje program; novější paměť se nepřepisuje snapshotem.
Starý pracovník doplňování opačné pořadí nepodporuje, pomocné tabulky ignoruje.
