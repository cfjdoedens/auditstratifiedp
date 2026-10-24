
# SSO-tab herstructureren: SSO-brede typen posten + meerdere klanten

## Doel

De huidige SSO-tab (`tab_sso` in `app.py`) vraagt per klant opnieuw om `n`/`k`
per type post in te vullen, terwijl die SSO-brede steekproefgegevens voor
alle klanten gelijk zijn. Herstructureer de tab in twee lagen:

1. **Typen posten bij de SSO** (één keer invullen, geldt voor alle klanten):
   `naam`, `n`, `k`, `ihr`, `ibr`, `car`, `materialiteit`.
2. **Klanten** (per klant × type post, wat nog ontbreekt): `klant`,
   `type_post` (verwijst naar een naam uit tabel 1), `N_klant`,
   `waarde_laag`.

Alle klanten worden in één keer berekend; de resultaattabel toont per klant
de maximale fout (fractie en euro's), met een keuzeveld om voor één
specifieke klant de steekproeventabel en kanskromme te tonen.

Gebaseerd op de antwoorden van de gebruiker:
- Alles behalve `N_klant` en `waarde_laag` is SSO-breed (dus ook `ihr`,
  `ibr`, `car`, `materialiteit`).
- Alle klanten tegelijk, niet één klant per keer.

## Datamodel (session state)

Vervangt de huidige `sso_strata_*`-sleutels:

| Nieuwe sleutel | Vervangt | Inhoud |
|---|---|---|
| `sso_typen_posten_tabel` | `sso_strata_tabel` | kolommen `naam, n, k, ihr, ibr, car, materialiteit` |
| `sso_typen_posten_tabel_key` | `sso_strata_tabel_key` | teller voor widget-refresh |
| `sso_klanten_tabel` | — (nieuw) | kolommen `klant, type_post, N_klant, waarde_laag`, lang/tidy-formaat (één rij per klant×type-post-combinatie) |
| `sso_klanten_tabel_key` | — (nieuw) | teller voor widget-refresh |
| `sso_klanten_res` | `sso_strata_res` | `dict[klant_naam, resultaat_van_evalueer_SSO_klant_gestratificeerd]` — alleen klanten waarvoor de berekening slaagde |
| `sso_klanten_waarschuwingen` | `sso_strata_waarschuwingen` | `dict[klant_naam, list[str]]` |
| `sso_error` | `sso_strata_error` | gecombineerde foutmelding (validatie typen-posten-tabel, klanten-tabel, of per-klant berekeningsfouten) |
| `sso_klant_getoond` | — (nieuw) | naam van de klant waarvan de steekproeventabel/kanskromme getoond wordt |

Een lang/tidy-formaat voor de klantentabel (één rij per klant×type-post) is
gekozen boven een brede matrix (kolommen per type post), omdat het aantal
typen posten dynamisch is (rijen toevoegen/verwijderen in tabel 1) — een
brede matrix zou dan kolommen moeten bijmaken/verwijderen, wat met
`st.data_editor` niet goed gaat. Het lange formaat sluit ook aan bij het
bestaande rij-gebaseerde validatiepatroon van de andere tabbladen.

## UI-opbouw

Binnen `with tab_sso:`, in deze volgorde:

1. **Instellingen** (ongewijzigd, links): model (binomiaal/poisson),
   zekerheid, knop "evalueer alle klanten" (hernoemd van "evalueer
   gestratificeerd").
2. **Typen posten bij de SSO** — `st.data_editor` zoals nu, maar zonder de
   kolommen `N_klant` en `waarde_laag`. `on_change=on_sso_typen_posten_tabel_change`
   (hernoemde/aangepaste versie van `on_sso_strata_tabel_change`, met
   dezelfde directe-rollback-validatie voor `naam, n, k, ihr, ibr, car,
   materialiteit`, zonder de `N_klant`/`waarde_laag`-checks).
3. **Klanten** — nieuwe `st.data_editor` met kolommen `klant` (tekst),
   `type_post` (`SelectboxColumn`, opties = de huidige, niet-lege namen uit
   de typen-posten-tabel, elke render opnieuw opgebouwd), `N_klant`,
   `waarde_laag`. `on_change=on_sso_klanten_tabel_change` (nieuw, zelfde
   stijl rollback-validatie: `klant` niet leeg, `N_klant > 0`,
   `waarde_laag >= 0`; `type_post` wordt hier alleen op "niet leeg"
   gecontroleerd — de koppeling met een bestaande naam uit tabel 1 wordt pas
   bij de submit-validatie gecontroleerd, omdat tabel 1 kan wijzigen nadat
   een rij in tabel 2 al is ingevuld).
4. **Resultaat** (bij klik op "evalueer alle klanten"):
   - Groepeer `sso_klanten_tabel` op `klant`; voor elke klant met
     tenminste één geldige rij: bouw `post_typen` door elke rij te
     koppelen (op `naam == type_post`) aan de bijpassende rij uit
     `sso_typen_posten_tabel` (`n, k, ihr, ibr, car, materialiteit`) plus
     de klant-specifieke `N_klant, waarde_laag`.
   - Validatiefouten per rij (ongeldig getal, `type_post` niet gevonden in
     tabel 1, dubbele `(klant, type_post)`-combinatie binnen dezelfde
     klant) worden verzameld als specifieke meldingen (zelfde stijl als nu:
     `"Klant '{klant}': type post '{type_post}': ..."`).
   - Roep per klant `evalueer_SSO_klant_gestratificeerd(...)` aan in een
     eigen `try/except ValueError`, zodat één mislukte klant (bijv. een
     volledige blinde vlek bij één type post) de andere klanten niet
     blokkeert. Sla het resultaat op in `sso_klanten_res[klant]`, of de
     foutmelding in de verzamelde `sso_error`-tekst.
   - Vang `RuntimeWarning`s net als nu per klant op in
     `sso_klanten_waarschuwingen[klant]`.
   - Toon samenvattingstabel: één rij per succesvol berekende klant met
     `klant`, `max_fout_convolutie` (fractie, `_nl(..., 4)`),
     `max_fout_convolutie_geld` (`_nl(..., 2)`).
   - Toon `st.error(...)` voor verzamelde fouten (validatie + per-klant
     berekeningsfouten) en `st.warning(...)` voor verzamelde
     waarschuwingen (beide met klantnaam ervoor, zoals nu al met
     typenpostnaam gebeurt).
   - Toon een `st.selectbox("Toon details voor klant", opties=succesvolle
     klanten)` en daaronder, voor de gekozen klant: de steekproeventabel
     (`naam, waarde_laag, n_laag, k_laag`, zoals nu) en
     `plot_kanskromme(...)`.

## Implementatiestappen in `app.py`

1. Vervang `LEGE_SSO_STRATA_DF` door `LEGE_SSO_TYPEN_POSTEN_DF` (kolommen
   `naam, n, k, ihr, ibr, car, materialiteit`, 4 lege rijen zoals nu) en een
   nieuwe `LEGE_SSO_KLANTEN_DF` (kolommen `klant, type_post, N_klant,
   waarde_laag`, enkele lege rijen).
2. Werk de sessiestatus-initialisatie bij (nieuwe/hernoemde sleutels, zie
   tabel hierboven).
3. Hernoem en pas `on_sso_strata_tabel_change` aan tot
   `on_sso_typen_posten_tabel_change` (verwijder `N_klant`/`waarde_laag`
   uit de validatielus en de "nieuwe rij"-defaults).
4. Voeg `on_sso_klanten_tabel_change` toe (nieuwe callback, zelfde
   rollback-stijl, velden `klant` (niet-leeg), `type_post` (niet-leeg),
   `N_klant` (> 0), `waarde_laag` (>= 0)).
5. Herschrijf het `with tab_sso:`-blok: twee data_editors (typen posten,
   klanten), aangepaste submit-logica die per klant itereert en resultaten
   verzamelt, aangepaste resultatensectie met samenvattingstabel +
   klantselector + details/plot voor de gekozen klant.
6. Controleer of `evalueer_SSO_klant_gestratificeerd`,
   `bouw_strata_SSO_klant`, `moment_match_SSO` ongewijzigd kunnen blijven
   (verwachting: ja — de herstructurering zit volledig in `app.py`, de
   onderliggende functies verwachten nog steeds dezelfde `post_typen`-lijst
   per klant).

## Validatie / tests

- Geen bestaande geautomatiseerde tests raken `app.py` rechtstreeks (geen
  treffers in `tests/` voor Streamlit-specifieke logica) — verificatie
  blijft zoals eerder in dit project: `ruff check .`,
  `.venv/bin/python -m pytest` (mag geen regressie geven, want
  onderliggende pakketlogica wijzigt niet), en handmatig
  `.venv/bin/streamlit run app.py` + functionele steekproef: twee typen
  posten invullen, twee klanten elk met een deel van die typen posten
  invullen, "evalueer alle klanten" klikken, samenvattingstabel + per-klant
  details controleren, inclusief een expres foute `type_post`-waarde om de
  foutmelding te checken.

## Documentatie

Na implementatie: `AGENTS.md` bijwerken met een nieuwe sectie die de
herstructuur van de SSO-tab beschrijft (datamodel, tidy klantentabel-keuze,
per-klant try/except-aanpak), en de bestaande SSO-tab-secties in `AGENTS.md`
die verwijzen naar de oude `sso_strata_*`-namen en één-klant-per-keer-opzet
aanpassen/verwijderen waar ze niet meer kloppen.

## Open punt om bij implementatie te bevestigen

Hoeveel standaardrijen moet `LEGE_SSO_KLANTEN_DF` krijgen (nu 4 voor typen
posten)? Voorstel: 6 lege rijen, zodat bijvoorbeeld 2 klanten × 3 typen
posten meteen passen zonder eerst rijen te moeten toevoegen — dit is een
kleine cosmetische keuze, geen aparte vraag waard.
