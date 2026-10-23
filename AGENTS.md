# auditstat — projectgeheugen

## Wat is dit project?

Python-pakket voor statistische auditmethoden voor de Rijksoverheid. Overkoepelend pakket `auditstat` met subpakketten:

- `auditstat.stratified` — gestratificeerde steekproefaudits (HARo-compatibel)
  - `plan_stratified()` — berekent optimale steekproefomvang per stratum
  - `eval_stratified()` — combineert steekproeven via convolutie tot één gezamenlijke foutschatting
  - `plot_kanskromme()` — visualiseert de resulterende kansverdeling
- `auditstat.sso` — steekproefaudits voor shared service organisaties (SSO's); evalueert gestratificeerd (één stratum per type post) een klant op basis van per-type-post SSO-steekproeven, volledig continu en in euro's (`evalueer_SSO_klant_gestratificeerd` → `eval_stratified`/`plot_kanskromme` uit `auditstat.stratified`). Zie "Item-count-gebaseerd SSO-pad: verwijderd" hieronder voor de achtergrond.

Live Streamlit-app: https://auditstratifiedp-ko3vmnx8pfjkuf8xacb8kx.streamlit.app/

## Bestandsstructuur

```
auditstat/
  __init__.py
  _formatting.py           # Gedeelde NL-getalnotatie voor alle plots: nl_getal, nl_getal_variabel, nl_tick_formatter
  stratified/               # Was: auditstratified/
    __init__.py
    eval_stratified.py      # Convolutie-evaluatie (FFT, Monte Carlo, direct)
    plan_stratified.py      # Heuvelklimalgoritme voor steekproefplanning
    plot_kanskromme.py      # Visualisatie
    utils.py                # HARo-helpers: haro_nog_nodige_zekerheid, drawsneeded, foutloze_posten_equivalent
    valideer_granulariteit.py
    analyseer_klimheuristiek.py
  sso/
    __init__.py
    moment_match_SSO.py              # Kalibreert (n_eff, k_eff) per type post op moment-matching (gemiddelde + variantie)
    strata_SSO_klant.py              # bouw_strata_SSO_klant: zet post_typen (per type post: n, k, N_klant, waarde_laag) om in een stratatabel
    evalueer_SSO_klant_gestratificeerd.py  # Roept bouw_strata_SSO_klant + eval_stratified aan
    script_SSO.py                     # Demonstratiescript
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
    test_moment_match_SSO.py
    test_strata_SSO_klant.py
    test_evalueer_SSO_klant_gestratificeerd.py
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

**Heterogeen SSO-model: verwijderd (was `max_fout_heterogeen_SSO`).** Dit model veronderstelde dat klant X een eigen, onafhankelijke foutfractie heeft (flat prior), los van de rest van de SSO-populatie, en marginaliseerde de posterior over welke van de `n` SSO-breed getrokken posten (`n_X ~ Binomial(n, f)`) bij klant X hoorden — op basis van alleen het SSO-brede totaal `(n, k)` en het relatieve aandeel `f`, zonder de opsplitsing per klant te kennen. Bij nadere analyse bleek deze aanname onrealistisch: de auditor moet elke gestoken post in de administratie van de betreffende klant controleren en kent dus altijd welke posten (en fouten) bij klant X horen (`n_X`, `k_X`). Zodra die opsplitsing bekend is, is conditioneren op `n_X` de statistisch juiste aanpak — simpelweg `Beta(k_X+1, n_X−k_X+1)` op de klanteigen deelsteekproef — en is marginaliseren over een onbekende verdeling nodeloos conservatief (in een rekenvoorbeeld: grens 0,21 bij direct conditioneren vs. 0,40 bij marginaliseren, bij n=100, k=5, f=0,2). Het model, de bijbehorende plotfunctie `plot_posterior_heterogeen_SSO`, de tests en de app-integratie zijn verwijderd. Mocht een vergelijkbare behoefte terugkomen, dan is dat waarschijnlijk alleen zinvol voor **planning vooraf** (vóór de steekproeftrekking, wanneer `n_X` nog niet gerealiseerd is en alleen `f` bekend is) — niet voor evaluatie achteraf.

**Item-count-gebaseerd SSO-pad: verwijderd (was `max_fout_exact_SSO`, `max_fout_exact_continu_SSO`, `max_fout_benaderd_SSO`, `n_klant_k_klant_SSO`, `plot_kanskromme_SSO`, `plot_max_fout_vergelijking_SSO`, `simuleer_SSO`).** Dit pad behandelde `N_klant` als een exact aantal (gehele) posten bij de klant en modelleerde de voorspellende verdeling van het aantal foute posten daarbinnen als Beta-Binomiaal resp. Negatief-Binomiaal — een attribuutsteekproefmodel. De "exacte" kanskromme toonde daardoor een getrapte verdeling (foutfractie alleen op veelvouden van 1/N_klant), wat gebruikers als verwarrend/artificieel ervoeren. Bij nadere analyse bleek dit géén modelartefact te zijn — voor een attribuutsteekproef bij een exact bekende, eindige populatie ís die discreetheid correct — maar wél een mismatch met de praktijk: SSO-audits in dit project zijn **geldsteekproeven** (monetary unit sampling), niet attribuutsteekproeven op postenaantallen. Het project had hiervoor al het juiste, volledig continue alternatief: `moment_match_SSO` (kalibreert per type post een effectieve (n_eff, k_eff) op gemiddelde + variantie) → `bouw_strata_SSO_klant` (zet post_typen, mét `waarde_laag` in euro's, om in een stratatabel) → `evalueer_SSO_klant_gestratificeerd` (roept `eval_stratified` aan) → `plot_kanskromme` (continue convolutie, geen trapvorm) — dit pad was al aanwezig en in `app.py` geïntegreerd als het "gestratificeerd"-gedeelte van het SSO-tabblad. Het item-count-pad en het bijbehorende "simpele" (n, k, N_klant)-gedeelte van het SSO-tabblad zijn verwijderd; alleen het gestratificeerde, geld-gebaseerde pad resteert als SSO-evaluatiemethode. `test_moment_match_SSO.py` had twee tests die vergeleken met `max_fout_exact_continu_SSO`/`n_klant_k_klant_SSO` (regressietests "nieuwe kalibratie beter dan naïeve pooling") — die zijn geschrapt; de overige (zelfstandige) tests van `moment_match_SSO` blijven.

**Dutch getalnotatie in plots (`auditstat/_formatting.py`):** alle plotfuncties (`plot_kanskromme`) gebruiken de gedeelde helpers `nl_getal`, `nl_getal_variabel` en `nl_tick_formatter` voor komma-decimalen in titels, legenda's en astick-labels, in plaats van losse `.replace(",","X")`-achtige implementaties per bestand.

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

**SSO-tab — gestratificeerde-evaluatie-sectie:** per ingevoerd type post wordt elk veld (`n`, `k`, `N_klant`, `waarde_laag`, en optioneel `materialiteit`) **afzonderlijk** gevalideerd en geeft bij een ongeldige waarde een eigen specifieke foutmelding, met zowel de veldnaam als de daadwerkelijk ingevoerde waarde: `"Type post '{naam}': veld '{veld_naam}' (\"{ingevoerde waarde}\") is geen geldig getal."` — niet één gedeelde melding per rij voor meerdere foute velden tegelijk. Meerdere foutmeldingen worden met `"\n".join(...)` gecombineerd in `st.error()` (niet `" ".join(...)`) zodat ze leesbaar als aparte regels verschijnen. `materialiteit` is optioneel (leeg = standaard 0,01), maar een niet-lege, onparseerbare waarde krijgt ook een eigen foutmelding in plaats van stilzwijgend op de standaardwaarde terug te vallen.

**SSO-tab — valkuil "lege rij" filteren (`naam` None/NaN):** bij het filteren van lege rijen uit `sso_strata_tabel` (vóór validatie) **nooit** filteren op `str(r.get("naam", "")).strip()`. Als een cel leeggemaakt is, levert `r.get("naam")` `None` of `float("nan")` op (de key bestaat immers nog, met een missende waarde) — en `str(None)` / `str(float("nan"))` geven respectievelijk `"None"` en `"nan"`, wat na `.strip()` een niet-lege, "truthy" string is. Zo'n rij werd dus tóch als "heeft een naam" behandeld en kreeg bij validatie absurde foutmeldingen als `Type post 'nan': veld 'n' ("nan") is geen geldig getal.`. Juiste filter controleert expliciet op `None`/`pd.isna(...)` vóórdat er naar string wordt geconverteerd:

```python
sso_strata_rijen = [
    r
    for r in sso_strata_rijen
    if r.get("naam") is not None
    and not pd.isna(r.get("naam"))
    and str(r.get("naam")).strip()
]
```

**SSO-tab — `data_editor` in een `st.form`:** de tabel met typen posten, de instellingen (`model`, `zekerheid`) en de bereken-knop staan sinds kort samen in `st.form("sso_strata_form")`, met de knop als `st.form_submit_button` in plaats van `st.button`. Reden: zonder form werd een celbewerking (bijv. in `k`) soms pas bij een **tweede** invoerpoging meegenomen. `st.data_editor` stuurt een celwijziging pas naar de server bij focusverlies (blur); een knopklik kan al een rerun triggeren vóórdat die blur-melding is verwerkt, waardoor de net getypte waarde de eerste keer wordt gemist. `st.form` bundelt alle widgetinteracties binnen de form en stuurt ze pas gezamenlijk door bij submit, wat deze race condition oplost. Dit is een ander patroon dan de `on_change`-aanpak van de eval-/planningstab (die juist meteen bij elke celbewerking valideert en wegpoetst); de SSO-tab valideert alleen bij submit, dus `st.form` volstaat hier zonder extra `on_change`-logica.

## Tests draaien

```bash
.venv/bin/python -m pytest
```

205 tests; alle groen, 0 warnings. Testbestanden gebruiken `@pytest.fixture` en `@pytest.mark.parametrize`.

**Testmapstructuur:** `tests/` spiegelt de subpakketten van `auditstat`: `tests/stratified/` voor `auditstat.stratified`, `tests/sso/` voor `auditstat.sso`. Elke (sub)map heeft een `__init__.py`. Testbestanden importeren rechtstreeks uit het volledige pad, bijv. `from auditstat.sso.moment_match_SSO import moment_match_SSO` — niet uit een kale modulenaam.

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
- `.github/workflows/python-tests.yml` — aparte "Python tests"-workflow, cross-platform matrix (ubuntu/windows/macos); installeert met `pip install -e ".[dev]"` (net als `test.yml`)
- `.github/workflows/publish.yml` — triggert op `v*`-tags; draait eerst de testmatrix, publiceert daarna naar PyPI (`pypi.org/p/auditstat`) via Trusted Publishing (OIDC, geen API-token)

**Valkuil: dev-dependencies op twee plekken in `pyproject.toml`.** `[dependency-groups] dev` (gebruikt door lokale `uv sync`) en `[project.optional-dependencies] dev` (gebruikt door CI's `pip install -e ".[dev]"`) moeten **beide** worden bijgewerkt als er een nieuwe dev-dependency wordt toegevoegd. Toen `hypothesis` alleen aan de eerste was toegevoegd en niet aan de tweede, faalden zowel `test.yml` als `publish.yml` met `ModuleNotFoundError: No module named 'hypothesis'` bij het verzamelen van `tests/stratified/test_hypothesis_properties.py`. Fix: voeg de dependency aan beide secties toe.

**Trusted Publishing registreren bij naamswijziging van het pakket.** Na het hernoemen van het PyPI-project (van `auditstratified` naar `auditstat`) moet er handmatig, eenmalig, een nieuwe "pending publisher" worden geregistreerd op https://pypi.org/manage/account/publishing/ (Project Name = `auditstat`, Owner = `cfjdoedens`, Repository = `auditstratifiedp`, Workflow = `publish.yml`, Environment = `pypi`). Zonder dit faalt de publish-stap met `400 ... Non-user identities cannot create new projects`, ook als de testmatrix wel slaagt. Dit is al gedaan voor `auditstat`; alleen relevant bij een volgende naamswijziging.

**Huidige PyPI-status:** `auditstat` 0.1.9 is live (gepubliceerd 2026-10-23). Tags `v0.1.8` (publish gefaald, nooit gepubliceerd, overruled door 0.1.9) en `v0.1.9` (gepubliceerd na een `gh run rerun` nadat de trusted publisher was geregistreerd) staan beide op GitHub.

## Beveiligingsonderhoud

Bij het eMudhra/emSign CA-incident (gecompromitteerde intermediate CA, risico op MITM voor tools met eigen CA-store zoals `pip`/`uv`/`certifi`) zijn volgende acties ondernomen: `uv self update` (0.11.28 → 0.13.5, bevat afwijzing van de gecompromitteerde keten), en `uv lock --upgrade-package certifi` + `uv sync` om `certifi` in `uv.lock` bij te werken naar 2026.10.19 (was transitief gepind via streamlit/requests op een kwetsbare versie). GitHub Actions-runners zijn niet getroffen (altijd verse images met actuele `pip`/`certifi`). Check bij toekomstige soortgelijke incidenten `uv.lock` op verouderde `certifi`-pins.
