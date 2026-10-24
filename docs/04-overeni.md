# Ověření

Kontroly používají dočasné adresáře, syntetické záznamy a izolované profily.
Běžné unit testy nepotřebují účty Claude/Codex ani modelový požadavek.

## Paměť a přenos

```powershell
py -m unittest -v test_memory test_portability
```

Celkem 56 testů pokrývá oddělení projektů/session/hostů, Git worktrees,
nezávislé klony, normalizaci Windows cest, persistence po restartu, souběžné
zápisy, zámek databáze a opakování fronty, přerušenou transakci, idempotenci,
nahrazení poznámky, redakci typických tajemství, MCP a zachování konfigurace.
Přenos testuje jiné cesty na druhém PC, archivy, zachování sessions, odmítnutí
přepsání cíle a chybné mapování. PowerShell launcher se reálně spouští
v izolovaném uživatelském profilu.

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
