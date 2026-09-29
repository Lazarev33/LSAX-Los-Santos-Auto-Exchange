# 04 — Сбор и возврат доказательств

Метка: **OWNER_RUNTIME_ACTION_REQUIRED**. Архивы доказательств создаёте вы на своём ПК и отправляете независимому
ревьюеру. Claude их не видел и не проверял.

## Когда собирать

Игра должна быть **закрыта**. Запускайте сбор после каждого этапа (каждый раз получается отдельный ZIP):

| Этап | Команда |
|---|---|
| smoke-тест (успешный **или** остановленный) | `scripts\COLLECT-EVIDENCE.cmd -GtaRoot "<GTA>" -Config <КОНФИГУРАЦИЯ> -Phase SMOKE` |
| T1–T17 одной конфигурации | `… -Phase FULL` |
| P-DB-01 | `… -Phase PDB01` |
| P-ID-01 | `… -Phase PID01` |
| P-SL-02 (только если вы его делали) | `… -Phase PSL02` |

Добавьте `-IncludeShvdnLogExcerpt`, если зонд не загрузился или были ошибки SHVDN: тогда в архив попадут
**только** строки `ScriptHookVDotNet.log`, в которых упоминаются зонды, SQLite или их зависимости.

Результат: `evidence-out\LSAX-PHASE0-RUNTIME-EVIDENCE-YYYYMMDD-HHMM.zip` (местное время; если такое имя уже есть —
добавляется `-2`, `-3`…). Скрипт печатает путь, число файлов и SHA-256 архива — перепишите SHA-256 в сообщение
ревьюеру.

## Что попадает в архив (и ничего больше)

| Путь в архиве | Откуда | Зачем |
|---|---|---|
| `probe-run\current\`, `probe-run\runs\<метка>\` | `scripts\LSAXProbe\` и его `runs\`: `probe-*.log`, `sqlite-probe.log`, `probe-ledger.tsv`, `session-token.txt`, `domains-*.count` | логи зондов — основное доказательство |
| `probe-bookkeeping\` | `probe.ini`, `LSAX-PACK-INSTALL-MANIFEST.tsv`, `install-report-*.txt` | что и с какими настройками было установлено |
| `PROBE-DLL-SHA256.txt` | SHA-256 установленных `LsaxPhase0Probe.dll` и `LsaxPhase0SqliteProbe.dll` | какая сборка зондов работала |
| `owner\` | `evidence-work\<КОНФИГУРАЦИЯ>\`: `ENVIRONMENT.txt`, `TEST-LOG.tsv`, `smoke-state.txt`, `check-log-output.txt`, `NOTES*.txt` | ваше окружение, время действий, заметки |
| `pack\` | `SHA256SUMS.txt`, `PACK-INFO.txt`, `DEPLOYMENT-MANIFEST.tsv` | манифест пакета |
| `AUTO-DETECTED.txt` | версии файлов `GTA5.exe`, ScriptHookV, SHVDN; версия Windows и .NET Framework; ключи консоли SHVDN | сверка с вашим ENVIRONMENT.txt (без имён и путей) |
| `shvdn-log-excerpt.txt` | только при `-IncludeShvdnLogExcerpt` | диагностика загрузки |
| `COLLECT-INFO.txt`, `REDACTION.txt`, `EVIDENCE-SHA256SUMS.txt` | создаются скриптом | описание архива, редактирование, контрольные суммы |

**Никогда не собирается:** сохранения и папка профиля, установка GTA, другие скрипты и моды, другие логи,
скриншоты, личные документы, произвольное содержимое профиля.

## Персональные данные

- Скрипт **не собирает** имя пользователя, имя компьютера и пути. В текстовых файлах он заменяет папку GTA на
  `<GTA>`, папку scripts на `<SCRIPTS>`, «Документы» на `<DOCUMENTS>`, профиль на `<USERPROFILE>` и любые пути
  вида `C:\Users\<имя>` на `C:\Users\<USER>`. В `REDACTION.txt` для каждого файла записаны исходный SHA-256 и число
  замен — больше ничего в логах не меняется.
- Не пишите личные данные в `ENVIRONMENT.txt`, `TEST-LOG.tsv`, `NOTES.txt`.
- Перед отправкой один раз откройте ZIP и просмотрите, что внутри.

## Правила для доказательств

1. **Не редактируйте логи.** Любые пояснения — только в `TEST-LOG.tsv` или `NOTES.txt`.
2. В `TEST-LOG.tsv` — каждое действие с местным временем (для T1–T17 — каждый повтор). Не пишите PASS/FAIL.
3. Хеши сохранений на старте: зонд сам пишет SHA-256 каждого файла сохранения при каждом старте
   (`SAVEFILE_INITIAL` в `probe-*.log`). Если ревьюер попросит ещё и хеши вашей резервной копии профиля
   (README-PROBES §10 п. 3), посчитайте их сами: `certutil -hashfile <файл> SHA256` и впишите в `NOTES.txt`.
   Скрипты пакета файлы сохранений не читают.
4. Если smoke-тест остановился — всё равно соберите и отправьте архив `-Phase SMOKE` с описанием в `NOTES.txt`.

## Что отправить ревьюеру

- все ZIP-архивы `LSAX-PHASE0-RUNTIME-EVIDENCE-*.zip` с их SHA-256;
- SHA-256 архива пакета `LSAX-PHASE0-RUNTIME-VALIDATION-PACK.zip`, который вы использовали;
- короткое сообщение: какие этапы выполнены, на каких конфигурациях, что было невозможно.

После отправки: зонды можно удалить (`09-REMOVE-AND-RESTORE-RU.md`). **B-01 остаётся OPEN**, пока ревьюер не
вынесет решение.
