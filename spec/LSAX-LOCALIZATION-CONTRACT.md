# LSAX — Localization Contract & Enforcement

Document: LSAX-LOCALIZATION-CONTRACT.md · Spec: LSAX MASTER SPEC v1.0 DRAFT1 · Status: DRAFT for independent audit

**ru-RU is primary and default. en-US has full parity. No user-facing hardcoded strings.** (mandatory invariant 6)

## 1. Architecture

- Core/domain never produces display text. It produces `MessageRef { key, params }` (params are typed values:
  money, distance, duration, count, text, enum-key). DESIGN DECISION D-L10N-1.
- The `Localizer` (Stage 1, UI-independent) renders `MessageRef` for the active locale. Renderers (debug inspector,
  notifications, mail, later UI) only display rendered strings.
- Technical logs (`LSAX.log`) are English and are **not** user-facing; they may contain literals.

## 2. Resource format

- Files: `scripts/LSAX/lang/ru-RU.json`, `scripts/LSAX/lang/en-US.json`, UTF-8 without BOM, flat object
  `{ "key": "message", … }`, keys sorted. A sidecar `keys.schema.json` declares each key's parameters and types
  (single source of truth for parity checks).
- Message syntax: ICU MessageFormat **subset**: literal text, `{name}`, typed `{name:money|distance|duration|number|gcdate}`,
  `{name, plural, …}`, `{name, select, …}`; `#` inside plural = formatted count; `'` escapes `{`.
  Anything else is a build error.

## 3. Key naming

`lsax.<area>.<subarea>.<item>[.<variant>]`, lowercase `[a-z0-9_]` segments separated by `.`, ≤ 96 characters.
Areas: `market, underground, heat, valuation, vehicle, title, history, mail, notify, error, reconcile, inspector,
duration, unit, settings`. Enum-derived keys use the enum name in upper case as the last segment
(`lsax.title.status.STOLEN`) — the only allowed upper-case segment.

## 4. Formatting rules

| Type | ru-RU | en-US |
|---|---|---|
| money (GTA $, integer) | `$15 100` (space U+0020 grouping, `$` prefix as in GTA HUD) | `$15,100` |
| negative money | `-$1 200` (ASCII hyphen) | `-$1,200` |
| number | `1 234,5` | `1,234.5` |
| distance | km or mi per GTA measurement setting (SHVDN `MeasurementSystem`); default by locale if unreadable: km (ru-RU), mi (en-US); stored in metres | same |
| duration (MT) | `2 дн. 5 ч`, `45 мин` | `2 d 5 h`, `45 min` |
| GC date/time (flavour) | `12.06, 14:30` | `06/12, 2:30 PM` |
| percentages | `12 %` | `12%` |

Font safety (ASSUMPTION A-L10N-1): GTA V ships an official Russian localisation, so game fonts contain Cyrillic;
no-break spaces, U+2212 and typographic quotes are **not** used in game-rendered text until the UI spike (UI-S1)
proves glyph coverage. The debug inspector may use them only if its renderer is proven.

## 5. Plurals

CLDR cardinal rules (integers):

- ru: `one` if n%10=1 ∧ n%100≠11; `few` if n%10∈2..4 ∧ n%100∉12..14; `many` if n%10=0 ∨ n%10∈5..9 ∨ n%100∈11..14;
  `other` (fractions). All four forms required in ru-RU plural messages.
- en: `one` if n=1; `other`. Both required.
Test vectors (T-L10N-4): ru 1 объявление, 2 объявления, 5 объявлений, 11 объявлений, 21 объявление, 22 объявления,
111 объявлений; en 1 listing, 2 listings, 0 listings.

## 6. Locale selection, override, fallback

- Config `Language = auto | ru-RU | en-US` (default `auto`). `auto`: GTA language (`Game.Language` =
  `GET_CURRENT_LANGUAGE`, verified in SHVDN source) English → en-US; every other language → ru-RU (primary default).
- Runtime override: debug command / settings; takes effect immediately; persisted mail re-renders because mail stores
  key + params (LSAX-DB-SCHEMA-DRAFT.md §3).
- Fallback: key missing in en-US → ru-RU text + WARN once per key per session; missing in ru-RU → visible
  `⟦lsax.key⟧` placeholder + ERROR once per key per session; parameter missing/wrong type → placeholder `⟦name⟧` +
  ERROR. Never throw from rendering.
- Diagnostics: counters of missing keys/params exposed in the debug inspector (`inspector.l10n`).

## 7. Enforcement (automated)

| Check | Where | Fails build/test when |
|---|---|---|
| T-L10N-1 parity | unit test over both JSON files + schema | key sets differ; a key lacks either locale; a message is empty |
| T-L10N-2 placeholder parity | same | placeholder names/types differ between locales or from the schema |
| T-L10N-3 syntax | same | message uses syntax outside §2 subset; plural lacks required forms |
| T-L10N-4 plural vectors | same | §5 vectors mismatch |
| T-L10N-5 untranslated suspicion | same | en-US value contains Cyrillic, or ru-RU value has no Cyrillic letter and is not in the allowlist (brand names, `$`, numbers) |
| T-L10N-6 hardcoded strings | Roslyn analyzer `LSAX001` in all LSAX projects | a string literal (or interpolated string) flows into a parameter marked `[UserFacing]` (notification, mail, UI text APIs, `MessageRef.Text`) — only `MessageRef` keys are allowed |
| T-L10N-7 key usage | build step | a key referenced in code is not in the schema, or a schema key is unused (warning) |
| T-L10N-8 length budget | same | rendered sample exceeds the slot budget declared in the schema (e.g. feed notification ≤ 99 characters) |

## 8. Key examples (appendix)

| Key | ru-RU | en-US |
|---|---|---|
| `lsax.error.wallet.unsupported_character` | Сделки LSAX доступны только Майклу, Франклину и Тревору. | LSAX deals are only available to Michael, Franklin and Trevor. |
| `lsax.reconcile.title` | LSAX: требуется сверка | LSAX: reconciliation required |
| `lsax.reconcile.body.ambiguous` | Не удалось однозначно сопоставить загруженное сохранение с историей LSAX. Сделки приостановлены до вашего выбора. | The loaded save could not be matched unambiguously to LSAX history. Trading is paused until you choose. |
| `lsax.reconcile.action.new_campaign` | Начать новую историю LSAX для этого сохранения | Start a new LSAX history for this save |
| `lsax.market.listing.count` | `{count, plural, one {# объявление} few {# объявления} many {# объявлений} other {# объявления}}` | `{count, plural, one {# listing} other {# listings}}` |
| `lsax.market.offer.received` | `{buyer} предлагает {amount:money} за {vehicle}.` | `{buyer} offers {amount:money} for your {vehicle}.` |
| `lsax.valuation.line.F_age` | `Возраст: {months} мес.` | `Age: {months} mo` |
| `lsax.valuation.line.F_mileage` | `Пробег: {km:distance} (норма {expected:distance})` | `Mileage: {km:distance} (expected {expected:distance})` |
| `lsax.valuation.line.adj.acc_severe` | Серьёзные ДТП в истории | Severe accidents on record |
| `lsax.title.status.STOLEN` | В угоне | Stolen |
| `lsax.title.status.SALVAGE` | Восстановлен после тотальной аварии | Salvage title |
| `lsax.heat.tier.BURNING` | Пылает | Burning |
| `lsax.duration.days_hours` | `{d, plural, one {# день} few {# дня} many {# дней} other {# дня}} {h} ч` | `{d, plural, one {# day} other {# days}} {h} h` |
| `lsax.mail.sale_completed.subject` | `Сделка завершена: {vehicle}` | `Sale completed: {vehicle}` |
| `lsax.mail.sale_completed.body` | `Вы продали {vehicle} за {amount:money}. Комиссия площадки: {fee:money}.` | `You sold your {vehicle} for {amount:money}. Marketplace commission: {fee:money}.` |
| `lsax.error.identity.ambiguous` | Не удалось однозначно определить этот автомобиль. Подтвердите его в инспекторе. | This vehicle could not be identified unambiguously. Confirm it in the inspector. |
| `lsax.error.title.ineligible` | `Этот автомобиль нельзя продать легально: {reason}.` | `This vehicle cannot be sold legally: {reason}.` |
| `lsax.underground.laylow` | Слишком много внимания. Скупщики не выходят на связь, пока всё не уляжется. | Too much attention. Fences won't answer until things cool down. |
