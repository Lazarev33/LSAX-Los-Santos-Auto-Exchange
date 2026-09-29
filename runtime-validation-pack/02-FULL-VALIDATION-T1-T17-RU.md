# 02 — Полная валидация P-SL-01: T1–T17 (блокер B-01)

Метка всех шагов: **OWNER_RUNTIME_ACTION_REQUIRED**. Claude ничего из этого не выполнял.
Источник: `upstream\README-PROBES.md` (DRAFT2) §5 — таблица ниже содержит действия и ожидаемые строки логов
**дословно** (английские столбцы); русский столбец — только перевод для удобства. При расхождении перевода и
оригинала действует английский текст DRAFT2.

**Начинайте только если smoke-тест этой конфигурации завершился `SMOKE S10: OK` и архив `-Phase SMOKE` собран.**

## Правило повторов (DRAFT2, без изменений)

> «each step 10 times per configuration unless stated; note the wall time of every action»

- Каждый шаг T1–T16 — **10 раз на каждой конфигурации** (MINIMAL и FULL-MODPACK). T7 — в каждом повторе две загрузки.
- T17 — **только FULL-MODPACK**. Сколько раз повторять T17 — открытый вопрос **U-01** (`03-PASS-FAIL-RULES.md`).
  Пакет **не уменьшает** число повторов: если ревьюер письменно не решил иначе до начала T17 — выполняйте T17 **10 раз**.
- Никакой шаг нельзя пропустить молча. Если шаг невозможен (например, в T3 нет быстрого сохранения, в T4 нет
  подходящей миссии) — запишите в `TEST-LOG.tsv` `NOT_POSSIBLE` и причину. Решает ревьюер.
- Прогоны smoke-теста **не** засчитываются в эти 10 повторов.

## Подготовка конфигурации

1. Игра закрыта. `scripts\START-NEW-RUN.cmd -GtaRoot "<GTA>" -Label FULL-<КОНФИГУРАЦИЯ>` (логи smoke-теста
   перемещаются в `scripts\LSAXProbe\runs\`, ничего не удаляется).
2. `scripts\SET-PROBE-CONFIG.cmd -GtaRoot "<GTA>" -ProbeProfile PSL01` (настройки B-01 из README §3:
   `SessionToken.Enabled=true`, `AnchorProbe.Enabled=false`, `IdentityProbe.Enabled=false`, `SqliteProbe.Enabled=false`).
3. Установлены оба компонента (`INSTALL-PROBES -Component All`, как в README §3). Не меняйте это между
   конфигурациями.
4. Тестовые слоты: **S, S2, S3, S4** — четыре отдельных неважных слота. Запишите их номера в `NOTES.txt`.
   S4 будет перезаписан вручную (T14) копией файла из вашей резервной копии.
5. Нужно сохранение с доступными тремя персонажами (T10) и миссией, которую можно провалить и повторить (T9).

## Таблица шагов

| Шаг | Действие (перевод) | Action — DRAFT2 verbatim | Expected log evidence — DRAFT2 verbatim | Повторы на конфигурацию |
|---|---|---|---|---|
| **T1** | Запустить игру; Story Mode загружает последнее сохранение | Start the game; Story Mode loads the latest save | `CTOR domainInstanceInProcess=1`, `TOKEN_AT_CTOR present=0`, `TOKEN_SET setOk=1 readBack=1`, `SAVEFILE_INITIAL` per file, `LOAD_MATCH` per play-time candidate | 10 |
| **T2** | Ручное сохранение в кровати убежища в слот S | Manual save at a safehouse bed into slot S | `FLAGS` transition(s) with `preSignal=[…]`, then `SAVEFILE_CHANGED … signalSeen=1 bracketLo=[…] bracketHi=[…]`; no `TICK_INTERLEAVE` | 10 |
| **T3** | Быстрое сохранение через телефон (если доступно) в слот S2 | Phone quick-save (if available) into slot S2 | as T2 | 10 |
| **T4** | Завершить миссию / занятие с автосохранением | Finish a mission / activity that autosaves | as T2 (autosave slot) | 10 |
| **T5** | Изменить наличные (купить что-то), проехать ≥ 1 км, подождать ≥ 2 игровых часов | Change cash (buy something), drive ≥ 1 km, wait ≥ 2 in-game hours | `WALLET_CHANGE` rows; no `PT_DECREASED` | 10 |
| **T6** | Пауза → Игра → Загрузить игру → слот S | Pause → Game → Load Game → slot S | `ABORTED` (informative) then `CTOR domainInstanceInProcess=+1`, `TOKEN_AT_CTOR present=0`, `LOAD_MATCH … matches=1 [S…:W=]` for the working play-time candidate | 10 |
| **T7** | Загрузить слот S ещё раз (×2) | Load slot S again (×2) | as T6 each time | 10 (в каждом повторе 2 загрузки) |
| **T8** | Умереть, затем быть арестованным | Die, then get arrested | **no** `CTOR`; wallet changes only | 10 |
| **T9** | Провалить миссию → Повторить | Fail a mission → Retry | record whether `CTOR` occurs (informs PC-1 for mission retry) | 10 |
| **T10** | Смена персонажа Майкл → Франклин → Тревор → Майкл | Switch character Michael → Franklin → Trevor → Michael | `TOKEN_PED_CHANGED newPedHadToken=0 retagOk=1` for each switch; **no** `CTOR`; no `PT_DECREASED` | 10 |
| **T11** | Консоль SHVDN (F4) `Reload()` | SHVDN console (F4) `Reload` | `CTOR domainInstanceInProcess=+1` with the **same** process key, `TOKEN_AT_CTOR present=1 value=<persisted token>` | 10 |
| **T12** | Выйти на рабочий стол без сохранения; перезапустить игру; загрузить слот S | Quit to desktop without saving; restart the game; load slot S | `CTOR domainInstanceInProcess=1` with a **new** process key, `TOKEN_AT_CTOR present=0`, `LOAD_MATCH matches=1` | 10 |
| **T13** | Поспать в кровати убежища (≥ 6 игровых часов), затем сразу сохранить в слот S3 | Sleep in a safehouse bed (≥ 6 in-game hours), then save immediately into slot S3 | `FLAGS fadedOut=1…`; no `PT_DECREASED`; then `SAVEFILE_CHANGED signalSeen=1` for S3 | 10 |
| **T14** | Пока игра запущена, скопировать файл сохранения из резервной копии поверх слота S4 в папке профиля (Проводник) | While the game runs, copy a backed-up save file over slot S4 in the profile folder (Explorer) | `SAVEFILE_CHANGED file=S4 … signalSeen=0` (no save flag transition within 10 s before) | 10 |
| **T15** | Загрузить слот S4 (скопированный файл) | Load slot S4 (the copied file) | `CTOR`, `TOKEN_AT_CTOR present=0`; `LOAD_MATCH` must **not** attribute the world to another file unless its bracket and wallets really match (record) | 10 |
| **T16** | Начать новую игру (на одноразовом профиле или после резервного копирования сохранений) | Start a New Game (on a disposable profile or after backing up saves) | `CTOR`; `CTOR_FP pt=…` value of each candidate at the first tick (PC-2 new-game bound) | 10 |
| **T17** | Только конфигурация (A): 30 мин обычной игры с активными Crime Jobs и другими модами, меняющими деньги; 10 сохранений и 10 загрузок вперемешку | Configuration (A) only: 30 min normal play with Crime Jobs and other cash-writing mods active, 10 saves and 10 loads interleaved | `WALLET_CHANGE` rows (look for change-and-restore across consecutive frames), all T2/T6 expectations | только FULL-MODPACK; число повторов — см. U-01 (по умолчанию 10, не меньше) |

## Запись каждого действия (`evidence-work\<КОНФИГУРАЦИЯ>\TEST-LOG.tsv`)

Столбцы (UTF-8, разделитель — табуляция): `config  test_id  repetition  local_time  owner_action  result  notes`.

- `local_time` — местное время **начала** действия в формате `YYYY-MM-DD HH:MM:SS` (по часам Windows).
- `result` — только то, что сделали вы: `DONE`, `NOT_POSSIBLE`, `CRASH`, `SEE_NOTES`. **Не пишите PASS/FAIL** —
  приёмку по логам решает ревьюер.
- Пример строки (не копировать в файл): `FULL-MODPACK  T6  3  2026-10-02 21:14:05  Load slot 5 via pause menu  DONE  -`
- Шаблон уже содержит пустые строки для всех шагов и повторов; добавляйте строки, если действий больше.

## Рекомендуемый цикл (удобство, не требование)

Один повтор k (k = 1…10) можно выполнить одним циклом; порядок внутри цикла не меняет определений шагов:

1. **T1** запустить игру → 2. **T2** кровать → слот S → 3. **T3** телефон → S2 → 4. **T4** миссия с автосохранением →
5. **T5** покупка, ≥ 1 км, ≥ 2 игровых часа → 6. **T8** смерть, затем арест → 7. **T10** М→Ф→Т→М →
8. **T13** сон ≥ 6 ч → сразу S3 → 9. **T6** загрузить S → 10. **T7** загрузить S ещё два раза → 11. **T9** провал миссии → повтор →
12. **T11** `Reload()` → 13. **T14** скопировать файл из резервной копии поверх S4 (игра запущена) → 14. **T15** загрузить S4 →
15. **T12** выйти без сохранения, перезапустить, загрузить S → 16. **T16** новая игра (одноразовый профиль или после резервной копии).
T17 (только FULL-MODPACK) — отдельные 30-минутные сессии.

После каждой игровой сессии (необязательно, только для контроля):
`scripts\CHECK-LOG.cmd -GtaRoot "<GTA>" -Config <КОНФИГУРАЦИЯ> -Step SUMMARY` — печатает счётчики событий,
строки `CTOR`, `SAVEFILE_CHANGED` и `PROBE_ERROR`. Вердикта не даёт. Если видите `PROBE_ERROR` или игра
вылетает — запишите в `NOTES.txt` и продолжайте, если игра запускается; если не запускается — остановитесь и
соберите доказательства.

## T14 — единственный шаг, где владелец вручную трогает файл сохранения

- Делаете **только вы**, только со слотом S4, только копией из **вашей** резервной копии. Скрипты пакета файлы
  сохранений не читают, не копируют и не меняют.
- Имя файла слота (например `SGTA50004`) и папку профиля определяете вы сами.

## Завершение конфигурации

1. Выйдите из игры полностью.
2. `scripts\COLLECT-EVIDENCE.cmd -GtaRoot "<GTA>" -Config <КОНФИГУРАЦИЯ> -Phase FULL`.
3. Затем P-DB-01 (`06-P-DB-01-RU.md`) и P-ID-01 (`07-P-ID-01-RU.md`) — можно до или после; для каждого — свой
   `START-NEW-RUN` и свой сбор доказательств.
4. Повторите всё для второй конфигурации.

B-01 закрывает **только** независимый ревьюер по правилам `03-PASS-FAIL-RULES.md`. До этого B-01 = **OPEN**.
