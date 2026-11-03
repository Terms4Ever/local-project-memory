# Ověření

Kontroly používají dočasné adresáře, syntetické záznamy a izolované profily.
Běžné unit testy nepotřebují účty Claude/Codex ani modelový požadavek.

## Paměť a přenos

```powershell
py -m unittest -v test_memory test_portability test_recall test_reliability
```

Testy pokrývají oddělení projektů/session/hostů, Git worktrees,
nezávislé klony, normalizaci Windows cest, persistence po restartu, souběžné
zápisy, zámek databáze a opakování fronty, přerušenou transakci, idempotenci,
nahrazení poznámky, redakci typických tajemství, MCP a zachování konfigurace.
Přenos testuje jiné cesty na druhém PC, archivy, zachování sessions, odmítnutí
přepsání cíle a chybné mapování. PowerShell launcher se reálně spouští
v izolovaném uživatelském profilu.

Verze 1.3.0 přidává testy dlouhých Unicode záznamů a stránkování, rozpočtu
odpovědi, migrace schématu 2 na 3, opravy importu po změně přiřazení projektu,
idempotence, obnovy indexu a integrity i filtrace uloženého originálu.
Tyto testy prošly lokálně na Windows s Pythonem 3.13; CI nové verze zatím neběželo.


Verze 1.3.0 má pět vlastních testů: dlouhý Unicode záznam uložený celý
a čtený po stránkách; rozpočet odpovědi rozdělený mezi ID a odmítnutí
chybného offsetu či limitu; migrace schématu 2 na 3 se stejnými ID
a fulltext, který sleduje opravu obsahu; filtrace uloženého originálu při
čtení view=source, odmítnutí změněného originálu a kontrola jeho integrity;
repair_legacy.py, který doplní nový řádek do mapovaného projektu a druhým
během nic nezduplikuje. Starý test odmítnutí poznámky nad 24 000 znaků
nahradil test úplného uložení, limit od 1.3.0 platí jen pro odpovědi.
Každý z pěti testů padá, když se rozbije funkce, kterou hlídá (sabotáž
ověřená ručně 24. 10. 2026). Opravu záznamu, který migrace už vložila
zkrácený, testy neprověřují; to se ověřilo jen na skutečné databázi.
Verze 1.3.1 přidává test, že druhý prompt ve stejném tahu Codexu (odpověď
na dialog) se uloží a stejný text podruhé se nezduplikuje.

CI běží na Windows s Pythonem 3.11 a 3.13. Verze 1.2.0 prošla v
[tomto běhu](https://github.com/Terms4Ever/local-project-memory/actions/runs/39789719618)
i z čistého ZIPu. Nový commit se posuzuje podle svého vlastního výsledku CI.

## Dokumentace a společná sada

Sadu nastroje mít v samostatném místním klonu. Příklad předpokládá sousední
složku; na konkrétním počítači použij její skutečnou cestu a PHP 8.3+ s mbstring.

```powershell
php ../nastroje/stav-projektu.php . --zapsat
php ../nastroje/kontrola-readme.php .
php ../nastroje/kontrola-dokumentace.php .
php ../nastroje/kontrola-pravidel.php . --online
git diff --check
```

Při kontrole commitované dávky předat kontrolám dokumentace/README i základní
a cílový commit podle jejich rozhraní. Místní pre-push hook a sdílené workflow
rozsah předávají samy. Online kontrola musí přečíst skutečný GitHub topic;
bez --online příslušnost na GitHubu ověřena není.

Tvar nového issue se ověřuje centrálním kontrolorem před odesláním. Existující
issues kontroluje sdílené workflow; události změn řeší Tvar issue. Šablona sama
o sobě tvar nevynucuje. Po pushi nesmí zůstat žádná červená kontrola.

## Integrační ověření instalace

```powershell
py verify_codex.py
py verify_session.py --host both
py memory.py check
```

verify_codex vyžaduje CLI codex dostupné v PATH a kompatibilní app-server API.
Zjišťuje skutečnou registraci MCP i důvěru/enabled stav hooků. verify_session
spouští nainstalované příkazy a MCP v nových procesech; vytváří malé diagnostické
záznamy. Nepotvrzuje, že host hook vyvolal v běžném chatu. Proto je nutné
ověřit nový skutečný lokální chat po každé instalaci nebo změně hosta.

## Co kontroly nedokazují

- Úplnost filtrů soukromých dat a správnost všech rozhodnutí modelu.
- Kompatibilitu všech budoucích či starších vydání Claude/Codex.
- Cloudové sessions, macOS/Linux instalaci a vlastní umístění profilů.
- Automatické zálohování nebo synchronizaci, které implementované nejsou.
- Že poznámka z jiné větve odpovídá aktuálnímu stavu kódu.

Selhání nebo přeskočení se uvede s konkrétním důvodem. U čistě dokumentační
úpravy není potřeba měnit skutečný profil uživatele; ověří se konfigurace,
odkazy, balíček, testy a CI.

## Regrese automatického vybavování 1.3.2

Dne 25. 10. 2026 prošlo lokálně na Windows a Pythonu 3.13 všech 69 testů.
Nových 13 testů v test_recall.py ověřuje obsah při startup/resume/compact
i UserPromptSubmit pro oba hosty, vyloučení aktuálního vstupu, výběr staršího
relevantního rozhodnutí proti logům, oddělení projektů a sessions, vyřazení
nahrazených poznámek, zachování celých těl i omezení kontextu. Souběh šesti
procesů ukládá 36 událostí a ověřuje jejich počet, kontext i frontu.

První zátěžový běh odhalil Windows WinError 32 při mazání souboru právě čteného
druhým hookem. Opravené odložení úklidu prošlo celou sadou. Reprodukce původního
WinError 2 testuje zmizení před čtením i po potvrzení v DB. Vynucená chyba replay
neodebere kontext a zůstává viditelná. Simulovaný zámek DB zachová frontu
i čtení kontextu. Skutečný zámek a přehrání navíc ověřuje původní sada.

Jde o lokální výsledek, nikoli nový běh GitHub CI. Simulace události compact
není důkaz skutečné kompakce hosta; skutečné chování se dokládá odděleně
v místním instalačním protokolu bez zveřejňování konverzací.

První živý průchod odhalil odložení 13,5 KB kontextu Claudem do souboru.
Rozpočet je proto měřen i v bajtech serializovaného UTF-8, obsah je před
pokyny a test dlouhých českých poznámek kontroluje velikost i pozici obsahu.
Po úpravě prošlo znovu všech 69 testů. Nainstalované hooky obou hostů předaly
uložené rozhodnutí při dalším promptu i při simulovaném compact. Samostatná
živá session Claude Desktop předala 25. 10. 2026 v 17:22 UTC přímo 4 441 znaků
kontextu s obsahem poznámek, správnou projektovou identitou a bez odložení
do persisted-output. Skutečná kompakce po nasazení zatím nebyla pozorována.

## Ověření spolehlivosti 1.4.0

Sada test_reliability.py pokrývá chybné tvary argumentů, odmítnutí rozporných
scopes, evidenci chyb bez syrových argumentů, celý konec poznámky a oddělení
rozpracovaných úloh. Dále testuje přerušený převod indexu, starého souběžného
zapisovatele, zachování plných obrázkových těl, explicitní návrat indexu bez
ztráty novějších dat a opětovný převod.

Testy rekonciliace ověřují obnovu výsledku, opakovaný běh, pozdější nativní
událost, původní datum poznámky, ochranu novějšího rozhodnutí, neúplný řádek,
uloženou chybu k opakování a skutečný pracovní adresář Codexu.
Lokální běh 28. 10. 2026: 87 testů prošlo za 34,508 s. Testy zahrnují i
odstraněnou pracovní složku s doloženou identitou a explicitní rodičovskou
vazbu subagentů Codexu včetně zděděné historie a opakovaného čtení. Skutečný
fork Claude odhalil přepsaná sessionId u zkopírovaných událostí. Dva regresní
testy ověřují stabilní ID nástroje v rámci projektu a zachování oddělení
jiného projektu. Duplicitní rekonstruované kopie jsou neaktivní a zachované.

Převod soukromé kopie se 108 181 záznamy zachoval otisky všech sloupců
entries, entry_originals, projects a aliases. Devět stejných kontextových
dotazů mělo před převodem rozsah 0,994-4,495 s, po převodu 0,106-0,959 s.
V každém výstupu byly vybrané poznámky celé. Jde o konkrétní měření,
nikoli zaručenou odezvu pro libovolný dotaz nebo velikost databáze.

Soukromý test skutečných přepisů obnovil dvě chybějící poznámky ze tří
neúspěšných pokusů a chybějící dokončený příkaz, se správným projektem
a původními daty. Opakovaný průchod nepřidal duplicity. Obsah ani přepisy
nejsou součástí veřejného repozitáře; provoz hostů dokládá místní protokol.

Nainstalované hooky obou hostů a nové MCP procesy ověřily uložení, obnovení
po další zprávě, simulovaný compact a oddělení sessions. Integrita skutečné
databáze byla ok, cizí klíče bez porušení. Živý Codex převzal 28. 10. 2026
v 09:51 UTC kontext 1.4.0 přímo, včetně celého předání o 1 179 znacích.
Claude po nasazení prokazatelně ukládal nástroje; nové předání v jeho běžném
chatu zatím nebylo pozorováno. Přímé vyvolání jeho nainstalovaného hooku prošlo.
Již otevřené MCP připojení může stále hlásit 1.3.2 a novou obsluhu API
načte až při obnovení spojení. Nebyl proveden restart rozpracovaných chatů.

## Ověření využití paměti 1.5.0

Lokální běh 2. 11. 2026: všech 96 testů prošlo za 41,888 s. Nové regresní
testy ověřují jednorázovou výzvu Stop, skutečné potvrzení uložené poznámky,
chybějící zápis bez smyčky, nový požadavek, zastaralé předání a oddělení
poznámek souběžných sessions. Pokrývají také chat bez složky, jiného hosta,
neúspěšný nástroj, background_tasks a stop_hook_active. Codex Stop zůstává
bez dodatečného pokračování.

První kontrola skutečných dat odhalila, že staré vlastní předání vytlačilo
novější sdílený stav. Po opravě a doplnění regresního testu tři read-only
dotazy předaly vybranou poznámku o 2 821 znacích celou; celé kontexty měly
4 329 znaků a 4 644 JSON/UTF-8 bajtů. Výběr trval 0,118-0,148 s. Uložená
data se při této kontrole neměnila a soukromý obsah není v repozitáři.

Test protokolu a databázové potvrzení nejsou důkaz, že model ve všech
budoucích úlohách správně využije každý fakt. Živé automatické vytvoření
poznámky v běžném desktop chatu je nutné odlišit od přímé diagnostiky hooku.

Lokálně nasazené příkazy 1.5.0 a nový MCP proces prošly 2. 11. 2026 kontrolou
výzvy Stop, zápisu a čtení přes MCP, potvrzení saved, obnovení při simulované
kompakci a oddělení jiné session i hosta. Sedm příkazů hooku mělo odezvu
0,225-0,306 s; pending i failed byly 0, diagnostika bez otevřené chyby.
Konfigurace hostů zůstaly podle SHA-256 nezměněné a předchozí app je zálohovaná.

Samostatný pokus s Claude CLI se zastavil před modelovým požadavkem:
`Failed to authenticate: OAuth session expired and could not be refreshed`.
Nevznikla modelová odpověď ani modelová poznámka; reakce modelu na Stop
proto zatím není ověřená. Tento výsledek neprokazuje stav přihlášení
samostatné desktop aplikace. Otevřené chaty ani přihlašování se neměnily.

## Ověření průběžného předání 1.5.1

Lokální běh 2. 11. 2026: 102 testů prošlo za 53,428 s. Nové regresní případy
ověřují zachování potvrzení po dalším nástroji, oddělenou čerstvost, zápis po
příchodu dalšího promptu bez následného Stop, opravu starého markeru podle
nahrazené poznámky a idempotenci této opravy. Původní text a stav poznámky
zůstávají nezměněné.

Další testy ověřují první průběžné předání při práci na pozadí, desetiminutový
odstup, novou výzvu po 25 oznámeních dokončení a ochranu proti opakovanému
Stop. Diagnostika rozlišuje chybějící prompt a pokračování vyvolané hookem,
aniž by kopírovala soukromé popisy běžících úloh.

Read-only kontrola současných dat ověřila limity kontextu a správný projekt
ve třech sessions (0,100-0,283 s). Simulace Stop používala oddělený dočasný
adresář; dvě čerstvá předání nechala být, chybějící vyžádala i při běžící úloze.
Nešlo o spuštění modelu ani změnu skutečné historie.

Po místním nasazení prošly nainstalované příkazy a nový MCP proces zápisem,
čtením, obnovením při simulované kompakci a izolací session/hosta. Výzva byla
ověřena s background_tasks. Další nástroj po zápisu zachoval potvrzení saved
a samostatně nastavil fresh=false; druhý Stop nevyvolal smyčku. Osm příkazů
hooků trvalo 0,227-0,311 s. Fronty byly prázdné a diagnostika bez chyby.
Tato diagnostika neprokazuje reakci modelu v běžném desktop chatu po aktualizaci.

## Ověření publikace 1.5.1

Při sloučení s hlavní větví zůstalo šest dříve publikovaných regresních testů.
První běh měl 107 úspěchů a jednu chybu přípravy migračního testu:
`sqlite3.OperationalError: no such trigger: entries_au`. Nová prázdná databáze
už má optimalizovaný index; test nyní výslovně připravuje historické schéma
a nad ním ověřuje migraci, zachování řádku i aktualizaci vyhledávání.
Opakovaný úplný běh na Windows s Pythonem 3.13 dne 2. 11. 2026:
`Ran 108 tests in 50.162s`, `OK`.

README, dokumentace, online pravidla a tvar issue prošly. Výsledky CI přesného
publikovaného commitu na Pythonu 3.11 a 3.13 se dokládají při uzavření
[issue #1](https://github.com/Terms4Ever/local-project-memory/issues/1).

První GitHub CI nad 72f2aa1 odhalilo na obou Pythonech chybu testu souběhu:
`test_replay_another_consumer_unlinks_before_read`, `AssertionError: 1 != 0`.
Mock porovnával cestu z TEMP s cestou normalizovanou úložištěm; na runneru
se neshodovaly a simulovaný druhý konzument se vůbec nespustil. Test nyní
používá normalizovaný domov úložiště a výslovně ověřuje vyvolání simulace.
Produkční mechanismus fronty se touto opravou nemění.

## Ověření pořadí událostí 1.5.2

Regrese 1.5.1 byla reprodukována na syntetickém transcriptu: běžné pořadí
uložilo jednu událost, opačné ani po druhém průchodu žádnou. Sedm nových testů
pokrývá opačné pořadí, restart a neúplný řádek mezi částmi, oddělení souborů
a sessions, filtr citlivého obsahu, pozdější nativní hook, transakční selhání
po vložení s opakováním a migraci starého kurzoru na konci nezměněného souboru.
Změna původního řádku nesmí přiřadit cizí výsledek a musí být vidět v diagnostice.

Lokálně 3. 11. 2026 na Windows s Pythonem 3.13:
`Ran 115 tests in 51.904s`, `OK`. Důkazy nasazení a CI přesného publikovaného
commitu se dokládají při uzavření [issue #2](https://github.com/Terms4Ever/local-project-memory/issues/2).
Soukromé transcripty ani databáze nejsou součástí testů nebo repozitáře.

Při nasazení prošel SQLite snapshot kontrolami quick_check a foreign_key_check.
Konkrétní chybějící událost byla doplněna jednou, opakovaný průchod doplnil nulu;
otisky dřívějších řádků stejné session zůstaly shodné. Konfigurace hostů se
při výměně programu nezměnily. Nainstalované hooky a nový MCP proces prošly
zápisem, čtením, potvrzením, simulovanou kompakcí a izolací jiné session/hosta.
Osm hooků mělo odezvu 0,225 až 1,231 s při souběžném doplňování historie.
Tento diagnostický průchod není novým testem rozhodování modelu.
