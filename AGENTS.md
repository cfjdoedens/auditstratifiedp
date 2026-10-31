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
    invoer_csv.py                     # CSV-uitwisseling van de SSO-invoer: maak_sso_invoer_csv / lees_sso_invoer_csv
    evalueer_SSO_totaal.py            # Evaluatie van de hele SSO (geen klantkalibratie): evalueer_SSO_totaal
    schema_figuren.py                 # Schema-figuren voor de Theorie (teken_sso_schema, THEORIE_FIGUREN)
    theorie_qmd.py                    # Kleine lezer van theorie.qmd voor de Theorie-tab
    rapport_pdf.py                    # PDF-rapport van een SSO-evaluatie (reportlab): maak_sso_rapport_pdf
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
    test_invoer_csv.py
    test_evalueer_SSO_totaal.py
    test_rapport_pdf.py
theorie.qmd               # Bron van de Theorie-tab (ook los te renderen met Quarto)
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

**Klemming hangt af van absolute N_klant, niet van N_klant t.o.v. n.** Een eerdere formulering ("N_klant is klein t.o.v. de SSO-steekproef n") bleek onjuist: klemming treedt op zodra N_klant *absoluut* te klein is om de steekproefvariabiliteit van de foutfractie bij de klant (die schaalt met 1/N_klant) nog binnen een Beta/Gamma-verdeling te kunnen weergeven bij het gegeven gemiddelde — niet omdat N_klant klein is *relatief aan* n. Tegenvoorbeeld: bij n=50, k=0, N_klant=2000 (N_klant 40× groter dan n) treedt klemming op; bij n=50.000, k=500, N_klant=200 (N_klant 250× kleiner dan n) niet. De rol van n is slechts secundair: een kleine n voegt wat extra posterior-onzekerheid over de SSO-foutkans zelf toe, wat de benodigde compound-variantie beïnvloedt, maar bepaalt niet of klemming optreedt via een "N_klant/n"-verhouding. De waarschuwingstekst in `moment_match_SSO` en de docstring zijn hierop aangepast (spreken nu van "N_klant is te klein" zonder de vergelijking met n).

**Exacte-grens-kalibratie bij klemming in `moment_match_SSO`.** Wanneer het benodigde k_eff negatief zou worden (N_klant te klein, zodat vasthouden aan het juiste gemiddelde sowieso niet meer houdbaar is binnen de Beta/Gamma-familie), wordt niet simpelweg geklemd of vergeleken met een benaderingsformule. In plaats daarvan wordt `k_eff` op 0 gezet (geen fouten specifiek aan de klant toe te rekenen) en wordt `n_eff` zo gekozen dat de 95%-kwantiel van de resulterende Beta(1, n_eff+1)- resp. Gamma(1, schaal=1/n_eff)-verdeling **exact** gelijk is aan de exacte Beta-Binomiale resp. Negatief-Binomiale grens (`_max_fout_exact`, via `scipy.stats.betabinom`/`nbinom`) — "exact" betekent hier: zonder de Beta/Gamma-benadering van `moment_match_SSO`, niet een absolute waarheid los van het onderliggende model (dat zelf nog steunt op een vlakke prior en `N_klant` als exacte eindige populatie) — opgelost via een gesloten vorm in `_kalibreer_k_eff_nul_op_exacte_grens` (voor binomiaal: `Beta(1,b).ppf(zekerheid) = 1-(1-zekerheid)^(1/b)`, op te lossen naar `b`; voor poisson: de Gamma(1,·) is een Exponentiële verdeling, direct naar `n_eff` te herleiden). Dit vervangt een eerdere aanpak (sessie van 2026-10-24) die bij klemming vergeleek met een naïeve-poolingmethode (`n_klant = n·N_klant/(n+N_klant)`) en de conservatiefste van de twee aanhield: die vergelijking bleek overbodig zodra de werkelijke exacte grens zelf als ijkpunt beschikbaar is, en gaf bovendien bij een zeer kleine N_klant (bijv. N_klant=5) nodeloos conservatieve uitkomsten (max_fout95 0,65 vs. de werkelijke 0,20). De nieuwe kalibratie reproduceert de exacte grens tot op numerieke precisie (geverifieerd voor N_klant=100/20/5 bij n=120,k=1: 0,0500/0,1000/0,2000 exact gelijk aan `betabinom`). Bij een extreem kleine N_klant waarbij zelfs de breedst mogelijke Beta-verdeling (n_eff=0, d.w.z. Uniform(0,1)) de exacte grens niet kan bereiken (die kwantiel ligt dan boven de gekozen zekerheid zelf), wordt `n_eff=0` als beste, nog altijd geldige, keuze aangehouden — nog steeds conservatiever dan niets doen, maar kan in dat uiterste randgeval de werkelijke grens net niet volledig dekken (fundamentele beperking van de Beta-familie, niet oplosbaar binnen één verdeling). Het spiegelbeeldige randgeval — de exacte grens is zelf precies 0 (bij een zeer kleine N_klant met k=0, waar zelfs bij 95% zekerheid 0 fouten te verwachten zijn) — gaf aanvankelijk een `ZeroDivisionError` (`log(1-0)=0` in de gesloten-vormformule): een Beta/Gamma-verdeling heeft een strikt positieve drager en kan nooit exact kwantiel 0 weergeven, dus is dit apart afgevangen: `k_eff=0` met `n_eff=n` (niet meer precisie claimen over de klant dan over de SSO-steekproef als geheel), wat altijd minstens zo conservatief is als de exacte grens (die hier het laagst mogelijke getal, 0, is).

**"Exacte grens" is exact voor een bewust worst-case per-post-model, niet voor de werkelijke tainting-praktijk.** `_max_fout_exact` (en dus ook de hele momentmatching-aanpak, die zijn variantie-doel hieruit afleidt) modelleert het aantal fouten bij de klant als `Binomiaal(N_klant, p)`: elke post wordt behandeld als ófwel volledig goed, ófwel volledig fout. In een geldsteekproef is dat niet realistisch — een post kan bijvoorbeeld voor 13% fout zijn (tainting). Dit is echter geen willekeurige vereenvoudiging maar de **maximaal conservatieve**: voor elke grootheid X ∈ [0,1] met gegeven gemiddelde p geldt Var(X) ≤ p(1-p), met gelijkheid alleen in het binaire (Bernoulli) geval. Posten die typisch gedeeltelijk (dus minder extreem) fout zijn, hebben dus minder spreiding dan dit model aanneemt — het model overschat de werkelijke spreiding bij de klant eerder dan dat het 'm onderschat. Alle gebruikersgerichte teksten (de `RuntimeWarning` bij gewone klemming en de `ValueError`-boodschappen bij een blinde vlek) verwijzen daarom niet meer kaal naar "de exacte grens", maar naar "de grens bij de conservatieve aanname dat elke post volledig goed of volledig fout is" — zodat ook in de gebruikersinterface duidelijk is wat "exact" hier wel en niet betekent. De docstrings van `_max_fout_exact` en `moment_match_SSO` leggen de onderliggende Var(X) ≤ p(1-p)-redenering in detail uit.

**Verkennende (niet-geïmplementeerde) numerieke verkenning: hoeveel conservatiever is het binaire model dan een realistischer tainting-model?** Ter illustratie van bovenstaand punt is eenmalig (sessie 2026-10-24, los script, niet in de codebase opgenomen) een alternatief gesimuleerd: in plaats van `X ~ Binomiaal(N_klant, p)` kreeg elke post een eigen Beta-verdeelde taintingfractie met hetzelfde gemiddelde `p` maar een fractie van de maximale variantie `p(1-p)` (parametriseerbaar via een concentratieparameter `c`, met Beta-variantie `p(1-p)/(c+1)`; `p` zelf nog steeds `Beta(k+1, n-k+1)`-verdeeld, als in `_max_fout_exact`). Vergelijking van de 95%-grens tussen het binaire model en dit alternatief (`c=1`: halve variantie; `c=9`: een tiende van de variantie) over een aantal representatieve klemgevallen:

| (n, k, N_klant) | binair model (huidig) | Beta-tainting, halve variantie | Beta-tainting, 1/10 variantie |
|---|---|---|---|
| (50, 0, 2000) | 0,0575 | 0,0573 | 0,0571 |
| (120, 1, 100) | 0,0500 | 0,0453 | 0,0398 |
| (120, 1, 20) | 0,1000 | 0,0641 | 0,0450 |
| (120, 1, 5) | 0,2000 | 0,1160 | 0,0613 |
| (20, 19, 5) | 1,0000 | 1,0000 | 0,9942 |

Bij een ruime `N_klant` (2000) is het verschil verwaarloosbaar — de grens wordt daar vooral bepaald door de posterior-onzekerheid over de SSO-brede foutkans `p` zelf, niet door de spreidingsaanname per post. Naarmate `N_klant` kleiner wordt (100 → 20 → 5, bij gelijke n,k) loopt het verschil op tot een factor ~2 à 3 (bijv. bij N_klant=5: 0,20 binair vs. 0,06–0,12 bij realistischere tainting). In het extreme randgeval waarin de SSO-brede foutkans zelf al zeer hoog is (n=20,k=19,N_klant=5) verzadigen beide modellen bijna tot 1,0 en maakt de aanname nauwelijks verschil. Conclusie: het binaire model is vooral (onnodig) conservatief precies in de kleine-`N_klant`-klemgevallen waarin het al wordt ingezet — met mogelijk aanzienlijke ruimte voor verscherping bij een op data gebaseerd tainting-model — maar dit is een illustratieve, niet op echte tainting-data gekalibreerde verkenning, geen uitgewerkt of geïmplementeerd alternatief. Geen actie ondernomen; puur gedocumenteerd als achtergrond mocht dit later relevant worden.

**Volledige blinde vlek bij `exact_doel = 0`: berekening geweigerd (ValueError), niet alleen een waarschuwing.** Dit randgeval (`exact_doel <= 0`, d.w.z. P(0 fouten bij de klant) ≥ 95%) is kwalitatief anders dan het "gewone" klemgeval: géén continue verdeling kan dan nog een reëel, positief foutscenario weergeven (elk eindig, niet-negatief (n_eff, k_eff)-paar zou vrijwel 0 kans toekennen aan ieder foutscenario, terwijl de werkelijke kans op minstens 1 fout — hoe klein ook — altijd positief blijft). Dit is geen gradueel precisieverlies maar een totale blinde vlek. `moment_match_SSO` gooit in dit geval daarom een `ValueError` (in plaats van, zoals aanvankelijk geïmplementeerd, een `RuntimeWarning` met een terugvalresultaat `k_eff=0, n_eff=n`) die aanraadt de posten van dit type bij deze klant rechtstreeks (100%) te controleren in plaats van te extrapoleren — de berekening van de kanskromme wordt dus geweigerd in plaats van stilzwijgend een misleidend geruststellend resultaat te tonen. `bouw_strata_SSO_klant` vangt deze `ValueError` op en gooit 'm opnieuw met de naam van het type post ervoor (`"Type post '<naam>': ..."`), zodat de hele gestratificeerde opbouw voor de klant stopt zodra één type post een volledige blinde vlek heeft — ook als andere typen posten voor diezelfde klant prima gekalibreerd kunnen worden. `app.py` vangt deze net als elke andere `ValueError` uit `evalueer_SSO_klant_gestratificeerd` af via het bestaande `except ValueError` + `st.error()`-patroon in de SSO-tab; geen aparte app.py-wijziging nodig. Het gewone klemgeval (`exact_doel > 0`, waarin de exacte grens zelf wél positief is en exact gereproduceerd wordt) blijft ongewijzigd de mildere `RuntimeWarning` geven. Het omslagpunt (de kleinste N_klant waarbij `exact_doel` niet langer 0 is) is geen vaste grens maar hangt af van `n` en `k` van de SSO-steekproef — in de praktijk typisch een klein getal (bijv. 4–8 in enkele doorgerekende voorbeelden), maar altijd exact te berekenen via `_max_fout_exact`, dus geen losse geconfigureerde drempelwaarde nodig. Getest in `tests/sso/test_moment_match_SSO.py` (`test_geklemd_bij_exacte_grens_nul_geeft_value_error`, `test_geklemd_bij_exacte_grens_nul_poisson_geeft_value_error`, `test_gewoon_klemgeval_geeft_niet_de_100_procent_weigering`) en `tests/sso/test_strata_SSO_klant.py` (`test_volledige_blinde_vlek_wordt_geweigerd_met_naam_van_type_post`, `test_volledige_blinde_vlek_stopt_ook_bij_meerdere_typen_posten`). De zekerheid van de klemkalibratie is sinds 2026-10-31 een parameter (`zekerheid`, standaard 0,95 = `_ZEKERHEID_VOOR_KLEMKALIBRATIE`) van `moment_match_SSO` en `bouw_strata_SSO_klant`; `evalueer_SSO_klant_gestratificeerd` geeft de door de gebruiker gekozen zekerheid door, zodat de kalibratie exact aansluit op dat niveau (voorheen vast 95%, dan conservatief bij een ander niveau: bijv. n=120,k=1,N_klant=20 bij 99%: exact 0,10 vs gekalibreerd-op-95% 0,15; bij 90%: 0,05 vs 0,078). Gevolg: ook de blinde-vlek-weigering (`exact_doel = 0` of `1`) hangt van de gekozen zekerheid af (bijv. N_klant=5 bij n=120,k=1: bij 90% geweigerd, bij 95% niet); de meldingen noemen het werkelijke percentage (`_procent`). `naief_match_SSO` kent de parameter niet. Getest in `tests/sso/test_moment_match_SSO.py` (`test_geklemd_binomiaal_matcht_exacte_grens`, `test_geklemd_binomiaal_matcht_exacte_grens_bij_zeer_kleine_N_klant`, `test_geklemd_poisson_matcht_exacte_grens`, `test_geklemd_binomiaal_is_minstens_zo_conservatief_als_exact`, `test_geklemd_bij_exacte_grens_nul_geeft_value_error`, `test_geklemd_bij_exacte_grens_nul_poisson_geeft_value_error`).

**Omgekeerde klemgeval (hoge SSO-foutfractie) krijgt dezelfde exacte-grens-behandeling, gespiegeld.** Het eerder "simpelweg geklemd op n_eff=k_eff" afgehandelde omgekeerde klemgeval (zeer hoge SSO-foutfractie, k dicht bij n, in combinatie met een kleine N_klant, waarbij het benodigde n_eff kleiner dan k_eff zou zijn) bleek in alle 71 doorgerekende voorbeelden de werkelijke exacte grens te **onderschatten** (bijv. n=20,k=19,N_klant=5: geklemd mf95=0,98 vs. werkelijk 1,00) — hetzelfde euvel als bij het "gewone" klemgeval vóór de eerdere fix. Opgelost analoog en gespiegeld: `n_eff` wordt op `k_eff` gezet (kleinst mogelijke `beta`-parameter, `n_eff-k_eff+1=1`, binnen `eval_stratified`'s vereiste `n_laag>=k_laag`) en beide opgehoogd zodat de Beta(n_eff+1,1)-kwantiel bij de gekozen zekerheid exact gelijk is aan de werkelijke grens (`_kalibreer_n_eff_gelijk_k_eff_op_exacte_grens`, gesloten vorm: `Beta(a,1).ppf(zekerheid)=zekerheid^(1/a)=doel`, op te lossen naar `a=ln(zekerheid)/ln(doel)`). Als de exacte grens zelf al 1 is (vrijwel zekere 100% fout — het spiegelbeeld van `exact_doel<=0`), kan geen continue verdeling kwantiel 1 exact weergeven en wordt de berekening net als bij de andere blinde vlek geweigerd met een `ValueError` (aanbeveling tot 100%-controle). In het zeldzame geval dat de exacte grens zelf onder de 95%-referentiezekerheid ligt, volstaat de eenvoudige klem (ongewijzigde momentmatching-waarden) al.

**Dit omgekeerde klemgeval komt alleen voor bij het binomiale model.** Bij poisson geldt `n_eff >= k_eff` altijd (gegeven `k <= n` kan het benodigde gemiddelde daar — een rate, niet een begrensde fractie — nooit ver genoeg boven 1 uitkomen om deze klem te bereiken; algebraïsch afgeleid en numeriek geverifieerd over een brede reeks (n,k,N_klant), inclusief de extreme k=n-grens voor kleine n). Die tak behoudt voor poisson daarom de eenvoudige klem (`n_eff=k_eff`) als defensieve, in de praktijk onbereikbare terugval. Getest in `tests/sso/test_moment_match_SSO.py` (`test_k_gelijk_aan_n_is_een_volledige_blinde_vlek`, `test_omgekeerd_klemgeval_matcht_exacte_grens`, `test_omgekeerd_klemgeval_volledige_blinde_vlek_geeft_value_error`, `test_omgekeerd_klemgeval_komt_niet_voor_bij_poisson`).

**Zichtbare melding in de SSO-tab bij terugval (`bouw_strata_SSO_klant` / `app.py`).** De `RuntimeWarning` die `moment_match_SSO` bij klemming afvuurt, kent de naam van het type post niet. `bouw_strata_SSO_klant` vangt die warning per type post op (`warnings.catch_warnings(record=True)` rondom de `moment_match_SSO`-aanroep) en vuurt 'm opnieuw af met de naam ervoor (`"Type post '<naam>': ..."`). `app.py` vangt op zijn beurt *alle* `RuntimeWarning`s op rondom de `evalueer_SSO_klant_gestratificeerd`-aanroep (in `st.session_state.sso_strata_waarschuwingen`, reset bij elke nieuwe berekening/fout) en toont ze, indien niet leeg, als `st.warning(...)` direct onder de resultaattabel (vóór de kanskromme-plot) — alleen voor de typen posten waarvoor daadwerkelijk is teruggevallen, niet voor de rest. De `st.warning(...)` toont uitsluitend de samengevoegde per-type-post-boodschappen (elk al zelf volledig beschrijvend, inclusief de naam van het type post) — géén extra algemene inleidende zin ervoor, want dat gaf dubbele tekst (de inleidende zin herhaalde wat de per-post-boodschap al zei). Getest in `tests/sso/test_strata_SSO_klant.py` (`test_klem_waarschuwing_bevat_naam_van_type_post`, `test_geen_waarschuwing_zonder_klemming`).

**Item-count-gebaseerd SSO-pad: verwijderd (was `max_fout_exact_SSO`, `max_fout_exact_continu_SSO`, `max_fout_benaderd_SSO`, `n_klant_k_klant_SSO`, `plot_kanskromme_SSO`, `plot_max_fout_vergelijking_SSO`, `simuleer_SSO`).** Dit pad behandelde `N_klant` als een exact aantal (gehele) posten bij de klant en modelleerde de voorspellende verdeling van het aantal foute posten daarbinnen als Beta-Binomiaal resp. Negatief-Binomiaal — een attribuutsteekproefmodel. De "exacte" kanskromme toonde daardoor een getrapte verdeling (foutfractie alleen op veelvouden van 1/N_klant), wat gebruikers als verwarrend/artificieel ervoeren. Bij nadere analyse bleek dit géén modelartefact te zijn — voor een attribuutsteekproef bij een exact bekende, eindige populatie ís die discreetheid correct — maar wél een mismatch met de praktijk: SSO-audits in dit project zijn **geldsteekproeven** (monetary unit sampling), niet attribuutsteekproeven op postenaantallen. Het project had hiervoor al het juiste, volledig continue alternatief: `moment_match_SSO` (kalibreert per type post een effectieve (n_eff, k_eff) op gemiddelde + variantie) → `bouw_strata_SSO_klant` (zet post_typen, mét `waarde_laag` in euro's, om in een stratatabel) → `evalueer_SSO_klant_gestratificeerd` (roept `eval_stratified` aan) → `plot_kanskromme` (continue convolutie, geen trapvorm) — dit pad was al aanwezig en in `app.py` geïntegreerd als het "gestratificeerd"-gedeelte van het SSO-tabblad. Het item-count-pad en het bijbehorende "simpele" (n, k, N_klant)-gedeelte van het SSO-tabblad zijn verwijderd; alleen het gestratificeerde, geld-gebaseerde pad resteert als SSO-evaluatiemethode. `test_moment_match_SSO.py` had twee tests die vergeleken met `max_fout_exact_continu_SSO`/`n_klant_k_klant_SSO` (regressietests "nieuwe kalibratie beter dan naïeve pooling") — die zijn geschrapt; de overige (zelfstandige) tests van `moment_match_SSO` blijven.

**Dutch getalnotatie in plots (`auditstat/_formatting.py`):** alle plotfuncties (`plot_kanskromme`) gebruiken de gedeelde helpers `nl_getal`, `nl_getal_variabel` en `nl_tick_formatter` voor komma-decimalen in titels, legenda's en astick-labels, in plaats van losse `.replace(",","X")`-achtige implementaties per bestand.

**Gekleurde subtitel in `plot_kanskromme` (`_gekleurde_subtitel`):** de subtitel onder de hoofdtitel ("blauwe lijn = meest waarschijnlijke fout | rode lijn = maximale fout (...)") wordt niet meer als één `ax.set_title(...)`-string getekend, maar kleurt "blauwe lijn" en "rode lijn" in de bijpassende kleur (`"blue"`/`"red"`, gelijk aan `ax.axvline`'s kleuren), zodat de tekst overeenkomt met wat ze beschrijft. Matplotlib ondersteunt geen kleurwisseling binnen één tekststring — ook mathtext niet, dat kent geen `\color`-commando (`ParseFatalException: Unknown symbol: \color`). Oplossing: de helper `_gekleurde_subtitel(ax, segmenten, y=1.04, fontsize=10)` tekent elk tekststuk (`(tekst, kleur)`-tuples) als los `Text`-object, meet de werkelijk gerenderde breedte via `fig.canvas.draw()` + `fig.canvas.get_renderer()` + `get_window_extent`, en positioneert de stukken na elkaar, gezamenlijk gecentreerd boven de as (conversie tussen display-coördinaten en `ax.transAxes`-fracties via `ax.transAxes.inverted()`). **Volgorde is belangrijk:** deze positionering moet ná alle lay-outbepalende calls staan (`fig.tight_layout()`, `fig.subplots_adjust(top=0.88)`, legenda) — een latere `tight_layout`/`subplots_adjust` zou de al-berekende (in pixels gemeten, naar axes-fracties omgerekende) posities weer verstoren, omdat de pixelbreedtes van elk tekststuk vastliggen maar de axes-breedte dan verandert. Vandaar dat `plot_kanskromme` nu maar één `tight_layout()`-call heeft (vóór de subtitel-positionering), niet meer twee (was: één na de assen-opmaak, één aan het eind na de legenda).

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
- `n_laag` mag niet-geheel zijn (sinds 2026-10-30; `eval_stratified` rekent met Beta-/Gamma-verdelingen, dus een effectieve steekproefomvang is toegestaan)
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

**SSO-tab — herstructureerd (2026-10-24) naar twee tabellen: SSO-brede typen posten + meerdere klanten tegelijk.** Voorheen vroeg de tab per klant om `n`/`k` per type post opnieuw in te vullen. Dat is gesplitst in twee lagen, zodat `n`/`k`/risico/materialiteit (SSO-breed, geldt voor alle klanten) maar één keer worden ingevuld, en alle klanten in één keer berekend worden:
  - **`sso_typen_posten_tabel`** (kolommen `naam, n, k, ihr, ibr, car, materialiteit`): de SSO-brede steekproefgegevens per type post.
  - **`sso_klanten_tabel`** (kolommen `klant, type_post, N_klant, waarde_laag`, lang/tidy-formaat — één rij per klant×type-post-combinatie): alleen wat per klant verschilt. `type_post` is een `SelectboxColumn` waarvan de opties elke render opnieuw worden opgebouwd uit de niet-lege namen in `sso_typen_posten_tabel`.
  - Bij "evalueer alle klanten" worden de rijen van `sso_klanten_tabel` gegroepeerd per `klant`; voor elke klant wordt per rij de bijpassende rij uit `sso_typen_posten_tabel` opgezocht (op `naam == type_post`) en samengevoegd tot een `post_typen`-lijst, waarna `evalueer_SSO_klant_gestratificeerd` **per klant los** wordt aangeroepen in een eigen `try/except ValueError`. Zo blokkeert één mislukte klant (bijv. een volledige blinde vlek bij één type post, zie hierboven) niet de berekening voor de andere klanten.
  - Resultaten komen in `st.session_state.sso_klanten_res: dict[klant_naam, resultaat]` en `sso_klanten_waarschuwingen: dict[klant_naam, list[str]]` (alleen succesvol berekende klanten). De resultaatsectie toont een samenvattingstabel (klant, max fout fractie, max fout euro's) voor alle geslaagde klanten, gevolgd door de detailsectie (metrics, steekproeventabel, `plot_kanskromme`-plot) voor **elke** klant achter elkaar (`for sso_klant_getoond, sso_klant_res in sso_klanten_res.items(): ...`, elk voorafgegaan door een `#### {klantnaam}`-kopje) — niet via een selectbox voor één klant tegelijk (dat was het oorspronkelijke ontwerp bij de herstructurering van 2026-10-24, maar is diezelfde dag vervangen: de gebruiker wilde de resultaten voor alle klanten direct zien zonder eerst te hoeven kiezen).
  - Een lang/tidy-formaat is gekozen voor `sso_klanten_tabel` (in plaats van een brede matrix met kolommen per type post), omdat het aantal typen posten dynamisch is (rijen toevoegen/verwijderen in `sso_typen_posten_tabel`) — `st.data_editor` kan geen kolommen dynamisch bijmaken. Dit sluit ook aan bij het bestaande rij-gebaseerde validatiepatroon van de andere tabbladen.
  - Gecombineerde foutmelding-sleutel `sso_error` (vervangt `sso_strata_error`) bevat zowel validatiefouten (typen-posten-tabel, klanten-tabel: ontbrekend/dubbel `type_post`, niet-gevonden `type_post`-referentie, dubbele `(klant, type_post)`-combinatie) als per-klant berekeningsfouten (`"Klant '{klant}': {foutmelding}"`).

**SSO-tab — gestratificeerde-evaluatie-sectie:** per ingevoerd type post wordt elk veld (`n`, `k`, en optioneel `materialiteit`) **afzonderlijk** gevalideerd en geeft bij een ongeldige waarde een eigen specifieke foutmelding, met zowel de veldnaam als de daadwerkelijk ingevoerde waarde: `"Type post '{naam}': veld '{veld_naam}' (\"{ingevoerde waarde}\") is geen geldig getal."`. Voor elke klantenrij wordt analoog gevalideerd: `N_klant`/`waarde_laag` geven `"Klant '{klant}': type post '{type_post}': veld '{veld_naam}' (\"...\") is geen geldig getal."` — niet één gedeelde melding per rij voor meerdere foute velden tegelijk. Meerdere foutmeldingen worden met `"\n".join(...)` gecombineerd in `st.error()` (niet `" ".join(...)`) zodat ze leesbaar als aparte regels verschijnen. `materialiteit` is optioneel (leeg = standaard 0,01), maar een niet-lege, onparseerbare waarde krijgt ook een eigen foutmelding in plaats van stilzwijgend op de standaardwaarde terug te vallen.

**SSO-tab — valkuil "lege rij" filteren (`naam`/`klant` None/NaN):** bij het filteren van lege rijen uit `sso_typen_posten_tabel`/`sso_klanten_tabel` (vóór validatie) **nooit** filteren op `str(r.get("naam", "")).strip()`. Als een cel leeggemaakt is, levert `r.get("naam")` `None` of `float("nan")` op (de key bestaat immers nog, met een missende waarde) — en `str(None)` / `str(float("nan"))` geven respectievelijk `"None"` en `"nan"`, wat na `.strip()` een niet-lege, "truthy" string is. Zo'n rij werd dus tóch als "heeft een naam" behandeld en kreeg bij validatie absurde foutmeldingen als `Type post 'nan': veld 'n' ("nan") is geen geldig getal.`. Juiste filter controleert expliciet op `None`/`pd.isna(...)` vóórdat er naar string wordt geconverteerd:

```python
sso_typen_posten_rijen = [
    r
    for r in sso_typen_posten_rijen
    if r.get("naam") is not None
    and not pd.isna(r.get("naam"))
    and str(r.get("naam")).strip()
]
```

**SSO-tab — NL-getalnotatie in resultaattabel en invoertabel:**
- De steekproeventabel onder de samenvatting (`naam`, `waarde_laag`, `n_laag`, `k_laag`, uit `sso_klant_res["steekproeven"]` voor de geselecteerde klant) toont alle drie de numerieke kolommen via `_nl(x, 2)` (punt als duizendtalscheiding, komma als decimaalteken, 2 decimalen) in plaats van pandas' standaardweergave. `n_laag`/`k_laag` zijn hier gekalibreerde, continue effectieve waarden uit `moment_match_SSO` (geen gehele tellingen), vandaar ook voor hen 2 decimalen in plaats van een integer-weergave.
- Beide invoertabellen (`sso_typen_posten_tabel`: `n`, `k`, `materialiteit`; `sso_klanten_tabel`: `N_klant`, `waarde_laag`) herformatteren **direct na elke celbewerking** (niet pas bij submit) alle geldige, parseerbare celwaarden naar NL-notatie via `_format_nl_auto` (`n`/`k`/`N_klant` met minimaal 0 decimalen, `waarde_laag`/`materialiteit` met minimaal 2), zodat bijv. `123456` meteen wordt getoond als `123.456`. Lege of onparseerbare cellen blijven ongewijzigd (zodat de gebruiker ze kan corrigeren).

**SSO-tab — twee `on_change`-callbacks, beide met harde rollback net als eval-/planningstab:** `on_sso_typen_posten_tabel_change` (voor `sso_typen_posten_tabel`, velden `n`, `k` verplicht, `materialiteit` optioneel) en `on_sso_klanten_tabel_change` (voor `sso_klanten_tabel`, velden `N_klant`, `waarde_laag`; `type_post` wordt hier alleen bij submit tegen `sso_typen_posten_tabel` gevalideerd, niet al in deze callback, omdat die tabel na het invullen van een klantenrij nog kan wijzigen). Beide lezen de widgetstatus (`edited_rows`/`added_rows`/`deleted_rows`) via hun eigen dynamische key (`sso_typen_posten_tabel_editor_{...}` resp. `sso_klanten_tabel_editor_{...}`), en volgen **hetzelfde strenge patroon als `on_eval_tabel_change`/`on_plan_tabel_change`**: een ongeldige of buiten-bereik waarde (niet-parseerbaar, `n`/`N_klant` ≤ 0, `k` < 0, `waarde_laag` < 0, `materialiteit` ≤ 0, of — alleen in de typen-posten-tabel — de kruiscontrole `k > n`) wordt direct teruggedraaid naar de vorige geldige celwaarde, met een verzamelende foutmelding in `sso_error` (stijl `"Invoerfout: ... bij {rij_naam}."`, net als bij eval/plan — dus niet de uitgebreidere per-veld-foutmelding-stijl van de submit-validatie). Geldige waarden worden meteen naar NL-notatie geherformatteerd. Beide tabel-key-tellers worden **onvoorwaardelijk** aan het eind van hun callback opgehoogd (niet alleen bij een revert, zoals bij eval/plan) om de widget te laten verversen — dit werkte al betrouwbaar voor de pure-herformatteer-variant van deze callback en is behouden.
  - De submit-validatie bij de "evalueer alle klanten"-knop (met de specifieke, veld-voor-veld foutmeldingen) blijft bestaan als vangnet, bijv. voor geplakte data die de `on_change`-callbacks omzeilen — net als bij eval/plan.
  - **Waarom niet `st.form`:** een eerdere fix gebruikte `st.form` om de "een celbewerking wordt pas bij een tweede invoerpoging meegenomen"-race op te lossen (zie git-historie commit "Fix: SSO-tab in st.form..."). Dat loste die race op, maar binnen een form triggert géén enkele widget (behalve de submit-knop) een eigen rerun, dus herformattering/validatie kon daar per definitie pas bij submit zichtbaar worden — niet live tijdens het typen. Omdat `on_change` zelf al bij focusverlies een onafhankelijke rerun triggert (dus los van, en vóór, een eventuele latere klik op de bereken-knop), lost dit dezelfde race op als `st.form` deed, terwijl het wél live herformatteren/valideren mogelijk maakt. `st.form` is daarom losgelaten voor deze tabellen.

## Tests draaien

```bash
.venv/bin/python -m pytest
```

290 tests; alle groen, 0 warnings. Testbestanden gebruiken `@pytest.fixture` en `@pytest.mark.parametrize`.

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

**Huidige PyPI-status:** `auditstat` 0.1.14 is live (gepubliceerd 2026-10-31; bevat o.a. het PDF-rapport, de evaluatie over de hele SSO, de Theorie-tab uit `theorie.qmd` en de doorgegeven `zekerheid` voor de klemkalibratie). Eerder: 0.1.9 (2026-10-23). Tags `v0.1.8` (publish gefaald, nooit gepubliceerd, overruled door 0.1.9) en `v0.1.9` (gepubliceerd na een `gh run rerun` nadat de trusted publisher was geregistreerd) staan beide op GitHub.

## SSO-tab herontwerp (2026-10-27): geleide flow, theorie, methodekeuze, consistentiechecks

Naar aanleiding van een eerste gebruikerssessie met de live Streamlit-app is de SSO-tab verder
herontworpen (bovenop de 2026-10-24-herstructurering naar SSO-brede typen posten + meerdere
klanten tegelijk, zie hierboven). Vijf losse verbeterpunten, alle doorgevoerd:

**Geleide flow (vervangt het "meteen twee tabellen"-scherm als standaardpad).** De SSO-tab
begint nu met (1) een invoerblok voor de SSO-brede totalen (`n`, `k`, `N totaal`, `totale massa`,
`ihr`/`ibr`/`car`, `materialiteit` — losse tekstvelden/selectboxen, geen tabel), gevolgd door (2)
een vereenvoudigde klantentabel (`klant`, `N_klant`, `waarde_laag`, nieuwe sessiestatus
`sso_klanten_totaal_tabel`/`-_key`, eigen `on_sso_klanten_totaal_tabel_change`-callback met
hetzelfde harde-rollback-patroon als de andere SSO-tabellen), en dan (3) een radio "onderscheid
naar typen posten?" (`sso_onderscheid`, "nee"/"ja"). Bij "nee" wordt per klant één synthetisch
type post `"totaal"` gebouwd met de SSO-brede (n,k,risico,materialiteit) en de per-klant
(N_klant, waarde_laag) uit stap 2, en rechtstreeks door de bestaande
`evalueer_SSO_klant_gestratificeerd`-pijplijn gehaald — geen backend-wijziging nodig voor dit
pad. Bij "ja" worden de twee bestaande tabellen (`sso_typen_posten_tabel` met `n`/`k` per type
post, `sso_klanten_tabel` in lang/tidy-formaat) getoond en werkt het precies als vóór dit
herontwerp. `N_totaal` is een nieuw veld (niet expliciet door de gebruiker genoemd in de
oorspronkelijke vraag, maar nodig om de consistentiecheck tussen de klantentotalen en de
SSO-brede populatieomvang mogelijk te maken).

**Theoretische achtergrond.** Nieuw tabblad "Theorie" met vier `st.expander`-secties (two-stage
sampling-idee, de eenvoudige (naïeve) n_klant-poolingformule met randgevallenargument, de
momentmatching-kalibratie met de Var(X)≤p(1-p)-redenering, en een aankondiging van de nog niet
geïmplementeerde FFT-exacte methode), plus korte contextuele `st.expander("Hoe werkt dit?")`-
uitklappers bij de SSO-totalen-sectie in de werktab zelf, die naar het Theorie-tabblad
verwijzen. Uitdrukkelijk **geen** formeel Lean-bewijs in deze slag — alleen de gewone
wiskundige afleiding/redenering in LaTeX (`st.latex`/`st.markdown`); een Lean-bewijs is een
apart, mogelijk toekomstig traject.

**Voorbeeldinvoer.** Omdat `st.data_editor` geen per-cel "grijze suggestiewaarde die je
overtypt" ondersteunt (een cel is leeg of ingevuld, geen placeholder-concept zoals bij
`st.text_input`), zijn alle SSO-invoertabellen vooraf gevuld met realistische voorbeeldcijfers
in plaats van lege rijen, duidelijk gelabeld ("Onderstaande cijfers zijn een voorbeeld —
overschrijf of verwijder de rijen"). De voorbeeldcijfers zijn bewust onderling consistent (zie
hieronder) zodat de consistentiecontrole bij het eerste gebruik al "klopt": SSO-totalen
n=200/k=4/N=5.000/massa=2.500.000; typen posten Emolumenten (n=120,k=1) + Inkoopfacturen
(n=80,k=3) tellen op tot die SSO-totalen; Klant A (N=3.000, €1.500.000) + Klant B (N=2.000,
€1.000.000) tellen op tot de SSO-totalen; en de klant×type-post-opsplitsing telt op tot de
respectievelijke klanttotalen.

**Consistentiechecks.** Niet-blokkerend, puur informatief (`st.info`, geen `st.error`): (a) som
van `N_klant`/`waarde_laag` over de klantentabel (stap 2) wordt vergeleken met de SSO-brede
`N totaal`/`totale massa` (stap 1); (b) bij "ja" (onderscheid naar typen posten): som van
`n`/`k` over de typen-posten-tabel wordt vergeleken met de SSO-brede `n`/`k`, én voor elke klant
wordt de som van `N_klant`/`waarde_laag` over zijn typen-posten-rijen vergeleken met zijn rij in
de klantentotaaltabel. Vergelijkingen gebruiken `_sso_ongeveer_gelijk` (`math.isclose`,
`rel_tol=1e-6`), en slaan een check over (geen melding) zodra een van beide te vergelijken
waarden niet parseerbaar is — dat wordt al apart afgevangen door de bestaande
veld-voor-veld-validatie bij submit. Bewust niet-blokkerend gehouden: dit zijn
totaalconsistenties over meerdere rijen/tabellen heen, geen enkele-celfout, en de gebruiker kan
legitieme redenen hebben om tijdelijk inconsistent te zijn tijdens het invullen.

**Methodekeuze: `kalibratiemethode`-parameter (momentmatching / naïef), FFT-exact nog niet
geïmplementeerd.** `bouw_strata_SSO_klant` en `evalueer_SSO_klant_gestratificeerd` hebben een
nieuwe parameter `kalibratiemethode` (`"momentmatching"` default, of `"naief"`), onafhankelijk
van de bestaande `methode`-parameter (die de *convolutie*-methode kiest: "FFT samen", "FFT
paarsgewijs", "direct", "Monte Carlo" — een andere as). Nieuw: `auditstat/sso/naief_SSO.py` met
`naief_match_SSO(n, k, N_klant)`, een eenvoudige poolingformule (sinds 2026-10-30 onderbouwd als eerste-orde variantie-matching,
zie hieronder): `n_eff = n·N_klant/(n+N_klant)` (parallelformule, analoog aan weerstanden in
parallel), `k_eff = k·n_eff/n` (foutfractie behouden). Eerst gemotiveerd via twee grensgevallen
(N_klant≫n → n_eff→n; N_klant≪n → n_eff→N_klant); daarna afgeleid (zie "Afleiding poolingformule" hieronder) —
een gelijkwaardig alternatief naast `moment_match_SSO` (zie "Labels berekeningsmethode" hieronder). Anders dan
`moment_match_SSO` kent `naief_match_SSO` geen klemming/blinde-vlek-afhandeling (geen
`RuntimeWarning`/`ValueError` bij een extreem kleine `N_klant`) — simpelweg de formule, altijd.
In de app is dit een radio "berekeningsmethode" naast model/zekerheid in het instellingenblok.
De FFT-exacte methode (directe convolutie van de twee-traps posterior, zonder de Beta/Gamma-
benadering van `moment_match_SSO` als tussenstap) is **niet geïmplementeerd** in deze slag —
dit vereist een fundamenteel andere manier van samenvoegen van strata en is bewust als eigen
vervolgtraject/apart ontwerpgesprek afgebakend (zie ook het Theorie-tabblad, dat dit al wel
aankondigt).

Plan vastgelegd in `.posit/assistant/plans/2026-10-27-sso-tab-herontwerp-geleide-flow-theorie-methodekeuze.md`.

## SSO-invoer als CSV (2026-10-29)

De SSO-tab kan de volledige invoer uit één CSV inlezen en weer wegschrijven (uploader + downloadknop onder "invoer als CSV" in de linkerkolom). Logica staat in `auditstat/sso/invoer_csv.py` (puur, getest in `tests/sso/test_invoer_csv.py`); `app.py` bevat alleen de koppeling.

**Formaat (bewuste keuzes na overleg):** één bestand, lang formaat, kolommen `onderdeel;klant;type_post;veld;waarde`, scheidingsteken `;`, getallen in **NL-notatie** zoals de invoervelden ze tonen (opent direct goed in Nederlandse Excel; export is `utf-8-sig`). Onderdelen: `instelling` (model, zekerheid, berekeningsmethode, onderscheid), `totaal` (n, k, N_totaal, massa, ihr, ibr, car, materialiteit), `klant` (N_klant, waarde_laag), `type_post` (n, k, ihr, ibr, car, materialiteit), `klant_type_post` (N_klant, waarde_laag). Alleen invoer wordt geëxporteerd, geen resultaten. De typen-posten-tabellen worden ook geëxporteerd als `onderscheid = nee`.

**Inlezen is strikt en alles-of-niets:** `lees_sso_invoer_csv` verzamelt alle fouten (met regelnummer) en gooit één `ValueError`; de app past dan niets toe en toont de meldingen. Getallen moeten strikte NL-notatie hebben (`_NL_GETAL`): `1234.56` wordt **bewust geweigerd**, omdat `_parse_nl` in de app dat stilzwijgend als 123456 zou lezen (punt = duizendtalscheiding). Verder gecontroleerd: kop, onbekend onderdeel/veld, `klant`/`type_post` verkeerd (niet) ingevuld, dubbele regels, ontbrekende verplichte velden (`materialiteit` mag leeg), H/M/L, model/methode/onderscheid, verwijzing van `klant_type_post` naar een onbekend type post, en `onderscheid = ja` zonder detailtabellen. Ook `,` als scheidingsteken en BOM/Windows-regeleinden worden geaccepteerd. Onderdelen die ontbreken laten de bestaande invoer ongemoeid.

**Callback-patroon (`on_sso_csv_upload`):** draait als `on_change`, dus vóór de rerun, waardoor widget-sleutels (`sso_model`, `sso_totaal_*`, ...) en tabel-state veilig gezet kunnen worden; de tabel-key-tellers worden opgehoogd zodat de data_editors verversen, oude resultaten worden gewist. De uploader krijgt na elke verwerking een nieuwe key (`sso_csv_upload_key`), zodat hetzelfde bestand na een wijziging opnieuw kan worden geüpload. De melding gaat via `st.session_state.sso_csv_melding` en wordt eenmalig getoond. De downloadknop wordt pas ná alle invoerwidgets opgebouwd (kolom `col_sso_inst` wordt opnieuw betreden) zodat hij de actuele waarden kent.

**Voorbeeldbestand en formatuitleg (2026-10-29):** onder de downloadknop in `col_sso_inst` staat een tweede downloadknop "Voorbeeldbestand downloaden (CSV)" (`sso_invoer_voorbeeld.csv`, `onderscheid = ja`), gebouwd met `maak_sso_invoer_csv` uit de voorbeeldconstanten `SSO_TOTAAL_VOORBEELD`, `LEGE_SSO_TYPEN_POSTEN_DF`, `LEGE_SSO_KLANTEN_DF` en `LEGE_SSO_KLANTEN_TOTAAL_DF` -- het voorbeeld blijft dus automatisch gelijk aan de voorbeeldinvoer van de app (geverifieerd: wordt door `lees_sso_invoer_csv` geaccepteerd). Daaronder een `st.expander("Uitleg van het CSV-formaat")` met de onderdelen-tabel en de leesregels. Bij wijziging van het formaat in `invoer_csv.py` moet deze uitlegtekst in `app.py` handmatig mee.

## SSO-PDF-rapport (2026-10-29)

`auditstat/sso/rapport_pdf.py` bevat `maak_sso_rapport_pdf(invoer, resultaten, waarschuwingen=None, datum=None) -> bytes` (A4, NL-notatie, DejaVu Sans uit matplotlib's meegeleverde fonts zodat Unicode werkt). `invoer` heeft dezelfde vorm als de uitvoer van `lees_sso_invoer_csv` (`instellingen`, `totaal`, DataFrames `klanten`/`typen_posten`/`klanten_typen`); bij `onderscheid = ja` worden de typen-posten-tabellen getoond, anders de klantentabel. Inhoud: instellingen, SSO-totalen, invoertabellen, samenvattingstabel per klant, waarschuwingen en per klant metrics, steekproeventabel (effectieve n/k) en kanskromme.

**Keuzes (na overleg):** reportlab (niet matplotlib-PdfPages of fpdf2), invoer + resultaten + kanskrommen (geen methodebeschrijving), logica los testbaar in het pakket en niet in `app.py`. `reportlab` is een **optionele** dependency: extra `pdf` in `[project.optional-dependencies]`, plus in beide dev-secties (met `pypdf` voor de tests, die tekst uit de PDF halen) en in `requirements.txt` (Streamlit Cloud). `app.py` importeert de module in `try/except ImportError` en toont zonder reportlab een hint in plaats van de knop.

**Verouderde module in draaiend proces (2026-10-29):** een lang draaiende Streamlit-sessie kan een oudere `rapport_pdf`-module in het geheugen houden dan de (herlaadde) `app.py` verwacht, wat een technische `TypeError` gaf ("unexpected keyword argument 'methodebeschrijving'"). De knop "PDF-rapport maken" controleert daarom met `inspect.signature` of `maak_sso_rapport_pdf` de parameter `methodebeschrijving` kent; zo niet, dan volgt een duidelijke `st.error` ("herstart de app", lokaal opnieuw starten of op Streamlit Cloud *Reboot app*) en `st.stop()`. Bij een nieuwe parameter in `maak_sso_rapport_pdf` die `app.py` gebruikt, kan deze controle op die parameter worden uitgebreid. Getest met `AppTest` door `maak_sso_rapport_pdf` te vervangen door een variant zonder die parameter (niet in de pytest-suite).

**Colofon (2026-10-29):** onderaan de laatste pagina staat in klein lettertype "Dit rapport is gemaakt met auditstat versie X op d-m-jjjj om uu:mm:ss". De parameter `tijdstip: datetime.datetime | None` (was `datum`; standaard nu) levert datum en tijd. `_auditstat_versie()` leest bij een broncode-checkout (`pyproject.toml` met `name = "auditstat"` naast het pakket) de versie uit dat bestand, omdat de metadata van een editable installatie na een versieverhoging achterloopt (hier gaf `importlib.metadata` nog 0.1.9) en Streamlit Cloud het pakket niet installeert maar uit de repo draait; anders `importlib.metadata`, anders "onbekend".

**Methodebeschrijving (optioneel, 2026-10-29):** `maak_sso_rapport_pdf(..., methodebeschrijving=False)` voegt bij `True` een laatste pagina toe (`_methode_onderdelen`), afgestemd op de instellingen: model (binomiaal/Poisson), kalibratiemethode (momentmatching: samengestelde verdeling, Beta/Gamma-moment-matching, klem- en blinde-vlek-afhandeling bij de gekozen zekerheid; eenvoudig/naïef: poolingformule, geen klem-afhandeling, meestal conservatief maar bij zeer kleine N_klant niet gegarandeerd) en de drie aannames (willekeurige verspreiding/random injectie, vlakke prior, elke post volledig goed of fout met Var(X) ≤ p(1-p)). De tekst staat hard in `rapport_pdf.py`; bij inhoudelijke wijzigingen aan `moment_match_SSO`/`naief_SSO` moet die handmatig mee. In de app: checkbox `sso_rapport_methode` (wist de opgeslagen PDF bij wijziging) boven de knop "PDF-rapport maken".

**App-koppeling:** bij een geslaagde berekening bewaart `app.py` een **momentopname** van de invoer (`st.session_state.sso_rapport_invoer`, kopieën van de tabellen) zodat het rapport bij de resultaten blijft passen als de invoer daarna wordt aangepast. De PDF wordt op verzoek gebouwd (knop "PDF-rapport maken" -> `sso_rapport_pdf` in session state -> `st.download_button`), niet bij elke rerun, omdat het tekenen van de kanskrommen enkele seconden kost. De opgeslagen PDF wordt gewist bij elke nieuwe berekening.

**Valkuil:** de tekstvelden van de SSO-totalen en `sso_zekerheid_text` hebben **geen `value=`** meer; hun standaardwaarden staan in de `session_state`-initialisatie bovenaan `app.py`. Combineren van `value=` met een via de Session State API gezette waarde geeft een Streamlit-logwaarschuwing.

**Getest met `streamlit.testing.v1.AppTest`** (niet in de pytest-suite opgenomen): upload via `at.file_uploader[0].set_value((naam, bytes, mime))` (niet `.upload`), ongeldig bestand laat invoer ongewijzigd, export→import geeft identieke tabellen, en berekening na import slaagt.

## Beveiligingsonderhoud

Bij het eMudhra/emSign CA-incident (gecompromitteerde intermediate CA, risico op MITM voor tools met eigen CA-store zoals `pip`/`uv`/`certifi`) zijn volgende acties ondernomen: `uv self update` (0.11.28 → 0.13.5, bevat afwijzing van de gecompromitteerde keten), en `uv lock --upgrade-package certifi` + `uv sync` om `certifi` in `uv.lock` bij te werken naar 2026.10.19 (was transitief gepind via streamlit/requests op een kwetsbare versie). GitHub Actions-runners zijn niet getroffen (altijd verse images met actuele `pip`/`certifi`). Check bij toekomstige soortgelijke incidenten `uv.lock` op verouderde `certifi`-pins.

## Evaluatie over de hele SSO (2026-10-29)

`auditstat/sso/evalueer_SSO_totaal.py` bevat `evalueer_SSO_totaal(post_typen, model, zekerheid, methode, granulariteit)`: evalueert de **hele SSO** (niet één klant). Er is geen tweede trap en dus geen kalibratie: de SSO-steekproef `(n, k)` is direct een steekproef uit de populatie waarover geoordeeld wordt. Elk type post wordt één stratum met `n_laag = n`, `k_laag = k` en `waarde_laag` = totale massa van dat type post bij de hele SSO; daarna `eval_stratified`. `n` moet geheel zijn (anders `ValueError` met naam type post); `k` mag niet-geheel zijn (gewogen foutaantal bij een geldsteekproef), mits 0 ≤ k ≤ n.

**App:** bij "evalueer alle klanten" wordt dit ook berekend (`st.session_state.sso_totaal_res`, sectie "Hele SSO" onder de klantensamenvatting, met metrics, tabel en kanskromme). Bij onderscheid = nee: één stratum `"totaal"` met de SSO-totalen en `totale massa`; bij ja: één stratum per type post, massa = som van `waarde_laag` over alle klanten. Een fout hierbij komt in `sso_error` als `"SSO totaal: ..."` zonder de klantresultaten te blokkeren.

**PDF-rapport:** `maak_sso_rapport_pdf(..., resultaat_totaal=None)` voegt een sectie "Hele SSO" toe (tabel + kanskromme) direct na de klantensamenvatting. De stale-modulecontrole in `app.py` controleert nu ook op de parameter `resultaat_totaal`.

Getest in `tests/sso/test_evalueer_SSO_totaal.py` en `tests/sso/test_rapport_pdf.py`; app-flow (ja/nee, incl. PDF) met `AppTest` gecontroleerd.

**Samenvatting onder "Resultaat" (2026-10-30, vervangt "Hele SSO als eerste regel" van 2026-10-29):** de tabel toont alleen de klanten; daaronder (app: `st.divider()`, rapport: tweede tabel "Totaal") staan twee regels: "Klanten samen" (`KLANTEN_SAMEN_NAAM`; `klanten_samen(resultaten)` in `evalueer_SSO_totaal.py`: som van `max_fout_convolutie_geld`, fractie = som euro / som `waarde_populatie`, dus gewogen naar de massa van elke klant) en "Hele SSO" (de eigenstandige berekening). Een korte toelichting eronder zegt in eenvoudige taal dat "Klanten samen" de grenzen van de klanten optelt (voorzichtige schatting, de werkelijke gezamenlijke grens is meestal lager) en dat "Hele SSO" een aparte berekening is. "Klanten samen" is (nog) niet als klantnaam gereserveerd. Oorspronkelijke bepaling hierover ("Hele SSO" als eerste regel): onder het kopje "Resultaat" (app) staat "Hele SSO" als eerste regel van de samenvattingstabel, gevolgd door de klanten; in het PDF-rapport geldt hetzelfde voor de tabel onder het kopje "Resultaat" (voorheen "Resultaat per klant"). De regel verschijnt alleen als `sso_totaal_res`/`resultaat_totaal` beschikbaar is. De naam "Hele SSO" (`HELE_SSO_NAAM` in `evalueer_SSO_totaal.py`, hoofdletterongevoelig via `is_gereserveerde_klantnaam`) is daarom **verboden als klantnaam**: geweigerd bij CSV-import (`lees_sso_invoer_csv`, test `test_klantnaam_hele_sso_is_gereserveerd`), teruggedraaid in de twee klantentabel-callbacks en geweigerd bij submit-validatie (beide onderscheid-paden).

**`sso_error` wordt na de berekening getoond (2026-10-29):** het `st.error(sso_error)`-blok staat direct vóór de resultaatsectie, ná het `if sso_bereken:`-blok. Daarvoor stond het erboven, waardoor fouten van de berekeningsknop pas bij de volgende interactie zichtbaar werden (met AppTest aangetoond).

**Imports in `app.py` zijn robuust tegen verouderde modules (2026-10-29):** alle `auditstat`-imports staan in een `for _poging in (1, 2)`-lus. Bij een `ImportError` (typisch: een langlopend proces, bijv. Streamlit Cloud na een push, houdt een oudere `auditstat`-module in het geheugen) worden alle `auditstat*`-modules uit `sys.modules` gehaald en opnieuw geladen (zelfherstel). Lukt het dan nog niet, dan toont de app een duidelijke `st.error` met herstartinstructie plus de technische melding, en `st.stop()`. De optionele `rapport_pdf`-import vangt alleen een ontbrekende `reportlab` af (`e.name`); een andere `ImportError` gaat naar de herstartlogica. Met `AppTest` geverifieerd (zelfherstel en harde melding), niet in de pytest-suite. Nieuwe `auditstat`-imports in `app.py` horen in deze lus.

**Prestaties PDF-rapport (2026-10-29):** de bouwtijd wordt gedomineerd door het tekenen van de kanskrommen (~0,3 s per figuur op Linux, op een trage Windows-omgeving merkbaar langer; bij veel klanten loopt het op). Maatregelen: (1) `_gekleurde_subtitel` in `plot_kanskromme.py` deed twee overbodige `fig.canvas.draw()`-aanroepen (tekstbreedtes meten kan met `get_window_extent(renderer=...)` zonder tekenen); verwijderd, afbeelding pixel-identiek (md5 vergeleken), ~35% sneller, ook voor de plots in de app. (2) `maak_sso_rapport_pdf(..., voortgang=None)` roept `voortgang(fractie, tekst)` aan voor/na elke kanskromme; de app toont daarmee een `st.progress`-balk (houdt ook de verbinding actief, relevant achter proxies). De stale-modulecontrole in `app.py` controleert nu ook op de parameter `voortgang`. Dpi verlagen of `bbox_inches="tight"` weglaten bleek nauwelijks te schelen (~10%).

## Werkwijze: wijzigingen van de gebruiker (2026-10-30)

De gebruiker werkt nooit tegelijk met de assistent aan het project: als er wijzigingen in de werkmap staan die niet van de assistent komen, zijn ze **afgerond en bedoeld**. Dat is anders dan bij een team dat via internet aan één project werkt, dus geen voorzichtigheid met `git add` nodig.

- **Begin van elke taak:** draai `git status` en `git diff` (en lees betrokken bestanden opnieuw), want de assistent krijgt geen melding van wijzigingen en onthoudt anders verouderde inhoud uit eerdere leesacties.
- **Behandel zulke wijzigingen als uitgangspunt:** niet terugdraaien, niet overschrijven, en bij een nieuwe aanpassing van een bestand uitgaan van de actuele inhoud (niet van het geheugen). Een mislukte exacte-tekstvervanging (`edit`/`assert old in s`) betekent vrijwel altijd dat de gebruiker die plek heeft gewijzigd: opnieuw lezen, niet forceren.
- **Commits:** `git add -A` is toegestaan; de wijzigingen van de gebruiker mogen in dezelfde commit mee. Noem ze kort in het commitbericht of de samenvatting als ze inhoudelijk zijn, en draai de tests als ze code raken.
- **Bestaande bestanden nooit in hun geheel overschrijven** op basis van een eerder gelezen versie; altijd gerichte bewerkingen op de actuele inhoud.

**Labels berekeningsmethode (2026-10-30, door de gebruiker bepaald):** de radio "berekeningsmethode" in de SSO-tab toont `["naief", "momentmatching"]` in die volgorde (bewust omgedraaid; de eerste optie is de app-standaard, dus de app start nu met `naief`, terwijl de Python-functies `momentmatching` als default houden) met de labels "gebruik afgeleide n_klant en k_klant, conservatief" resp. "idem, maar scherper en complexer". De naïeve methode wordt dus niet meer als "ter vergelijking"/"niet aanbevolen" gepresenteerd, en momentmatching niet meer als "de aanbevolen methode": beide zijn gelijkwaardige keuzes (eenvoudig en meestal conservatief vs. scherper en complexer). Bewust niet te sterk geformuleerd om de gebruiker niet te belasten: "conservatief" is een waarneming (in 60 doorgerekende (n,k,N_klant,model)-combinaties was de naïeve grens altijd ≥ momentmatching), geen bewijs; bij een zeer kleine N_klant (bijv. 1) kan de naïeve grens te laag uitvallen. Dezelfde toon staat in het Theorie-tabblad (onderdelen 2 en 3), in de PDF-methodebeschrijving (`_methode_onderdelen`, `_KALIBRATIE_LABELS`) en in de docstring van `naief_match_SSO`; bij een wijziging van de labels in de radio moeten die mee.

**Geen afronding van `n_eff` meer (2026-10-30).** `bouw_strata_SSO_klant` rondde `n_eff` af op een geheel `n_laag` (eis van `eval_stratified`) terwijl `k_eff` ongeafgerond bleef. Dat verstoorde de gekalibreerde variantie en het gemiddelde: met de CSV `SSO2.csv` (n=108, k=2, N_klant 84.000-147.000) lag "Klanten samen" (0,044248) onder "Hele SSO" (0,044280), terwijl de som van de klantgrenzen daar niet onder hoort te liggen. Nu accepteert `eval_stratified` een niet-geheel `n_laag` (alleen de gehele-getallencontrole is vervallen; `n_laag >= 0` en `k_laag <= n_laag` blijven) en geeft `bouw_strata_SSO_klant` `n_laag = max(n_eff, k_eff)` ongeafgerond door. Resultaat: Klanten samen 0,044283 (momentmatching) / 0,044292 (naief) >= Hele SSO 0,044280. In `evalueer_SSO_totaal` blijft `n` wel geheel (echte steekproefomvang).

**Afleiding poolingformule (2026-10-30, Theorie-onderdeel 2).** De naïeve formule `n_eff = n·N_klant/(n+N_klant)` is geen kale heuristiek meer maar een eerste-orde variantie-matching: de posterior-variantie van de SSO-foutkans (`≈ p(1-p)/n`) en de steekproefvariantie van de klant rond die foutkans (`≈ p(1-p)/N_klant`) tellen op (wet van de totale variantie); gelijkstellen aan `p(1-p)/n_eff` geeft de formule. Voor poisson (`p/n`, `p/N_klant`) komt in eerste orde dezelfde formule uit (niet "exact" dezelfde: de `+2` van de Beta-variantie is weggelaten). Evaluatie voor k=0, 95%, poisson, vlakke prior: benaderd `≈ 3/n + 3/N_klant`; exact (negatief-binomiaal/geometrisch) uit `X+1 ≥ ln(0,05)/ln(N/(n+N))`, `p = X/N`. De vereenvoudiging `≈ 3/n − 1/N` geldt **alleen voor N_klant ≫ n** (afrondingsonzekerheid ~1/N; voor kleine N kan ze negatief worden): n=100,N=10: benaderd 0,330 vs exact 0,100; n=100,N=300: 0,040 vs 0,033; n=100,N=1000: 0,033 vs 0,031; n=1000,N=100: 0,033 vs 0,010. Dit is een rekenvoorbeeld voor k=0, geen bewijs voor alle k. Teksten die hierop zijn afgestemd: Theorie-onderdeel 2 (`app.py`), `_methode_onderdelen` in `rapport_pdf.py`, docstrings van `naief_SSO.py` en `strata_SSO_klant.py`.

## Theorie-tab uit `theorie.qmd` (2026-10-31)

De tekst van het Theorie-tabblad staat niet meer in `app.py` maar in `theorie.qmd` (repo-root), zodat de gebruiker die als gewoon Quarto-document kan bewerken. `quarto render theorie.qmd` geeft een zelfstandige HTML (figuren via `{python}`-blokken); het pre-commit-hook rendert dit bestand niet. De app leest het met `auditstat/sso/theorie_qmd.py` (geen Quarto op de server nodig): titel uit de YAML-kop, tekst vóór de eerste `## ` is de inleiding (`st.caption`), elke `## `-kop is een uitklapper (de eerste open), overige tekst gaat naar `st.markdown` (`$...$` en `$$...$$` werken; `st.latex` is dus niet meer nodig). HTML-commentaar wordt genegeerd. Een `{python}`-blok met `#| label: fig-...` is een figuur: de tekenfunctie komt uit `THEORIE_FIGUREN` in `auditstat/sso/schema_figuren.py` (de figuurcode is daarheen verplaatst uit `app.py`), het bijschrift staat op **één regel** in `#| fig-cap: "..."` (geen dubbele aanhalingstekens erin). Een nieuw figuur vraagt dus: tekenfunctie + regel in `THEORIE_FIGUREN` + blok in het qmd. Getest in `tests/sso/test_theorie_qmd.py`. `theorie.qmd` moet bij de app staan (Streamlit Cloud draait vanuit de repo), niet in het PyPI-pakket.
