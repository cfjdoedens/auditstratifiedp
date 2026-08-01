# auditstratified — projectgeheugen

## Wat is dit project?

Python-pakket voor gestratificeerde steekproefaudits conform het Handboek Auditing Rijksoverheid (HARo). Drie hoofdfuncties:

- `plan_stratified()` — berekent optimale steekproefomvang per stratum
- `eval_stratified()` — combineert steekproeven via convolutie tot één gezamenlijke foutschatting
- `plot_kanskromme()` — visualiseert de resulterende kansverdeling

Live Streamlit-app: https://auditstratifiedp-ko3vmnx8pfjkuf8xacb8kx.streamlit.app/

## Bestandsstructuur

```
auditstratified/
  eval_stratified.py      # Convolutie-evaluatie (FFT, Monte Carlo, direct)
  plan_stratified.py      # Heuvelklimalgoritme voor steekproefplanning
  plot_kanskromme.py      # Visualisatie
  utils.py                # HARo-helpers: haro_nog_nodige_zekerheid, drawsneeded, foutloze_posten_equivalent
  valideer_granulariteit.py
tests/
  test_eval.py
  test_plan.py
  test_utils.py
  test_klimheuristiek.py
  test_valideer_granulariteit.py
app.py                    # Streamlit-applicatie
ruff.toml                 # Linting-configuratie
pyproject.toml            # Pakketconfiguratie (versie 0.1.x)
push_new_version.sh       # Script: bumpt versie, commit, tag, push naar GitHub + PyPI
```

## Ontwerpkeuzes

**assert vs. ValueError:**
- `assert` voor API-contractchecks (verkeerde aanroep door programmeur): `model`, `zekerheid`, `methode`, `granulariteit`, `start`, `vergelijk`, type van `steekproeven`, aanwezigheid van vereiste kolommen
- `raise ValueError` voor gebruikersinvoerfouten: leeg DataFrame, dubbele stratumnamen, verwachte fout te hoog, bekende fout te hoog, ongeldige kolominhoud

**plan_stratified invoer:** De kolom `kosten` is verplicht (relatieve uitvoeringskosten per steek). Wordt echter in `plan_stratified_basis` automatisch op 1.0 gezet als hij ontbreekt — dit is bedoeld voor aanroep vanuit `analyseer_klimheuristiek`.

**Convolutiemethoden in eval_stratified:** `"FFT paarsgewijs"`, `"FFT samen"`, `"direct"`, `"Monte Carlo"`. Plan gebruikt altijd `"FFT samen"`.

**HARo-risicocombinaties:** 27 mogelijke combinaties van IHR × IBR × CAR (`H`/`M`/`L`), getest via `@pytest.mark.parametrize`.

**Scope van de `materialiteit`-kolom in het DataFrame:**
- Slaat uitsluitend op het **laagstratum** — zowel in `plan_stratified` als in `eval_stratified`.
- In `plan_stratified`: gebruikt als `allowed_defect_rate` in `drawsneeded()` voor de basissteekproefomvang.
- In `eval_stratified`: gebruikt in `foutloze_posten_equivalent()` om `extra_foutloze_posten` te berekenen (HARo-risico-correctie op `n_calc`).
- Het hoogstratum wordt volledig bepaald door `fout_hoog` en `waarde_hoog`, onafhankelijk van de `materialiteit`-kolom.
- In `app.py`: de helptekst zegt "Materialiteit voor het laagstratum." (was eerder foutief "laag + hoog samen").

## Kolominhoudvalidatie in plan_stratified en eval_stratified

Beide functies bevatten nu een uitgebreid validatieblok (in `INVOER_CONTROLE`), dat na de structuurchecks (kolomaanwezigheid, dubbele namen) wordt uitgevoerd:

**Gedeeld (beide functies):**
- NaN in alle vereiste kolommen → `ValueError`
- Lege of whitespace-only `naam` → `ValueError`
- Niet-numeriek dtype voor numerieke kolommen → `ValueError`
- `waarde_laag` < 0 → `ValueError`
- `waarde_hoog` < 0 → `ValueError`
- `fout_hoog` < 0 → `ValueError`
- `fout_hoog` > `waarde_hoog` → `ValueError`
- `materialiteit`-kolom niet in (0, 1) → `ValueError`
- `ihr`, `ibr`, `car` niet in {"H", "M", "L"} → `ValueError`

**Alleen plan_stratified:**
- `verwachte_foutfractie` niet in [0, 1) → `ValueError`
- `kosten` ≤ 0 → `ValueError`

**Alleen eval_stratified:**
- `n_laag` < 0 → `ValueError`
- `n_laag` geen geheel getal → `ValueError`
- `k_laag` < 0 → `ValueError`
- `k_laag` > `n_laag` → `ValueError`

**NaN-tests:**
- Numerieke kolommen: getest met `float("nan")`
- Tekstkolommen (`naam`, `ihr`, `ibr`, `car`): getest met `None`

**Bugfixes bij implementatie:**
- `ihr` ontbrak in `vereiste_kolommen` van `plan_stratified` — hersteld.
- De `kosten`-defaultregel (`if "kosten" not in strata.columns: strata["kosten"] = 1.0`) was per ongeluk verwijderd uit `plan_stratified_basis` — hersteld.

## Kolomvolgorde in de DataFrames (app.py)

De volgorde weerspiegelt de scope: laagstratum-kolommen links, hoogstratum rechts.

**eval (LEGE_EVAL_DF):**
`naam · waarde_laag · n_laag · k_laag · ihr · ibr · car · materialiteit ‖ waarde_hoog · fout_hoog`

**plan (LEGE_PLAN_DF):**
`naam · waarde_laag · verwachte_foutfractie · ihr · ibr · car · materialiteit · kosten ‖ waarde_hoog · fout_hoog · n_laag · n_laag_extra · n_laag_tot`

## Monetaire materialiteit in de planningstab

De per-stratum `materialiteit`-kolom accepteert zowel fracties (≤ 1) als geldbedragen (> 1), conform dezelfde conventie als de globale materialiteitsparameter. Omrekening naar fractie vindt plaats in `df_clean` via `.assign(materialiteit=...)` door te delen door `waarde_populatie` als de waarde > 1 is.

Voor de **evaluatietab** zijn alleen fracties bedoeld — geen monetaire omrekening.

## Invoervalidatie in app.py (UX-niveau)

**Evaluatietab — `on_eval_tabel_change` callback:**
- Ongeldige waarden worden direct **weggepoetst** (cel teruggezet naar `""`) en `eval_error` wordt gezet.
- Gevalideerde kolommen: `waarde_laag`, `n_laag`, `k_laag`, `waarde_hoog`, `fout_hoog` (negatief); `materialiteit` (buiten (0, 1)); `k_laag > n_laag`; `fout_hoog > waarde_hoog`.
- Om de Streamlit data-editor te dwingen de gecorrigeerde data te tonen, wordt een **sleutel-teller** gebruikt: `eval_tabel_key` in `session_state`. Bij elke wegpoets wordt deze verhoogd; de data-editor gebruikt `key=f"eval_tabel_{st.session_state.eval_tabel_key}"` en de callback leest `st.session_state[f"eval_tabel_{st.session_state.eval_tabel_key}"]`.

**Planningstab — `if start_knop:` block:**
- Inline `st.error()` + `st.stop()` na het bouwen van `df_clean` (niet via geneste helperfunctie, want `st.stop()` propageert niet betrouwbaar vanuit geneste functies).
- Gevalideerde kolommen: `waarde_laag`, `verwachte_foutfractie`, `kosten`, `waarde_hoog`, `fout_hoog`, `materialiteit` (na omrekening).

## Tests draaien

```bash
.venv/bin/python -m pytest
```

153 tests; alle groen. Testbestanden gebruiken `@pytest.fixture` en `@pytest.mark.parametrize`.

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
- `.github/workflows/publish.yml` — triggert op `v*`-tags; publiceert naar PyPI
