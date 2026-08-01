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
- `raise ValueError` voor gebruikersinvoerfouten: leeg DataFrame, dubbele stratumnamen, verwachte fout te hoog, bekende fout te hoog

**plan_stratified invoer:** De kolom `kosten` is verplicht (relatieve uitvoeringskosten per steek).

**Convolutiemethoden in eval_stratified:** `"FFT paarsgewijs"`, `"FFT samen"`, `"direct"`, `"Monte Carlo"`. Plan gebruikt altijd `"FFT samen"`.

**HARo-risicocombinaties:** 27 mogelijke combinaties van IHR × IBR × CAR (`H`/`M`/`L`), getest via `@pytest.mark.parametrize`.

## Tests draaien

```bash
.venv/bin/python -m pytest
```

70+ tests; alle groen. Testbestanden gebruiken `@pytest.fixture` en `@pytest.mark.parametrize`.

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
