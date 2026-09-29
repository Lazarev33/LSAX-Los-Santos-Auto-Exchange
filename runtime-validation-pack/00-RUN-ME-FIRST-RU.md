# LSAX Phase 0 — пакет валидации на целевом рантайме: НАЧНИТЕ ЗДЕСЬ

> **ЭТОТ ПАКЕТ ПОДГОТОВЛЕН CLAUDE В ОБЛАКЕ.**
> **ВЛАДЕЛЕЦ ДОЛЖЕН ЗАПУСТИТЬ ЕГО ЛОКАЛЬНО, НА СВОЁМ ПК С GTA V.**
> **НИЧЕГО ИЗ ЭТОГО ЕЩЁ НЕ ПРОВЕРЕНО В GTA (RUNTIME).**
>
> Claude не имел доступа к вашему ПК, к GTA V, к вашим сохранениям, ScriptHookV, SHVDN или модпаку.
> Ни один скрипт этого пакета ни разу не запускался на Windows с GTA V. Сборка DLL и проверки скриптов
> выполнены в облаке (Linux) и имеют метку **OFFLINE VERIFIED** — это **не** доказательство, что зонды
> работают в игре.

- Статус пакета: **RUNTIME_VALIDATION_PACK_READY** + **OWNER_RUNTIME_ACTION_REQUIRED**.
- Блокер **B-01 остаётся OPEN**, пока вы не вернёте доказательства (логи), а независимый ревьюер их не проверит.
- Этот пакет **не** начинает Stage 1, **не** выдаёт SPEC_APPROVED и **не** содержит производственного кода LSAX.
- Решение PASS/FAIL по критериям принимает **только независимый ревьюер** по возвращённым логам
  (`03-PASS-FAIL-RULES.md`). Вы (владелец) выполняете шаги, записываете время и возвращаете доказательства.

Метки в пакете: **SOURCE VERIFIED** (проверено по исходникам), **OFFLINE VERIFIED** (проверено в облаке без GTA),
**OWNER_RUNTIME_ACTION_REQUIRED** (нужен ваш запуск на ПК с GTA), **INCONCLUSIVE** (не решено).
Метка «RUNTIME VERIFIED» в этом пакете **не используется нигде**.

## 1. Что это за пакет

Одноразовые зонды (probes) Phase 0 — маленькие скрипты SHVDN, которые только **пишут логи**. Они нужны, чтобы
получить на реальном рантайме доказательства, которых нельзя получить в облаке. **Это не LSAX.** Не копируйте их
код в LSAX, не распространяйте.

| Зонд | Что пишет в игру | Для чего | Обязателен |
|---|---|---|---|
| P-SL-01 SessionSignalProbe (`LsaxPhase0Probe.dll`) | только runtime-декоратор `lsax_p0_sess` на персонаже игрока (исчезает после перезапуска игры) | B-01: PC-1…PC-8, T1–T17 | **да** |
| P-DB-01 SqliteReloadProbe (`LSAXProbeSql\`) | ничего в игре; только свои файлы в `scripts\LSAXProbe\` | R-DB-1, R-DB-2, R-COMP-2, D-DB-4 | **да** |
| P-ID-01 IdentityProbe (`LsaxPhase0Probe.dll`) | один декоратор `lsax_p0_tag` на одной машине по F10 | R-ID-4, OD-4 | **да** (выключен по умолчанию, включается профилем) |
| P-SL-02 AnchorCarrierProbe (`LsaxPhase0Probe.dll`) | **пишет SP-статы** | необязательное исследование | **нет** — ВЫКЛЮЧЕН, только одноразовое сохранение, см. `08-P-SL-02-OPTIONAL-RU.md` |
| UI-S1 | — (кода нет) | R-UI-1 | только план, см. `05-UI-S1-PLAN-RU.md` |

## 2. ОБЯЗАТЕЛЬНО до любых действий

1. **Закройте GTA V полностью** (и лаунчер Rockstar/Steam/Epic, если он держит игру). Скрипты откажутся работать,
   если процесс игры запущен.
2. **Сделайте резервную копию папки профиля/сохранений.** Обычно это
   `%USERPROFILE%\Documents\Rockstar Games\GTA V\Profiles\<id>\` (у вас путь может отличаться — проверьте сами).
   Скопируйте её целиком в место **вне** папок игры. Скрипты пакета **никогда не читают, не копируют и не меняют**
   ваши сохранения — копию делаете вы.
3. **Сделайте резервную копию папки `scripts`** вашей GTA (всей папки, целиком, в место вне игры).
4. **Важные сохранения держите минимум в двух копиях** (например: внешний диск + другая папка).
   Шаги T2–T4, T13–T16 создают и перезаписывают слоты сохранений; T14 требует вручную скопировать файл сохранения.
   Используйте **отдельные, неважные слоты** для тестов.
5. **Запишите окружение** в `evidence-work\<КОНФИГУРАЦИЯ>\ENVIRONMENT.txt` (см. §5): версию сборки GTA
   (свойства `GTA5.exe`, цель — **Legacy 1.0.3725.0**), версию ScriptHookV, **точную** версию ScriptHookVDotNet
   (с номером nightly), и конфигурацию: **FULL MODPACK** или **MINIMAL**.

## 3. Пути: скрипты ничего не угадывают

- Скрипты **никогда не угадывают** путь к GTA. Вы передаёте его явно: `-GtaRoot "D:\Games\Grand Theft Auto V"`,
  или скрипт спросит его в окне. Это папка, где лежит `GTA5.exe`. **Не ставьте** `\` в конце пути в кавычках.
- Папку `scripts` скрипт находит сам: `<GTA>\scripts` или значение `ScriptsLocation` из `ScriptHookVDotNet.ini`
  (этот INI только **читается**; если там нестандартный путь — скрипт покажет его и попросит подтвердить `YES`).
- Если `AutoLoadScripts=false` в `ScriptHookVDotNet.ini` — установка остановится: включите автозагрузку сами.
- Если игра стоит в `C:\Program Files\…`, запускайте `.cmd` из командной строки **от имени администратора**
  (иначе запись в `scripts` будет запрещена Windows).

## 4. Распаковка пакета — ВАЖНО

- Распакуйте ZIP в **отдельную папку вне игры**, например `C:\LSAX-P0\`.
- **НИКОГДА не распаковывайте пакет внутрь папки GTA или внутрь `scripts`.** SHVDN загружает *все* `.dll` и
  компилирует *все* `.cs`/`.vb` файлы во всех подпапках `scripts` (SOURCE VERIFIED, `ScriptDomain.cs`):
  исходники из `source\` и DLL из `install\` загрузились бы повторно.
- Проверьте SHA-256 ZIP-архива до распаковки:
  `certutil -hashfile LSAX-PHASE0-RUNTIME-VALIDATION-PACK.zip SHA256` — значение должно совпасть с файлом
  `LSAX-PHASE0-RUNTIME-VALIDATION-PACK.zip.sha256` / отчётом, которые вы получили вместе с архивом.
- Если Windows пометила архив как «скачанный из интернета»: Свойства → «Разблокировать» до распаковки.
  (Установщик также снимает эту пометку, но **только** со скопированных им файлов зондов.)

## 5. Как запускать скрипты

Все скрипты — в папке `scripts\`. Это обёртки `.cmd` над PowerShell 5.1 (`scripts\lib\*.ps1`).
Откройте «Командную строку» (cmd) в папке пакета и запускайте, например:

```
cd /d C:\LSAX-P0\LSAX-PHASE0-RUNTIME-VALIDATION-PACK
scripts\HASH-PROBES.cmd
scripts\PREPARE-EVIDENCE-FOLDER.cmd
scripts\INSTALL-PROBES.cmd -GtaRoot "D:\Games\Grand Theft Auto V"
```

Каждый скрипт печатает `[LSAX-OK]` или `[LSAX-FAILED] … (exit code N)` и ждёт нажатия клавиши.
Сообщения скриптов — на английском (консоль Windows плохо показывает кириллицу); ключевые слова:
`OK`, `FAILED`, `STOP`, `YES`.

| Скрипт | Что делает | Что пишет |
|---|---|---|
| `HASH-PROBES.cmd` | проверяет файлы пакета по `SHA256SUMS.txt`; с `-GtaRoot` — установленные файлы | ничего |
| `PREPARE-EVIDENCE-FOLDER.cmd` | копирует `evidence-template\` → `evidence-work\` (не перезаписывает) | только папку пакета |
| `BUILD-PROBES-WINDOWS.cmd` | (необязательно) локальная сборка из `source\`, нужен .NET SDK 8 | только `build-local\` пакета |
| `INSTALL-PROBES.cmd` | ставит **только** файлы зондов, печатает каждый путь, спрашивает `YES` | `scripts\LsaxPhase0Probe.dll`, `scripts\LSAXProbeSql\`, `scripts\LSAXProbe\` |
| `SET-PROBE-CONFIG.cmd` | переключает `scripts\LSAXProbe\probe.ini` на профиль (PSL01, PDB01-STEP1, PDB01, PDB01-LEAK, PID01) | только `probe.ini` (+ резервная копия) |
| `START-NEW-RUN.cmd` | **перемещает** (не удаляет) логи текущего прогона в `scripts\LSAXProbe\runs\<метка>-<время>\` | только `scripts\LSAXProbe\` |
| `CHECK-LOG.cmd` | читает логи; шаги smoke-теста S4–S10 или сводка `SUMMARY` | только `evidence-work\` пакета |
| `COLLECT-EVIDENCE.cmd` | собирает **только** доказательства валидации в ZIP | `evidence-out\` пакета |
| `REMOVE-PROBES.cmd` | удаляет **ровно** установленные пакетом файлы (по манифесту) | удаляет только их |

Никакой скрипт не трогает: сохранения, `GTA5.exe`, ScriptHookV, SHVDN, их INI, другие моды.

## 6. Порядок работы

Для **каждой** конфигурации — **MINIMAL** (ScriptHookV + SHVDN + зонды) и **FULL MODPACK** (полный целевой модпак
LSAX) — выполняется всё. Как переключать конфигурацию (убрать/вернуть моды) — решаете вы; пакет **никогда не
двигает и не отключает** чужие моды. Рекомендуемый (не обязательный) порядок: сначала MINIMAL, затем FULL MODPACK.

| # | Шаг | Документ | Метка |
|---|---|---|---|
| 1 | Резервные копии, ENVIRONMENT.txt (§2) | этот файл | OWNER_RUNTIME_ACTION_REQUIRED |
| 2 | `HASH-PROBES.cmd`, `PREPARE-EVIDENCE-FOLDER.cmd` | этот файл | OWNER_RUNTIME_ACTION_REQUIRED |
| 3 | (необязательно) `BUILD-PROBES-WINDOWS.cmd` | этот файл, §7 | OWNER_RUNTIME_ACTION_REQUIRED |
| 4 | `INSTALL-PROBES.cmd` | `01-SMOKE-TEST-RU.md` S2 | OWNER_RUNTIME_ACTION_REQUIRED |
| 5 | Короткий smoke-тест S1–S10, **остановка при любой ошибке** | `01-SMOKE-TEST-RU.md` | OWNER_RUNTIME_ACTION_REQUIRED |
| 6 | Полная валидация T1–T17 (по 10 повторов, без сокращений) | `02-FULL-VALIDATION-T1-T17-RU.md` | OWNER_RUNTIME_ACTION_REQUIRED |
| 7 | P-DB-01 (SQLite) | `06-P-DB-01-RU.md` | OWNER_RUNTIME_ACTION_REQUIRED |
| 8 | P-ID-01 (идентичность машины; LEGACY_TRUSTED = EMPTY) | `07-P-ID-01-RU.md` | OWNER_RUNTIME_ACTION_REQUIRED |
| 9 | UI-S1 — только план, ничего не запускать | `05-UI-S1-PLAN-RU.md` | OWNER + REVIEWER DECISION |
| 10 | Сбор доказательств, отправка ревьюеру | `04-RETURN-EVIDENCE-RU.md` | OWNER_RUNTIME_ACTION_REQUIRED |
| 11 | Удаление зондов, восстановление сохранений | `09-REMOVE-AND-RESTORE-RU.md` | OWNER_RUNTIME_ACTION_REQUIRED |
| — | P-SL-02 — **необязательно**, выключено, только одноразовое сохранение | `08-P-SL-02-OPTIONAL-RU.md` | не требуется |

> **ЕСЛИ ЛЮБОЙ ШАГ SMOKE-ТЕСТА НЕ ПРОШЁЛ: ОСТАНОВИТЕ ПОЛНУЮ ВАЛИДАЦИЮ.**
> **НЕ продолжайте T1–T17.** Запустите сбор доказательств (`COLLECT-EVIDENCE.cmd -Phase SMOKE`) и отправьте
> архив доказательств независимому ревьюеру.

Ориентировочное время (оценка, не измерение): smoke ≈ 30–45 мин на конфигурацию; T1–T17 — много часов на
конфигурацию (каждый шаг 10 раз); P-DB-01 ≈ 1 ч на конфигурацию; P-ID-01 ≈ 1 ч. Можно делать в несколько
сессий — логи накапливаются, время каждого действия записывайте в `TEST-LOG.tsv`.

## 7. Готовые DLL или своя сборка

- В `install\` лежат DLL, собранные в облаке из `source\` (детерминированная сборка .NET SDK, см.
  `install\BUILD-INFO.txt`). Метка: **OFFLINE VERIFIED (build)** — компилируются, зависимости байт-в-байт равны
  подписанным пакетам nuget.org. Это **не** доказательство работы в игре.
- Если хотите собрать сами: установите .NET SDK 8 (x64), запустите `scripts\BUILD-PROBES-WINDOWS.cmd`, затем
  `scripts\INSTALL-PROBES.cmd -GtaRoot "…" -UseLocalBuild`. Отличие хешей от `install\` при другой версии SDK
  ожидаемо; запишите в ENVIRONMENT.txt, какой вариант (PACK или LOCAL BUILD) и какие хеши вы использовали.

## 8. Содержимое пакета

```
00-RUN-ME-FIRST-RU.md            этот файл
01-SMOKE-TEST-RU.md              короткий smoke-тест S1–S10
02-FULL-VALIDATION-T1-T17-RU.md  полная валидация P-SL-01 (B-01)
03-PASS-FAIL-RULES.md            критерии DRAFT2 дословно (решает только ревьюер) + открытые вопросы U-01…U-11
04-RETURN-EVIDENCE-RU.md         что и как вернуть ревьюеру
05-UI-S1-PLAN-RU.md              UI-S1: только план
06-P-DB-01-RU.md                 SQLite-зонд
07-P-ID-01-RU.md                 зонд идентичности машины
08-P-SL-02-OPTIONAL-RU.md        необязательный P-SL-02 (выключен)
09-REMOVE-AND-RESTORE-RU.md      удаление и восстановление
PACK-INFO.txt                    происхождение пакета (коммит, хеши, метки)
SHA256SUMS.txt                   SHA-256 каждого файла пакета
install\                         DLL зондов, профили probe.ini, DEPLOYMENT-MANIFEST.tsv, BUILD-INFO.txt
source\                          исходники зондов (DRAFT2, без изменений) — НЕ копировать в scripts
scripts\                         .cmd + scripts\lib\*.ps1
evidence-template\               шаблоны ENVIRONMENT.txt и TEST-LOG.tsv (FULL-MODPACK\, MINIMAL\)
upstream\README-PROBES.md        исходный пакет валидации DRAFT2 (без изменений)
```
