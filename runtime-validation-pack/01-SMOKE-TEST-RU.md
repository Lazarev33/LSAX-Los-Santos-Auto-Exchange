# 01 — Короткий smoke-тест S1–S10 (на каждой конфигурации, до T1–T17)

Метка всех шагов: **OWNER_RUNTIME_ACTION_REQUIRED**. Ничего из этого не выполнялось Claude.

Цель: за 30–45 минут убедиться, что зонды загружаются и пишут основные сигналы, **до** многочасовой
полной валидации. Smoke-тест **не** является приёмкой: «OK» от `CHECK-LOG.cmd` значит только «можно продолжать».
PASS/FAIL по PC-1…PC-8 и P-DB-01 решает только независимый ревьюер (`03-PASS-FAIL-RULES.md`).
Прогоны smoke-теста **не засчитываются** в 10 повторов T1–T17.

> **ЕСЛИ ЛЮБОЙ ШАГ SMOKE-ТЕСТА НЕ ПРОШЁЛ: ОСТАНОВИТЕ ПОЛНУЮ ВАЛИДАЦИЮ.**
> **НЕ продолжайте T1–T17.** Закройте игру, запустите
> `scripts\COLLECT-EVIDENCE.cmd -GtaRoot "<GTA>" -Config <КОНФИГУРАЦИЯ> -Phase SMOKE`
> и отправьте архив доказательств независимому ревьюеру.
> «Не прошёл» = любой `[LSAX-FAILED]`, любая строка `SMOKE Sx: FAILED`, вылет игры, зонд не виден в консоли SHVDN,
> или вы не смогли выполнить действие шага.

Обозначения: `<GTA>` — ваша папка с `GTA5.exe` (вы вводите её сами); `<КОНФИГУРАЦИЯ>` — `MINIMAL` или
`FULL-MODPACK`. Команды выполняются в cmd из корня распакованного пакета.

**Подготовка:** режим экрана GTA «Оконный без рамки» (чтобы переключаться Alt+Tab к проверкам, пока игра работает);
сохранение, где доступны **все три** персонажа (нужно для S8 и T10); **отдельный неважный слот** для тестовых
сохранений (запишите его номер). Консоль SHVDN открывается клавишей **F4** (или вашей `ConsoleKeyBinding`;
`INSTALL-PROBES` печатает её). Команды консоли пишутся со скобками: `Reload()`, `ListScripts()`.

## Шаги

| Шаг | Действие владельца | Проверка | Ожидается |
|---|---|---|---|
| **S1** | Игра закрыта. Резервные копии сделаны (`00-RUN-ME-FIRST-RU.md` §2). `scripts\HASH-PROBES.cmd` → затем `scripts\PREPARE-EVIDENCE-FOLDER.cmd` → заполните `evidence-work\<КОНФИГУРАЦИЯ>\ENVIRONMENT.txt` | вывод скриптов | `[LSAX-OK] All checked files match.` и `[LSAX-OK] evidence-work ready` |
| **S2** | `scripts\INSTALL-PROBES.cmd -GtaRoot "<GTA>"` — прочитайте список путей, введите `YES`. Затем `scripts\HASH-PROBES.cmd -GtaRoot "<GTA>"`; оба SHA-256 DLL впишите в ENVIRONMENT.txt | вывод скриптов | `[LSAX-OK] Probe files installed…`; все строки `ok`; профиль `probe.ini` = PSL01 |
| **S3** | `scripts\START-NEW-RUN.cmd -GtaRoot "<GTA>" -Label SMOKE-<КОНФИГУРАЦИЯ>` (при вопросе — `YES`) | вывод скрипта | `[LSAX-OK]` (переносит старые логи в `runs\`, ничего не удаляет) |
| **S4** | Запустите GTA V → Story Mode, загрузится последнее сохранение. Подождите ≥ 60 с после появления управления. F4 → `ListScripts()` → должны быть видны `SessionSignalProbe`, `IdentityProbe`, `AnchorCarrierProbe`, `SqliteReloadProbe`. Закройте консоль. Alt+Tab → `scripts\CHECK-LOG.cmd -GtaRoot "<GTA>" -Config <КОНФИГУРАЦИЯ> -Step S4` | CHECK-LOG S4 | `SMOKE S4: OK` |
| **S5** | Ручное сохранение в кровати убежища в тестовый слот (запишите номер). Подождите 15 с. `CHECK-LOG … -Step S5` | CHECK-LOG S5 | `SMOKE S5: OK` |
| **S6** | Пауза → Игра → Загрузить игру → слот из S5. Подождите ≥ 60 с после появления управления. `CHECK-LOG … -Step S6` | CHECK-LOG S6 | `SMOKE S6: OK` |
| **S7** | F4 → `Reload()` → Enter; закройте консоль; подождите 30 с. `CHECK-LOG … -Step S7` | CHECK-LOG S7 | `SMOKE S7: OK` |
| **S8** | Одна смена персонажа (например Майкл → Франклин); дождитесь окончания + 30 с. `CHECK-LOG … -Step S8` | CHECK-LOG S8 | `SMOKE S8: OK` |
| **S9** | Выйдите из игры полностью. `scripts\SET-PROBE-CONFIG.cmd -GtaRoot "<GTA>" -ProbeProfile PDB01`. Запустите GTA → Story Mode, подождите 60 с; F4 → `Reload()`; подождите 30 с. `CHECK-LOG … -Step S9` | CHECK-LOG S9 | `SMOKE S9: OK` |
| **S10** | Выйдите из игры полностью. `scripts\SET-PROBE-CONFIG.cmd -GtaRoot "<GTA>" -ProbeProfile PSL01`. `CHECK-LOG … -Step S10`. Затем **всегда** `scripts\COLLECT-EVIDENCE.cmd -GtaRoot "<GTA>" -Config <КОНФИГУРАЦИЯ> -Phase SMOKE` | CHECK-LOG S10 + ZIP | `[LSAX-OK] Smoke test complete (gates only - NOT runtime acceptance)` и путь к ZIP |

Каждый шаг запишите строкой в `evidence-work\<КОНФИГУРАЦИЯ>\TEST-LOG.tsv` (местное время, что сделали,
`SMOKE-OK` или `SMOKE-FAILED`). Шаги проверяются строго по порядку: `CHECK-LOG` откажется проверять S6, если S5
не записан как OK. Повторить smoke-тест с начала можно: `START-NEW-RUN` (S3), затем снова S4 — S4 сбрасывает
состояние проверок этой конфигурации.

## Что проверяет каждый шаг (откуда требование)

Проверки — это ожидания из `upstream\README-PROBES.md` (DRAFT2) для одного прохода, а не критерии приёмки.

| Шаг | Проверки `CHECK-LOG` (все должны быть `ok`) | Источник в DRAFT2 |
|---|---|---|
| S4 | есть `CTOR`; последний `CTOR domainInstanceInProcess=1`; `TOKEN_AT_CTOR registered=1 present=0`; `TOKEN_SET setOk=1 readBack=1`; в `CTOR_FP` есть хотя бы один кандидат `pt=…`; есть `SAVEFILE_INITIAL`, нет `SAVEROOT_MISSING`; есть `LOAD_MATCH`; ноль `PROBE_ERROR`. Печатает версию SHVDN из `CTOR` (запишите её) | T1, PC-2 («at least one candidate stat exists»), PC-7, R-ENV-1 |
| S5 | ровно одна новая строка `SAVEFILE_CHANGED`, у неё `signalSeen=1`; нет нового `CTOR`; ноль `TICK_INTERLEAVE`, `PT_DECREASED`, `PROBE_ERROR` | T2, PC-4 |
| S6 | ровно один новый `CTOR`, тот же процесс, `domainInstanceInProcess` +1; `TOKEN_AT_CTOR present=0`; `TOKEN_SET setOk=1 readBack=1`; `LOAD_MATCH matches=1 [<файл из S5>:W=` или `:W?]`; нет новых `SAVEFILE_CHANGED`; ошибки 0. Печатает число `ABORTED` (PC-6, информативно) | T6, PC-1, PC-4, PC-5, PC-8 |
| S7 | ровно один новый `CTOR`, тот же процесс, +1; `TOKEN_AT_CTOR present=1` со значением прежнего токена; `TOKEN_SET` ок; ошибки 0 | T11, PC-5, PC-7 |
| S8 | нет нового `CTOR`; есть `TOKEN_PED_CHANGED`, каждая строка `newPedHadToken=0 retagOk=1`; ошибки 0 | T10, PC-1, PC-7 |
| S9 | ≥ 2 новых блока `SQL_CTOR` (старт + `Reload()`); в каждом: `SQL_PRELOAD ok=True` для `<scripts>\LSAXProbeSql\e_sqlite3.dll`, `SQL_OPEN nativeModule=` этот же файл, есть `SQL_COMMIT_US`, `SQL_DEPENDENCY`, `SQL_WATERMARK_AT_START`, `SQL_TWO_FILE_COMMIT_US`, `SQL_PRAGMAS main.synchronous=2 proj.synchronous=1 proj.journal=wal`, `SQL_SNAPSHOT tables=[projection_meta,vehicle]`, `SQL_JOURNAL_BACKUP tables=[probe_row]`, водяной знак `SQL_RESTORE` = `SQL_SNAPSHOT`; ноль `SQL_FAIL`. Печатает (не решает) времена коммитов и пути `SQL_DEPENDENCY` | P-DB-01 шаги 2–3 (один проход) |
| S10 | игра закрыта; во всём прогоне ноль `PROBE_ERROR`, `TICK_INTERLEAVE`, `PT_DECREASED`, `SQL_FAIL`; `probe.ini` снова = профиль PSL01 | общий |

Что `CHECK-LOG` **не** решает (решает ревьюер): 10/10 повторов, точность `LOAD_MATCH` по всем кандидатам,
p95 коммитов (R-DB-2), расположение зависимостей (R-COMP-2, см. `03-PASS-FAIL-RULES.md` U-03), PC-6.

## Если что-то пошло не так

- Зонда нет в `ListScripts()` или нет файла `scripts\LSAXProbe\probe-*.log` → STOP. При сборе доказательств
  добавьте `-IncludeShvdnLogExcerpt`: в архив попадут **только** строки `ScriptHookVDotNet.log`, где упомянуты зонды
  или SQLite.
- Игра вылетела → STOP, соберите доказательства, опишите в `NOTES.txt` (в `evidence-work\<КОНФИГУРАЦИЯ>\`).
- Скрипт пишет `[LSAX-FAILED]` → прочитайте сообщение; если причина — ваш ввод (путь, игра запущена), исправьте и
  повторите этот же шаг; иначе STOP.
- Никогда не правьте логи. Пояснения — только в `TEST-LOG.tsv` / `NOTES.txt`.
