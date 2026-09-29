# 06 — P-DB-01: SQLite в домене скриптов SHVDN (R-DB-1, R-DB-2, R-COMP-2, D-DB-4)

Метка всех шагов: **OWNER_RUNTIME_ACTION_REQUIRED**. Выполняется на **каждой** конфигурации (MINIMAL и FULL MODPACK).
Процедура и правило PASS — дословно в `03-PASS-FAIL-RULES.md` (V-4); ниже — те же шаги с командами пакета.
Зонд пишет только свои файлы в `scripts\LSAXProbe\` (`sqlite-probe.log`, `p0*.db`) и **не трогает игру**.

Числа повторов из DRAFT2 (не уменьшать): шаг 3 — **20** `Reload()` и **5** загрузок сохранения; шаг 4 — **5** `Reload()`.

## Шаги (одна конфигурация)

| Шаг | Действие | Что записать в `TEST-LOG.tsv` / что ищет ревьюер |
|---|---|---|
| 0 | Игра закрыта. `scripts\START-NEW-RUN.cmd -GtaRoot "<GTA>" -Label PDB01-<КОНФИГУРАЦИЯ>` | — |
| 1 | `scripts\SET-PROBE-CONFIG.cmd -GtaRoot "<GTA>" -ProbeProfile PDB01-STEP1` (без `NativePath`). **Запустите игру заново** (новый процесс — см. U-08), Story Mode, подождите 60 с, выйдите из игры | строка `PDB-1`; ревьюер фиксирует `SQL_FAIL` (ожидается по E6-4) или `SQL_OPEN` |
| 2 | `scripts\SET-PROBE-CONFIG.cmd -GtaRoot "<GTA>" -ProbeProfile PDB01` (`NativePath=<scripts>\LSAXProbeSql\e_sqlite3.dll`, см. U-04). Запустите игру, Story Mode, подождите 60 с | строка `PDB-2`; ожидается `SQL_OPEN` с `nativeModule` = этот файл |
| 3a | В той же сессии: F4 → `Reload()` **20 раз**, между повторами ≥ 10 с | 20 строк `PDB-3R`, повтор 1…20, время каждого |
| 3b | Затем **5 загрузок** сохранения: Пауза → Игра → Загрузить игру → тестовый слот; после каждой ≥ 30 с | 5 строк `PDB-3L`, повтор 1…5 |
| 4 | Выйдите из игры. `scripts\SET-PROBE-CONFIG.cmd -GtaRoot "<GTA>" -ProbeProfile PDB01-LEAK` (`CloseOnAbort=false`). Запустите игру, Story Mode, F4 → `Reload()` **5 раз** | 5 строк `PDB-4R`; информативно: есть ли `database is locked` (R-DB-3) |
| 5 | Выйдите из игры. `scripts\SET-PROBE-CONFIG.cmd -GtaRoot "<GTA>" -ProbeProfile PSL01`. `scripts\COLLECT-EVIDENCE.cmd -GtaRoot "<GTA>" -Config <КОНФИГУРАЦИЯ> -Phase PDB01` | путь и SHA-256 ZIP |

Контроль по ходу (необязательно): `scripts\CHECK-LOG.cmd -GtaRoot "<GTA>" -Config <КОНФИГУРАЦИЯ> -Step SUMMARY`
печатает число строк `SQL_*`. Вердикта не даёт.

## Что проверит ревьюер (кратко; точный текст — V-4)

- шаги 2–3 успешны **20/20** и **5/5** на (A) и (B): каждый `CTOR`/`SQL_CTOR` даёт `SQL_OPEN`, `SQL_COMMIT_US`,
  `SQL_DEPENDENCY`, `SQL_PRAGMAS main.synchronous=2 proj.synchronous=1 proj.journal=wal`, `SQL_TWO_FILE_COMMIT_US`,
  `SQL_SNAPSHOT tables=[projection_meta,vehicle]`, `SQL_JOURNAL_BACKUP tables=[probe_row]`, `SQL_RESTORE`
  с водяным знаком снимка, `SQL_WATERMARK_AT_START`; ноль `SQL_FAIL`;
- p95 `SQL_COMMIT_US` журнала ≤ 10 000 мкс (R-DB-2);
- каждый путь `SQL_DEPENDENCY` внутри `<GTA>\scripts\LSAXProbeSql\` (R-COMP-2) — см. открытый вопрос **U-03**
  (теневое копирование SHVDN); пакет это правило не меняет;
- списки таблиц снимка и резервной копии журнала точно как выше (D-DB-4).

На конфигурации FULL MODPACK `INSTALL-PROBES` заранее записал в `install-report-*.txt` (и показал вам), есть ли у
других модов одноимённые DLL (`System.Memory.dll` и т. п.) — это входные данные для R-COMP-2, ничего не
удалялось и не менялось.
