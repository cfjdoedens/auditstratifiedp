# auditstat — projectgeheugen

## Wat is dit project?

Python-pakket voor statistische auditmethoden voor de Rijksoverheid. Overkoepelend pakket `auditstat` met subpakketten:

- `auditstat.stratified` — gestratificeerde steekproefaudits (HARo-compatibel)
  - `plan_stratified()` — berekent optimale steekproefomvang per stratum
  - `eval_stratified()` — combineert steekproeven via convolutie tot één gezamenlijke foutschatting
  - `plot_kanskromme()` — visualiseert de resulterende kansverdeling
- `auditstat.sso` — (in voorbereiding)

Live Streamlit-app: https://auditstratifiedp-ko3vmnx8pfjkuf8xacb8kx.streamlit.app/

## Bestandsstructuur

```
auditstat/
  __init__.py
  stratified/               # Was: auditstratified/
    __init__.py
    eval_stratified.py      # Convolutie-evaluatie (FFT, Monte Carlo, direct)
    plan_stratified.py      # Heuvelklimalgoritme voor steekproefplanning
    plot_kanskromme.py      # Visualisatie
    utils.py                # HARo-helpers: haro_nog_nodige_zekerheid, drawsneeded, foutloze_posten_equivalent
    valideer_granulariteit.py
    analyseer_klimheuristiek.py
  sso/
    __init__.py             # Leeg, inhoud volgt later
tests/
  __init__.py
  stratified/              # Spiegelt auditstat/stratified/
    __init__.py
    test_eval.py
    test_plan.py
    test_utils.py
    test_klimheuristiek.py
    test_valideer_granulariteit.py
    test_convolutie_analytisch.py
    test_hypothesis_properties.py
  sso/                     # Spiegelt auditstat/sso/
    __init__.py
    test_max_fout_benaderd_SSO.py
    test_max_fout_exact_SSO.py
app.py                    # Streamlit-applicatie
ruff.toml                 # Linting-configuratie
pyproject.toml            # Pakketconfiguratie (name = "auditstat", versie 0.1.x)
push_new_version.sh       # Script: bumpt versie, commit, tag, push naar GitHub + PyPI
```

## Ontwerpkeuzes

**assert vs. TypeError/ValueError:**

`eval_stratified` gebruikt **geen asserts meer** voor invoervalidatie — alle checks gooien nu `TypeError` of `ValueError`. Dit is bewust: `app.py` vangt `ValueError` op in `try/except`-blokken, en `assert` kan worden uitgeschakeld met `python -O`. Voorkeur voor nieuwe code: gebruik altijd expliciete exceptions.

- `raise TypeError` voor verkeerd type argument: `steekproeven` geen DataFrame, `zekerheid`/`granulariteit`/`start`/`vergelijk` verkeerd type
- `raise ValueError` voor verkeerde waarden — zowel API-parameters (`model`, `zekerheid`, `methode`, `granulariteit`) als gebruikersinvoer (leeg DataFrame, ontbrekende kolommen, dubbele stratumnamen, ongeldige kolominhoud)

`plan_stratified` gebruikt **nog wel asserts** voor API-contractchecks (`model`, `zekerheid`, `granulariteit`, type van `steekproeven`, aanwezigheid van vereiste kolommen) en `raise ValueError` voor gebruikersinvoerfouten. Dit is historisch en verdient migratie naar het patroon van `eval_stratified`.

**Convolutiemethoden in eval_stratified:** `"FFT paarsgewijs"`, `"FFT samen"`, `"direct"`, `"Monte Carlo"`. Plan gebruikt altijd `"FFT samen"`.

**HARo-risicocombinaties:** 27 mogelijke combinaties van IHR × IBR × CAR (`H`/`M`/`L`), getest via `@pytest.mark.parametrize`.

**Scope van de `materialiteit`-kolom in het DataFrame:**
- Slaat uitsluitend op het **laagstratum** — zowel in `plan_stratified` als in `eval_stratified`.
- In `plan_stratified`: gebruikt als `allowed_defect_rate` in `drawsneeded()` voor de basissteekproefomvang.
- In `eval_stratified`: gebruikt in `foutloze_posten_equivalent()` om `extra_foutloze_posten` te berekenen (HARo-risico-correctie op `n_calc`).
- Het hoogstratum wordt volledig bepaald door `fout_hoog` en `waarde_hoog`, onafhankelijk van de `materialiteit`-kolom.
- In `app.py`: de helptekst zegt "Totale materialiteit voor dit stratum. Opgevat als fractie als ≤ 1 (bijv. 0,01) anders als bedrag in euro's (bijv. 75.000)." — geldt voor zowel de plannings- als evaluatietab.

## Optionele kolommen in de invoer DataFrames

Beide functies vullen ontbrekende kolommen automatisch aan met standaardwaarden **vóór** de validatie, zodat de validatie altijd op volledige data werkt. De check `if kolom not in steekproeven.columns` triggert alleen als de kolom echt afwezig is — aanwezige kolommen met `None`/NaN worden nog steeds geweigerd.

**plan_stratified — verplicht:** `naam`, `waarde_laag`

**plan_stratified — optioneel (standaardwaarden):**

| Kolom                  | Standaard |
|------------------------|-----------|
| `verwachte_foutfractie`| `0.001`   |
| `ihr`                  | `"H"`     |
| `ibr`                  | `"H"`     |
| `car`                  | `"H"`     |
| `waarde_hoog`          | `0.0`     |
| `fout_hoog`            | `0.0`     |
| `materialiteit`        | `0.01`    |
| `kosten`               | `1.0`     |

**eval_stratified — verplicht:** `naam`, `waarde_laag`, `n_laag`, `k_laag`

**eval_stratified — optioneel (standaardwaarden):**

| Kolom           | Standaard |
|-----------------|-----------|
| `ihr`           | `"H"`     |
| `ibr`           | `"H"`     |
| `car`           | `"H"`     |
| `waarde_hoog`   | `0.0`     |
| `fout_hoog`     | `0.0`     |
| `materialiteit` | `0.01`    |

## Kolominhoudvalidatie in plan_stratified en eval_stratified

Beide functies bevatten een uitgebreid validatieblok (in `INVOER_CONTROLE`), dat na de structuurchecks (kolomaanwezigheid, dubbele namen) wordt uitgevoerd. De NaN-check valideert zowel verplichte als optionele kolommen (via `alle_te_valideren_kolommen`).

**Gedeeld (beide functies):**
- NaN/None in alle kolommen (inclusief tekstkolommen `naam`, `ihr`, `ibr`, `car`) → `ValueError`
- Lege of whitespace-only `naam` → `ValueError`
- Niet-numeriek dtype voor numerieke kolommen → `ValueError`
- `waarde_laag` < 0 → `ValueError`
- `waarde_hoog` < 0 → `ValueError`
- `fout_hoog` < 0 → `ValueError`
- `fout_hoog` > `waarde_hoog` → `ValueError`
- `materialiteit`-kolom niet in (0, 1) → `ValueError`
- `ihr`, `ibr`, `car` niet in {"H", "M", "L"} → `ValueError`
- Granulariteit te laag voor kleinste stratum (FFT-methoden): `dx = totaal_waarde_laag / granulariteit >= min_waarde_laag` → `ValueError` met minimaal benodigde granulariteit. Monte Carlo is vrijgesteld (gebruikt geen vast rooster).

**Alleen plan_stratified:**
- `verwachte_foutfractie` niet in [0, 1) → `ValueError`
- `kosten` ≤ 0 → `ValueError`
- `granulariteit` moet strikt positief zijn (`> 0`, niet `>= 0`)

**Alleen eval_stratified:**
- `n_laag` < 0 → `ValueError`
- `n_laag` geen geheel getal → `ValueError`
- `k_laag` < 0 → `ValueError`
- `k_laag` > `n_laag` → `ValueError`

**NaN-tests:**
- Numerieke kolommen: getest met `float("nan")`
- Tekstkolommen (`naam`, `ihr`, `ibr`, `car`): getest met `None`

## Granulariteitscheck (FFT-crashpreventie)

Zowel `plan_stratified` als `eval_stratified` bevatten een check die voorkomt dat het kleinste stratum "tussen wal en schip valt" in het FFT-rooster:

```python
dx = totaal_waarde_laag / granulariteit
if dx >= min_waarde_laag:
    min_benodigde_gran = math.ceil((totaal_waarde_laag / min_waarde_laag) * 10)
    raise ValueError(...)
```

- Geldt alleen voor FFT-methoden (`"FFT samen"`, `"FFT paarsgewijs"`, `"direct"`).
- Monte Carlo is vrijgesteld.
- Verschilt van `valideer_granulariteit.py`: die checkt statistische fijnheid (Beta-verdeling); de crashcheck checkt roosterresolutie.

## Kolomvolgorde in de DataFrames (app.py)

De volgorde weerspiegelt de scope: laagstratum-kolommen links, hoogstratum rechts.

**eval (LEGE_EVAL_DF):**
`naam · waarde_laag · n_laag · k_laag · ihr · ibr · car · materialiteit ‖ waarde_hoog · fout_hoog`

**plan (LEGE_PLAN_DF):**
`naam · waarde_laag · verwachte_foutfractie · ihr · ibr · car · materialiteit · kosten ‖ waarde_hoog · fout_hoog · n_laag · n_laag_extra · n_laag_tot`

## Monetaire materialiteit in de plannings- en evaluatietab

De per-stratum `materialiteit`-kolom accepteert zowel fracties (≤ 1) als geldbedragen (> 1) in **beide** tabs. Omrekening naar fractie vindt plaats in `df_clean` via `.assign(materialiteit=...)` door te delen door `waarde_populatie` als de waarde > 1 is. Dit geldt zowel voor de planningstab als de evaluatietab.

## Invoervalidatie in app.py (UX-niveau)

**Evaluatietab — `on_eval_tabel_change` callback:**
- Ongeldige waarden worden direct **weggepoetst** (cel terugzetten naar vorige geldige waarde) en `eval_error` wordt gezet met een beschrijvende foutmelding.
- Gevalideerde kolommen: `waarde_laag`, `n_laag`, `k_laag`, `waarde_hoog`, `fout_hoog` (niet-parseerbaar of negatief); `materialiteit` (≤ 0, monetary values > 1 worden doorgelaten en pas bij submit omgerekend); cross-constraints `k_laag > n_laag` en `fout_hoog > waarde_hoog` (last-entered wordt weggepoetst).
- Bij wegpoetsen wordt **de vorige geldige waarde hersteld** (niet leeggemaakt): `df` is al een kopie van de vorige opgeslagen staat, dus niet overschrijven = herstellen.
- Sleutel-teller `eval_tabel_key` dwingt Streamlit de data-editor te herladen: `key=f"eval_tabel_{st.session_state.eval_tabel_key}"`.

**Planningstab — `on_plan_tabel_change` callback:**
- Zelfde wegpoets-logica als evaluatietab, met `plan_tabel_key` en `plan_error`.
- Gevalideerde kolommen: `waarde_laag`, `waarde_hoog`, `fout_hoog` (niet-parseerbaar of negatief); `verwachte_foutfractie` (niet in [0, 1)); `kosten` (≤ 0); `materialiteit` (≤ 0); cross-constraint `fout_hoog > waarde_hoog`.
- Submit-validatie (`if start_knop:`) blijft als vangnet (bijv. voor geplakte data die de callback omzeilt).
- Directe aanroepen van `eval_stratified` vanuit `app.py` (buiten `plan_stratified`) zijn afgevangen met `try/except ValueError` + `st.error()` + `st.stop()`.

## Tests draaien

```bash
.venv/bin/python -m pytest
```

191 tests; alle groen, 0 warnings. Testbestanden gebruiken `@pytest.fixture` en `@pytest.mark.parametrize`.

**Testmapstructuur:** `tests/` spiegelt de subpakketten van `auditstat`: `tests/stratified/` voor `auditstat.stratified`, `tests/sso/` voor `auditstat.sso`. Elke (sub)map heeft een `__init__.py`. Testbestanden importeren rechtstreeks uit het volledige pad, bijv. `from auditstat.sso.max_fout_exact_SSO import max_fout_exact_SSO` — niet uit een kale modulenaam.

**Let op bij warnings in tests:** Als een bibliotheekfunctie een `warnings.warn()` afvuurt en een test dat gedrag uitlokt, gebruik dan `pytest.warns(RuntimeWarning, match="...")` om de warning expliciet te verwachten. Zo blijft de testuitvoer schoon en is de intentie gedocumenteerd. Zie `tests/stratified/test_klimheuristiek.py::test_fallback_proxy_symmetrisch` als voorbeeld.

## App starten

```bash
.venv/bin/streamlit run app.py
```

## Nieuwe versie publiceren naar PyPI

```bash
./push_new_version.sh
```

Dit bumpt de patchversie in `pyproject.toml`, maakt een git-tag aan en pusht naar GitHub. De `publish.yml` workflow publiceert vervolgens automatisch naar PyPI via Trusted Publishing.

Voor alleen een CI-run (geen publicatie):

```bash
git add <bestanden>
git commit -am "Omschrijving"
git push origin main   # geen tag → alleen test-workflow
```

## CI/CD

- `.github/workflows/test.yml` — draait bij elke push/PR op main; matrix Python 3.10–3.13; inclusief ruff-linting en pakket-importtest
- `.github/workflows/publish.yml` — triggert op `v*`-tags; publiceert naar PyPI (`pypi.org/p/auditstat`)
