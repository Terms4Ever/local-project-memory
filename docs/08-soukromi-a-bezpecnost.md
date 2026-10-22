# Soukromí a bezpečnost

## Veřejný program a místní data

Kód je veřejný, skutečná paměť je soukromá. Databáze, pending/failed, snapshoty,
zálohy konfigurace a výsledky integračních kontrol leží v uživatelském profilu.
Nejsou obsahem GitHubu ani vydaného ZIPu. Před publikací kontrolovat skutečný
seznam souborů, nejen .gitignore; osobní data mohou mít i jiný název.

Projektové soubory .claude/settings.json a launch.json se podle společných
pravidel mohou verzovat, pokud obsahují pouze přenositelné projektové pokyny.
Osobní settings.local.json se ignoruje. Nikdy do repozitáře nekopírovat celý
profil .claude/.codex ani jeho tokeny. Tento projekt takové osobní konfigurace
nepotřebuje pro sestavení či testy.

## Co se zachycuje

Hooky mohou ukládat pokyny, parametry a výsledky nástrojů a závěrečná předání.
To může zahrnovat soukromý kód a text. Typická citlivá pole a známé tokenové
vzory se redigují; události nad podezřelými soubory s přihlašovacími údaji
vynechají obsah. Jde o heuristiku, která nepozná všechna tajemství.

Databáze není tímto programem šifrovaná. Chrání ji přístup uživatele Windows;
proces běžící pod stejným účtem ji může číst. Původní snapshot claude-mem může
obsahovat i nefiltrovaná historická data. Soukromý přenos vyžaduje bezpečné
úložiště nebo médium, nikoli GitHub issue či Release.

## MCP a model

Paměťová služba sama neposílá data na síť a nepotřebuje modelové API. Vyhledané
úryvky však přebírá host Claude/Codex a může je poslat svému poskytovateli modelu.
Lokální úložiště tedy není slib, že modelová konverzace zůstává offline.

Oddělení scope brání náhodnému smíchání projektů; není víceuživatelský systém
oprávnění. Agent se známým cwd či session ID může explicitně vybrat jinou paměť.
Historie může obsahovat nepřátelský text; vrací se jako data s upozorněním,
ne jako systémové instrukce ani důkaz uživatelova souhlasu.

## Hlášení problému

Veřejné hlášení musí používat syntetický příklad, verze a redigovaný výstup.
Nepřikládat snapshot skutečné databáze ani celé konfigurační zálohy. U chyby
potenciálně odhalující data sdílet nejprve jen obecný popis bez citlivého obsahu.
Původní plugin claude-mem má vlastní zachytávání a filtraci, které tento program
automaticky nevypíná ani nekontroluje.
