---
name: Úkol
about: Chyba i nová funkce, jeden tvar pro obojí
title: ''
labels: ''
assignees: ''
---

<!-- Sekce se nepřidávají ani nepřejmenovávají, nepotřebné se smažou.
     Tělo do 40 řádků: rozbor, SQL a odhady patří do docs/, ne sem. -->

## Problém

Co je špatně nebo co chybí. Jedna až tři věty, bez úvodu. U chyby napiš, co se
stane a co se stát mělo; u nové funkce, co dnes nejde a proč to vadí.

## Jak to poznat

Kroky, na kterých se to ukáže, nebo místo v aplikaci. U čísel piš, kde je vzít,
ať se dají přeměřit.

## Hotovo, když

- [ ] první ověřitelná podmínka
- [ ] druhá ověřitelná podmínka
- [ ] ověřeno v aplikaci, ne jen v kódu

## Kde to žije

Soubory a funkce, kterých se to týká. Cesty z kořene repozitáře.

## Snímky

Před při založení, po při zavření. Leží v `docs/snimky/<číslo issue>-<krátký-název>/`
a jmenují se `pred-neco.png` a `po-neco.png`. Vkládají se jako obrázek odkazem
na otisk commitu, ne na větev, a stojí v tabulce: řádek je jeden pár, prázdná
buňka tam, kde snímek není. Komentář snímky nevkládá.

| Co | Před | Po |
|---|---|---|
| Co řádek ukazuje | ![před: popis](https://github.com/<repozitář>/blob/<otisk>/docs/snimky/12-neco/pred-neco.png?raw=1) | ![po: popis](https://github.com/<repozitář>/blob/<otisk>/docs/snimky/12-neco/po-neco.png?raw=1) |
