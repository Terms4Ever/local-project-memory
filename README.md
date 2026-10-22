# Local Project Memory

Local, project-scoped and session-scoped memory for Claude Code and Codex.
Windows installer · Python standard library · SQLite FTS5 · stdio MCP

Vlastní lokální paměť pro práci v **Claude Code a Codexu**. Program ukládá
události přes hooky a nabízí hledání i strukturované poznámky přes MCP server
`project-memory`. Není to oficiální produkt Anthropic ani OpenAI a není to
balíček pro jejich plugin marketplace. Verze **1.2.0**.

**Tento repozitář obsahuje pouze program a syntetické testy. Neobsahuje žádné
uživatelské konverzace, databáze paměti, účty ani přihlašovací údaje.**

## Instalace na jiný počítač

Podporovaný instalátor: **Windows 11**, PowerShell, **Python 3.11+** a Git for
Windows dostupné v PATH. Místně ověřeno na Pythonu 3.13; CI testuje 3.11 a 3.13.
Claude Code / Codex musí být již nainstalované a přihlášené zvlášť. Je potřeba
verze hosta podporující použitá MCP a hook rozhraní; kompatibilita všech verzí
desktop aplikací není garantována. macOS/Linux instalátor zatím není podporován.

1. Stáhni tento repozitář přes **Code → Download ZIP** a rozbal ho, případně jej
   naklonuj. Program nestahuje ani nepřenáší tvoje staré záznamy.
2. Pokud chceš přenést i starou paměť, proveď **nejdřív obnovu zálohy** podle
   [návodu k přenosu](docs/TRANSFER.md). Jinak začni s prázdnou databází.
3. V rozbalené složce spusť jednorázově v PowerShellu:

   ```powershell
   py install.py --host both
   py memory.py check
   ```

   Jen Claude: `py install.py --host claude`. Jen Codex: `py install.py --host codex`.
   Alternativně `./install.ps1 -HostApp both`, pokud místní politika dovoluje
   spouštění PowerShell skriptů. Není potřeba administrátor ani změna politiky.
   Pokud nemáš příkaz `py`, použij `python` s Pythonem 3.11 nebo novějším.

4. Pro Codex musí být nové hooky **důvěryhodné/povolené**. Instalátor je sám
   neschvaluje. Postup ověření je níže. Pouhé připojení MCP nedokazuje, že se
   automaticky ukládají události.
5. Otevři nový lokální chat. Pokud host drží staré MCP připojení, aplikaci znovu
   otevři. V chatu napiš:

   > Ověř project-memory, jeho verzi a MEMORY_SCOPE. Ukaž, jestli používáš paměť
   > projektu, nebo session. Zkontroluj čekající události a chyby. Před prací
   > vyhledej související rozhodnutí a po práci ulož stručné předání se zdrojem.

Očekávaná verze: **1.2.0**. Ukládání/hledání nevyžaduje model, API klíč, Chroma
ani vzdálenou databázi. Samotný Claude/Codex však dál používá svého poskytovatele
modelu; kontext předaný modelu není „offline AI“.

### Co instalátor změní

Program zkopíruje do `%USERPROFILE%\.project-memory\app`. Databáze a fronty
jsou ve `%USERPROFILE%\.project-memory`, mimo tento repozitář.

Podle volby hosta přidá vlastní položky do:

| Host | Konfigurace |
| --- | --- |
| Claude | `%USERPROFILE%\.claude\settings.json`, `%USERPROFILE%\.claude.json` |
| Codex | `%USERPROFILE%\.codex\hooks.json`, `%USERPROFILE%\.codex\config.toml` |

Původní nastavení, cizí hooky a pluginy zachová. Před změnami konfigurace vytvoří
zálohy a manifest v `config-backups`. Souběžnou změnu konfigurace nebo jiný již
existující server stejného jména odmítne. Konfigurace s nestandardním profilem,
`CLAUDE_CONFIG_DIR` či `CODEX_HOME` nejsou automaticky rozpoznány; instalátor
používá výše uvedené výchozí cesty. Vzdálené/cloudové sessions nepokrývá.

### Ověření Codexu

Pokud je k dispozici CLI `codex` v PATH, lze bez modelového požadavku ověřit
MCP i skutečné načtení hooků:

```powershell
py verify_codex.py
```

Očekává se pět našich hooků `enabled=true`, `trusted=trusted`, žádné chyby a MCP
server verze 1.2.0. Pokud hooky nejsou důvěryhodné, nejprve zkontroluj jejich
příkazy a program. Po této kontrole je lze schválit:

```powershell
py verify_codex.py --trust-reviewed-hooks --manifest "CESTA_K_MANIFESTU_Z_INSTALACE"
```

Pomocník schvaluje pouze příkazy této instalace a zazálohuje změnu důvěry.
Parametr manifest aktualizuje hash pro případný návrat. Pokud daná verze Codexu
nepodporuje discovery API nebo nemáš CLI v PATH, tato kontrola selže: nepovažuj
automatické ukládání za ověřené, dokud host skutečně nespustí hook.

Přímá kontrola nainstalovaných příkazů a MCP:

```powershell
py verify_session.py --host both
```

Pro jeden host použij `--host claude` nebo `--host codex`. Kontrola vytvoří malé
diagnostické session záznamy s náhodnými ID. Nenahrazuje ověření, že host hooky
opravdu vyvolává při běžném chatu. Výsledky ukládá místně, nikoli do repozitáře.

## Jak se odděluje paměť

- **Git projekt:** skutečná cesta společné Git databáze. Worktrees sdílejí
  poznatky; nezávislé klony ne. Větev/commit jsou metadata záznamu, nikoli důkaz,
  že je změna jiného chatu již začleněná.
- **Registrovaná složka bez Gitu:** kořen a jeho podadresáře sdílejí paměť.
  Registrace: `py memory.py register "C:\work\my-project"`.
- **Bez rozpoznaného projektu:** vlastní paměť podle hosta + session/thread ID,
  i když dva chaty používají stejnou technickou pracovní složku. Stejná session
  pokračuje ve své paměti; nový chat s novým ID ji automaticky nepřebírá.
- **Připojení projektu:** staré session záznamy se automaticky neslučují.
- **Chybějící identita:** bez cwd i bez platného session ID se zápis odmítne.

Host neposkytuje jednotný spolehlivý příznak „přiřazená složka v UI“. Proto je
pro společnou paměť ne-Git složky nutná výslovná registrace. Git se pozná sám.

Hook vkládá `MEMORY_SCOPE`. Agent má tyto hodnoty předat do **každého** nástroje:
`project_memory_context`, `project_memory_search`, `project_memory_read`,
`project_memory_remember`, `project_memory_status`. Například session bez složky:

```json
{"scope":"session","platform":"codex","session_id":"ID_Z_HOOKU","query":"rozhodnutí"}
```

Nástroje odmítnou číst či nahradit ID z jiné zvolené paměti. Rozdělení není
bezpečnostní bariéra mezi uživateli počítače: lokální proces má přístup ke své
databázi a agent může výslovně vybrat jinou známou scope. Starší API s pouhým
cwd zůstává výslovným přístupem k projektové paměti.

## Spolehlivost a limity

Hooky zachycují SessionStart, UserPromptSubmit, PostToolUse, Stop, SubagentStop
a v Claude také PostToolUseFailure. Událost se nejdřív atomicky zapíše do diskové
fronty. SQLite používá WAL, FULL synchronizaci a transakce. Následující hook
zkouší čekající události znovu; chyby se zachovají ve `failed` a jsou viditelné
ve statusu. Není to běžící monitorovací služba a plný disk stále způsobí chybu.

**Nevznikají automatické AI souhrny.** Rozhodnutí a předání ukládá agent přes
remember; surové události lze vyhledat i bez těchto poznámek. Fulltext je
lexikální, kontext omezený a záznamy mohou zastarat. Paměť nezaručuje správné
chování modelu ani úplné zapamatování všech detailů. Není synchronizace mezi PC.

Filtr citlivých hodnot je pouze částečný. Databáze a zálohy mohou obsahovat
soukromé informace a nejsou šifrované tímto programem. **Nikdy je necommituj.**
Výchozí `.gitignore` pomáhá, nenahrazuje kontrolu obsahu před publikací.
Případný dříve instalovaný claude-mem zůstává zapnutý; jeho vlastní vkládání
kontextu ani izolace se touto instalací nemění.

## Záloha, přenos, návrat

```powershell
py memory.py backup
py memory.py check
py memory.py replay
```

Backup používá SQLite backup API včetně WAL. Nekopíruj pouze živý `.sqlite3`
soubor. [Přenos na druhý počítač a mapování složek](docs/TRANSFER.md).
Import existujícího claude-mem: [návod](docs/TRANSFER.md#import-z-claude-mem).

Návrat konfigurace: `py install.py --rollback "CESTA_K_MANIFESTU"`. Odmítne
přepsat pozdější uživatelské změny; pak je nutné selektivně odstranit pouze
vlastní položky. Databázi nemaže. Před aktualizací zálohuj také adresář `app`;
instalátor kopie programu aktualizuje, manifest obnovuje pouze konfiguraci.

## Vývoj a testy

```powershell
py -m unittest -v test_memory test_portability
```

Žádné externí Python balíčky. Testy používají dočasné uživatele, složky a
syntetické databáze; nevyžadují účty ani model. CI běží na Windows s Pythonem
3.11 a 3.13. Testy pokrývají izolaci, worktrees, souběžné zápisy, přerušení
transakce, replay, MCP, instalaci/rollback a přenos se změnou cest.

Rozhraní hostů: [Claude hooks](https://code.claude.com/docs/en/hooks),
[Claude MCP](https://code.claude.com/docs/en/mcp). Codex discovery pomocník je
ověřován proti skutečnému místnímu `codex app-server` a může vyžadovat úpravu
při změně jeho rozhraní.
