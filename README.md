# 🧠 Local Project Memory

**Lokální paměť projektů a chatů pro Claude Code a Codex**

Ukládá pracovní kontext na počítači, odděluje projekty i samostatné sessions
a umožňuje dohledat rozhodnutí v dalších chatech. Hooky zachycují události,
MCP nástroje zpřístupňují hledání a poznámky. Program je určen pro místní práci
na Windows; nejde o oficiální produkt Anthropic ani OpenAI.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-FTS5-003B57?logo=sqlite&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-11-0078D4)
![License](https://img.shields.io/badge/license-proprietary-red)
[![Pravidla: nastroje](https://img.shields.io/badge/pravidla-nastroje-0969da)](https://github.com/Terms4Ever/nastroje)

---

## ✨ Hlavní funkce

- **Paměť projektu:** Git worktrees sdílejí poznatky, nezávislé klony zůstávají oddělené.
- **Paměť session:** chat bez rozpoznaného projektu má vlastní kontext podle hosta a session ID.
- **Zachycení práce:** hooky ukládají pokyny, použití nástrojů a předání; disková fronta umožňuje opakovat přerušený zápis.
- **Vyhledávání a poznámky:** pět MCP nástrojů pro kontext, hledání, čtení, uložení a stav.
- **Přenos mezi PC:** soukromý snapshot s výslovným přiřazením projektů k novým cestám.
- **Instalace pro jeden či oba hosty:** zachovává cizí konfiguraci a vytváří zálohu změn.

Repozitář obsahuje program a syntetické testy, žádné osobní záznamy. Paměť
nevytváří automatické AI souhrny ani nesynchronizuje počítače. Důležitá
rozhodnutí musí pracující agent uložit; celá historie se do kontextu nevejde.

---

## 🛠️ Tech Stack

| Vrstva | Technologie |
|---|---|
| Program | Python 3.11+, pouze standardní knihovna |
| Úložiště | SQLite, FTS5, WAL a transakce |
| Integrace | MCP přes stdio a příkazové hooky |
| Instalace | Windows 11, PowerShell, Git for Windows |
| Testy | unittest, GitHub Actions na Windows, Python 3.11 a 3.13 |
| Pravidla dokumentace | sdílená sada nastroje, kontroly v PHP 8.3+ |

PHP slouží jen k údržbě repozitáře. Pro běh paměti není potřeba PHP, Chroma,
API klíč ani další Python balíčky. Claude/Codex dál používá svého poskytovatele
modelu; místní úložiště neznamená offline zpracování kontextu modelem.

---

## 📁 Struktura projektu

```text
local-project-memory/
├── memory.py                 # databáze, izolace, hooky a MCP
├── install.py                # instalace a návrat konfigurace
├── install.ps1               # spouštěcí skript pro Windows
├── transfer.py               # obnova soukromého snapshotu na novém PC
├── import_legacy.py          # volitelný import z claude-mem
├── verify_codex.py           # ověření MCP a důvěry hooků Codexu
├── verify_session.py         # přímé ověření nainstalovaných hooků
├── test_memory.py            # testy paměti, izolace a odolnosti
├── test_portability.py       # testy instalace a přenosu
├── .pravidla.json            # jediná primární sada pravidel
├── .readme-kontrola.json      # zapnuté kontroly dokumentace
├── AGENTS.md                 # pokyny vlastní tomuto projektu
├── CLAUDE.md                 # odkaz na společné pokyny agenta
├── docs/                     # stav, rozhodnutí a provozní návody
└── .github/                  # společné kontroly, testy a šablona issue
```

---

## 📚 Dokumentace

| Dokument | K čemu |
|---|---|
| `AGENTS.md` | kontext pro vývoj: doménová pravidla, kontroly a postup nasazení |
| `docs/00-stav-projektu.md` | živý stav: co je hotové, co se dělá, co je dál a na co si dát pozor |
| `docs/01-postup-prace.md` | jak se mění paměť, jaké kontroly spustit a čeho se vyvarovat |
| `docs/02-nasazeni.md` | sestavení ZIPu, vydání, aktualizace a návrat |
| `docs/03-rozhodovaci-dennik.md` | co bylo kdy rozhodnuto a proč; nové rozhodnutí je nový záznam |
| `docs/04-overeni.md` | co testy dokazují, kde běží a co je potřeba ověřit v aplikaci |
| `docs/TRANSFER.md` | přenos paměti na jiný počítač, mapování cest a import claude-mem |
| `docs/06-instalace-a-pouziti.md` | instalace, nastavení hostů a každodenní práce |
| `docs/07-identita-a-ukladani.md` | rozlišení projektu a session, fronta a schéma SQLite |
| `docs/08-soukromi-a-bezpecnost.md` | co se ukládá, omezení filtrů a co nesmí do veřejného balíčku |

---

## 🚀 Instalace (lokální vývoj)

Potřebuješ Windows, Python 3.11+ a Git dostupné v PATH. Claude Code a Codex
musí být nainstalované a přihlášené samostatně. Pro čisté testy účty potřeba nejsou.

```powershell
git clone https://github.com/Terms4Ever/local-project-memory.git
cd local-project-memory
py -m unittest -v test_memory test_portability
py install.py --host both
py memory.py check
```

Místo `both` lze zvolit `claude` nebo `codex`. Pokud nemáš příkaz `py`, použij
`python` s odpovídající verzí. Pro běžnou instalaci lze také stáhnout ZIP
z [vydání](https://github.com/Terms4Ever/local-project-memory/releases).

**Přenášíš i historii? Obnov ji před první instalací** podle
[návodu k přenosu](docs/TRANSFER.md). Obnova odmítá přepsat existující databázi.
Codex navíc vyžaduje ověřit a schválit hooky podle
[instalačního návodu](docs/06-instalace-a-pouziti.md#ověření-codexu).

Potom otevři nový místní chat a požádej o ověření `project-memory`, verze,
`MEMORY_SCOPE` a čekajících/chybných událostí. Pokud host drží staré připojení,
aplikaci znovu otevři. Restart PC není součástí postupu.

---

## 📦 Nasazení

Program se distribuuje jako zdrojový repozitář a ZIP v GitHub Releases.
Push spustí workflow **Kontroly**: společná pravidla `nastroje` a testy na
Windows pro dvě verze Pythonu. Vydání se připravuje ručně až po jejich úspěchu;
push sám neaktualizuje žádný uživatelský počítač.

Na cílovém PC instalátor zkopíruje program a přidá hooky/MCP vybraným hostům.
Databáze leží mimo repozitář v uživatelském profilu. Osobní data, konfigurace
účtů, zálohy a klíče se do vydání nezahrnují. Automatická aktualizace,
periodické zálohy ani synchronizace mezi počítači nejsou zapnuté.

Postup vydání, kontrola jeho obsahu a návrat jsou v
[dokumentaci nasazení](docs/02-nasazeni.md). Výsledky testů jsou v
[GitHub Actions](https://github.com/Terms4Ever/local-project-memory/actions).

---

## 📄 Licence

Proprietární software. Veškerá práva vyhrazena.
