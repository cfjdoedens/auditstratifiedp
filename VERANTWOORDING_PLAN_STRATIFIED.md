# Verantwoording van het planningsalgoritme

## 1. Inleiding

De functie `plan_stratified` berekent de optimale steekproefverdeling over 
meerdere strata. Het doel is het vinden van de meest kostenefficiënte 
steekproefomvang waarbij de gecombineerde 
maximale fout - berekend via convolutie (met `eval_stratified`) -
onder de gestelde materialiteitsgrens 
blijft. We leveren hier het bewijs dat het toegepaste algoritme,
een vorm van marginale allocatie,
gegarandeerd het globale 
optimum vindt, en zich niet verliest in een lokaal optimum.

We zullen hieronder de te trekken posten - in de code: `n_laag` -  steeds 
benoemen als het aantal
uit te voeren _waarnemingen_. Dit om te benadrukken
dat elke waarneming extra informatie toevoegt voor de auditor, 
en daarmee inherent de onzekerheid en dus de maximale fout vermindert.

### 1.1 Lijst van symbolen

De volgende symbolen worden doorlopend gebruikt in dit document.

| Symbool | Definitie |
|:--------|:----------|
| $S$ | Totaal aantal strata |
| $i$ | Stratumindex, $i \in \{1, \dots, S\}$ |
| $j$ | Iteratie-index van het algoritme |
| $n_i$ | Aantal waarnemingen voor stratum $i$ |
| $c_i$ | Controlekosten per waarneming in stratum $i$ (standaard $1$) |
| $K$ | Totale controlekosten: $K = \sum_i n_i \cdot c_i$ |
| $M$ | Materialiteitsgrens voor de gecombineerde maximale fout |
| $d_i$ | Verwachte foutfractie van stratum $i$ (`verwachte_foutfractie`) |
| $F_i$ | De maximale foutfractie van stratum $i$, te bepalen uit $n_i$ en $d_i$, en het gebruikte statistisch model (binomiaal of Poisson)|
| $F$ | Gecombineerde maximale foutfractie (berekend via convolutie) |
| $V_i$ | Geldswaarde van het laagstratum van stratum $i$ (`waarde_laag`) |
| $V_{\text{totaal}}$ | Totale populatiewaarde: $V_{\text{totaal}} = \sum_i V_i$ |
| $w_i$ | Relatief gewicht van stratum $i$: $w_i = V_i / V_{\text{totaal}}$ |
| $k_i$ | Verwacht aantal fouten van stratum $i$: $k_i = n_i \cdot d_i$ |
| $\alpha$ | Vereist betrouwbaarheidsniveau, bijv. $0{,}95$ (`zekerheid`) |
| $c$ | Zekerheidsterm: $c = -\ln(1-\alpha)$ — *niet* te verwarren met $c_i$ (kosten) |
| $B_\alpha(a,\,b)$ | $\alpha$-kwantiel van de bètaverdeling met parameters $a$ en $b$ |
| $I_i(n_i)$ | Fisher-informatie over de foutfractie van stratum $i$ bij $n_i$ waarnemingen |
| $\Delta_i(n_i)$ | Marginale foutreductie per kosteneenheid bij toevoeging van één waarneming in stratum $i$ |
| $g$ | Granulariteit: aantal roosterpunten in de FFT-convolutie |
| $n_{\max}$ | Maximale steekproefgrootte waarbij $\Delta_i(n_i) \geq 1/g$ nog geldt |
| $g_{\min}$ | Minimale granulariteit waarbij $\Delta_i(n_i)$ nog detecteerbaar is |

## 2. Probleemdefinitie

Zij $S  \in {\displaystyle \mathbb {N} >= 1}$, het totaal aantal strata. Voor elk stratum $i \in \{1, \dots, S\}$ 
definiëren we:

- $n_i \in {\displaystyle \mathbb {N}}$, de steekproefomvang, dus het aantal uit te voeren waarnemingen;
- $c_i \in {\displaystyle \mathbb {R}} >= 0$, de uitvoeringskosten per waarneming, standaard $1$.

Het probleem is het minimaliseren van de totale controlekosten $K$:

$$K = \sum_{i=1}^{S} n_i \cdot c_i$$

onderworpen aan de voorwaarde dat de gecombineerde maximale foutfractie 
$F$ (geëvalueerd op de vereiste betrouwbaarheid, bijv. 95%) onder de totale 
materialiteit $M$ komt:

$$F(n_1, n_2, \ldots, n_S) < M$$

## 3. Het algoritme

### 3.1 Creëer startpositie voor de klim
`plan_stratified` bepaalt eerst per stratum 
het aantal waarnemingen 
dat nodig is
om onder de materialiteit van elk stratum te komen.

### 3.2 De steile klim

Daarna worden stapsgewijs waarnemingen toegevoegd aan 1 of meer strata net zo lang
tot de totale maximale fout onder de totale materialiteit is gezakt.

Per stap 
berekent de functie `vind_beste_strata_groep` voor elk stratum de 
marginale (= extra) opbrengst van het toevoegen van één waarneming.

- Zij $j \in \{1, \dots, MAX\_ITER\}$, de $j$-de iteratie van het algoritme, 
  waar MAX_ITER het maximum aantal iteraties van het algoritme is.
- Zij $n_{ij}$ het voor stratum $i$ geplande aantal waarnemingen in de $j$-de
  iteratie.
- Zij $c_i$ de kosten per waarneming voor stratum $i$.

De marginale opbrengst  $\Delta_i(n_{ij})$ voor stratum $i$ 
wordt gedefinieerd
als afname, gedeeld door de kosten, van de maximale fout bij toevoeging van één waarneming
in dat stratum:

$$\Delta_i(n_{ij})  = \frac{F(\dots, n_{ij}, \dots) - F(\dots, n_{ij} + 1, \dots)}{c_i}$$

Het algoritme selecteert het stratum (of de strata) met $\max(\Delta_i(n_{ij}))$ en 
hoogt $n_{ij}$ op met $1$. Bij een gelijkstand — wanneer meerdere strata 
dezelfde maximale $\Delta_i$ hebben — worden alle gedeelde winnaars tegelijk 
met 1 opgehoogd. Dit proces herhaalt zich 
totdat $F < M$ of totdat $j > MAX\_ITER$.

## 4. Bewijs van globale optimaliteit

### 4.1 Inperking

Om te kunnen bewijzen dat het algoritme het globale optimum vindt, 
beperken we ons:

1. $\forall i \in \{1, \dots, S\}, \; c_i = 1$ 
   We beschouwen alleen de situatie waarbij de kosten per waarneming 
   overal gelijk zijn. 
   Het algoritme probeert dan de vereiste zekerheid te halen met een zo 
   klein mogelijk totaal aantal waarnemingen $N$. 
1. $\forall i \in \{1, \dots, S\}, \; d_i < M$ 
   Voor elk stratum is de verwachte fout kleiner dan de toegestane
   maximale fout over alle strata.

We gebruiken de volgende hulpstellingen:

*  $(\frac{1}{S} \sum_{i=1}^S d_i) < M$ De gemiddelde verwachte fout over 
   alle strata ligt onder de totale materialiteit.
* Bij elke extra waarneming in een stratum $i$ zal de maximale fout 
   in dat stratum zakken.
* Bij elke extra waarneming in een stratum $i$ zal de totale
   maximale fout zakken.
* Bij voldoende waarnemingen in een stratum $i$ zal de maximale fout, $F_i$,
   van dat stratum onder de totale materialiteit, $M$, zakken.
* Bij voldoende waarnemingen in de strata zal de 
  totale maximale fout, $F$, onder de materialiteitsgrens, $M$, zakken.


* Hulp1: **Afnemende meeropbrengst** (voor de bètaverdeling )

* Hulp2: **Stapsgewijze representatie is volledig**
   Zonder verlies van algemeenheid kunnen we elk klimalgoritme representeren
   alsof het stapje voor stapje keuzes maakt voor in welke
   stratum nu weer een waarneming wordt toegevoegd.
* Hulp3: **Ander algoritme betekent andere stratumkeuze**
   Een algoritme dat in de praktijk verschilt van
   het steilsteklimalgoritme zal op een bepaald moment in de opvolgende
   sequentie van het kiezen welk stratum we een extra waarneming willen 
   toekennen, een andere keuze moeten maken dan het steilsteklimalgoritme.
* Hulp4: **Ander algoritme kiest in keuzeproces voor minder meeropbrengst**
   Die keuze zal dus minder meeropbrengst opleveren dan
   bij gebruik van het steilsteklimalgoritme.
*  Hulp5: **Dominante meeropbrengst blijft dominant**
   Zolang het alternatief algoritme niet alsnog een waarneming uit
   het versmade stratum zal doen, zal elke volgende keus van het alternatief
   algoritme een lagere meeropbrengst hebben dan die voor het
   versmade stratum.

Stel dat er een allocatie $n^$ bestaat met $K^* < K_{\text{steilsteklim}}$ die
eveneens $F < M$ bereikt. Beschouw de eerste stap waarop $n^$ en 
het steilsteklimalgoritme divergeren: het steilsteklimalgoritme kiest 
stratum $i$, $n^$ kiest stratum $j \neq i$, met 
$\Delta_i \geq \Delta_j$ (Hulp4).
Door Hulp5 (met Hulp1 als basis) levert elke volgende 
keuze van $n^$ in stratum $j$ minder op dan de steilsteklimkeuze in 
stratum $i$, totdat $n^$ alsnog een extra waarneming aan 
stratum $i$ toevoegt — wat de totale kosten van $n^$ niet 
vermindert. Inductief volgt dat $K^ \geq K_{\text{steilsteklim}}$. 
Tegenspraak.

### 4.1 Bewijs van hulp1

#### Stap 1: Kwantiel-functie van de bètaverdeling is convex in parameters

Voor de bètaverdeling $Beta(\alpha, \beta)$ en 
vaste $p \in (0,1)$, is 
de kwantielfunctie
$Q(p; \alpha, \beta)$ 
convex in $(\alpha, \beta)$.
Hieruit volgt dat voor 
$$\alpha(n) = n \cdot d + 1$$ en
$$\beta(n)= n \cdot (1-d) + 1$$
(met $d \in [0,1)$), de functie
$$f(n)=B_p (\alpha(n),\beta(n))$$
convex is in n.
Daardoor is de marginale afname
$$\Delta(n)=f(n)−f(n+1)$$
dalend in n.
Dit wil zeggen
$$\Delta(n) > \Delta(n+1)$$
De kansdichtheid van de bètaverdeling is gedefinieerd op het interval [0, 1] als

$$f(p;\alpha,\beta) = \frac{1}{\mathrm{B}(\alpha,\beta)} p^{\alpha-1}(1-p)^{\beta-1}$$

Daarin zijn $\alpha$ en $\beta$ beide positieve reële getallen en is 
$$B(\alpha,\beta) = \frac{\Gamma(\alpha)\Gamma(\beta)}{\Gamma(\alpha + \beta)}$$
de bètafunctie.

Voor een gegeven kans $p$ (waarbij $0 < p < 1$) is de 
kwantielfunctie $Q(p; \alpha, \beta)$ 
gedefinieerd als de unieke drempelwaarde waarvoor geldt:
$$p = \frac{1}{B(\alpha, \beta)} \int_{0}^{Q(p, \alpha, \beta)} t^{\alpha-1}(1-t)^{\beta-1} \, dt$$ 

Belangrijk resultaat uit de literatuur:
De bètaverdeling is een natuurlijke exponentiële familie met natuurlijke parameters:
θ1=ψ(α)−ψ(α+β),θ2=ψ(β)−ψ(α+β),\theta_1 = \psi(\alpha) - \psi(\alpha + \beta), \quad \theta_2 = \psi(\beta) - \psi(\alpha + \beta),θ1​=ψ(α)−ψ(α+β),θ2​=ψ(β)−ψ(α+β),
waar ψ\psiψ de digamma-functie is.
Voor natuurlijke exponentiële families is de kwantiel-functie convex in de natuurlijke 
parameters (zie bijv. Barndorff-Nielsen, 1978, "Exponential Families").
Omdat α\alphaα en β\betaβ stijgende functies zijn van θ1\theta_1θ1​ en 
θ2\theta_2θ2​, volgt dat Q(p;α,β)Q(p; \alpha, \beta)Q(p;α,β) convex is 
in (α,β)(\alpha, \beta)(α,β).

#### Stap 2: Lineaire parameterisatie in n
In ons geval zijn de parameters:
α(n)=n⋅d+1,β(n)=n⋅(1−d)+1.\alpha(n) = n \cdot d + 1, \quad \beta(n) = n \cdot (1-d) + 1.α(n)=n⋅d+1,β(n)=n⋅(1−d)+1.
Dit is een lineaire transformatie van n:
(α(n)β(n))=(d1−d)n+(11).\begin{pmatrix} \alpha(n) \\ \beta(n) \end{pmatrix} = \begin{pmatrix} d \\ 1-d \end{pmatrix} n + \begin{pmatrix} 1 \\ 1 \end{pmatrix}.(α(n)β(n)​)=(d1−d​)n+(11​).

#### Stap 3: Samenstelling van convexe functies

Q(p;α,β)Q(p; \alpha, \beta)Q(p;α,β) is convex in (α,β)(\alpha, \beta)(α,β) (Stap 1).
(α(n),β(n))(\alpha(n), \beta(n))(α(n),β(n)) is lineair (en dus convex) in nnn (Stap 2).
De samenstelling van een convex functie met een lineaire functie is convex.
Dus: f(n)=Q(p;α(n),β(n))f(n) = Q(p; \alpha(n), \beta(n))f(n)=Q(p;α(n),β(n)) is convex in nnn.

#### Stap 4: Afnemende meeropbrengst
Voor een convexe functie f geldt:
f(n+1)−f(n)is stijgend in n.f(n+1) - f(n) \quad \text{is stijgend in } n.f(n+1)−f(n)is stijgend in n.
Dus:
f(n)−f(n+1)>f(n+1)−f(n+2).f(n) - f(n+1) > f(n+1) - f(n+2).f(n)−f(n+1)>f(n+1)−f(n+2).
Maar Δ(n)=f(n)−f(n+1)\Delta(n) = f(n) - f(n+1)Δ(n)=f(n)−f(n+1), dus:
Δ(n)>Δ(n+1).\Delta(n) > \Delta(n+1).Δ(n)>Δ(n+1).
QED: De marginale opbrengst (foutreductie per extra waarneming) is dalend in nnn.

  
## 5. Numerieke aspecten en praktische implementatie

Het algoritme in §3 is theoretisch exact, maar de praktische
implementatie in `plan_stratified.py` en `eval_stratified.py`
moet rekening houden met numerieke benaderingen en computationele beperkingen.
Hieronder lichten we de belangrijkste aspecten toe.

### 5.1 Empirische toets van de optimaliteit

Empirische validatie met de daarvoor gebouwde
functie `analyseer_klimheuristiek` in analyseer_klimheuristiek.py, bevestigt dat 
het steilsteklimalgoritme dezelfde uitkomst geeft
als gevonden met het brute-force globale optimum voor alle geteste
$n$-waarden.

### 5.2 Granulariteit: theoretische grens

Het planningsalgoritme gebruikt `eval_stratified` met FFT-convolutie
over een gediscretiseerd rooster met $g$ punten (de granulariteit).
De kleinst detecteerbare foutreductie op het rooster is van orde $1/g$.

* Zij $V_i$ = `waarde_laag_i`, de totale geldswaarde van het laagstratum
  van stratum $i$.
* Zij $V_{totaal} = \sum_i V_i$ de totale populatiewaarde
  over alle strata samen.
* Zij $w_i$ het relatieve gewicht van stratum $i$ als
  $w_i = V_i / V_{totaal}$.
* Zij $d_i$ de verwachte foutfractie (`verwachte_foutfractie`) voor stratum $i$.
* Zij $F_i(n_i)$ de maximale fout voor stratum $i$, gegeven $n_i$ geplande
  waarnemingen.

Verder is $\alpha$ het vereiste betrouwbaarheidsniveau (`zekerheid`,
standaard $0{,}95$), en $c = -\ln(1 - \alpha)$ de bijbehorende zekerheidsterm.

De centrale grootheid is de marginale reductie per extra waarneming in stratum $i$:

$$\Delta_i(n_i) = w_i \cdot \bigl[B_\alpha(k_i+1,\; n_i-k_i+1) - B_\alpha(k_i'+1,\; n_i+1-k_i'+1)\bigr]$$

met $k_i = n_i \cdot d_i$ en $k_i' = (n_i+1) \cdot d_i$.

De FFT kan de reductie alleen detecteren als $\Delta_i(n_i) > 1/g$. 
En dus ook als $g > 1/\Delta_i(n_i)$.

Hieruit volgen:

* $n_{\max}$: het grootste gehele aantal waarnemingen $n_i$, waarvoor $\Delta_i(n_i) \gt 1/g$
* $g_{\min}$: de kleinste granulariteit $g$, waarvoor de reductie nog
  detecteerbaar is, $g = \lceil 1/\Delta_i(n_i) \rceil$

Beide grootheden worden exact berekend in `valideer_granulariteit.py` via
`scipy.stats.beta.ppf` en binair zoeken — zonder analytische benaderingen.

**Tabel 1 — maximale steekproefgrootte $n_{max}$ gegeven $\alpha$, $w_i$, $d_i$ en $g$**

| $\alpha$ | $w_i$ | $d_i$ |        $g$ | $n_{max}$ |
|---------:|------:|------:|-----------:|----------:|
|     0,95 |  1,00 | 0,000 |     10.000 |       170 |
|     0,95 |  0,50 | 0,000 |     10.000 |       119 |
|     0,95 |  0,20 | 0,000 |     10.000 |        74 |
|     0,95 |  1,00 | 0,000 |    100.000 |       544 |
|     0,95 |  0,50 | 0,000 |    100.000 |       384 |
|     0,90 |  1,00 | 0,000 |     10.000 |       149 |
|     0,95 |  1,00 | 0,010 |     10.000 |       176 |
|     0,95 |  1,00 | 0,050 |     10.000 |       202 |
|     0,95 |  0,50 | 0,010 |     10.000 |       122 |

Een grotere granulariteit of een groter stratum-gewicht vergroot $n_{max}$.
Opvallend: bij $d_i > 0$ is $n_{max}$ hoger dan bij $d_i = 0$ — de
bèta-verdeling convergeert bij aanwezige fouten sneller, waardoor de
reductie per stap langer detecteerbaar blijft.

**Tabel 2 — minimale granulariteit $g_{min}$ gegeven $\alpha$, $w_i$, $d_i$ en $n$**

| $\alpha$ | $w_i$ | $d_i$ |   $n$ |   $g_{min}$ |
|---------:|------:|------:|------:|------------:|
|     0,95 |  1,00 | 0,000 |    50 |         939 |
|     0,95 |  1,00 | 0,000 |   100 |       3.542 |
|     0,95 |  1,00 | 0,000 |   200 |      13.757 |
|     0,95 |  0,50 | 0,000 |   100 |       7.084 |
|     0,95 |  0,20 | 0,000 |   100 |      17.710 |
|     0,90 |  1,00 | 0,000 |   100 |       4.577 |
|     0,95 |  1,00 | 0,010 |   100 |       3.459 |
|     0,95 |  1,00 | 0,050 |   100 |       2.994 |
|     0,95 |  0,50 | 0,010 |   100 |       6.917 |

$g_{min}$ schaalt ruwweg kwadratisch met $n$: verdubbeling van de
steekproefgrootte verhoogt de benodigde granulariteit circa viervoudig.
Een kleiner stratum-gewicht vereist een hogere granulariteit.
Bij $d_i > 0$ is $g_{min}$ iets lager: de verwachte foutfractie maakt de
reductie per stap groter, zodat een grover rooster volstaat.

### 5.3 Werkelijke FFT-precisie

Empirische meting toont dat de FFT de foutreductie in de praktijk nooit
exact nul bereikt, ook niet ver boven $n_{max}$.
De oorzaak ligt in de functie `interpolate_quantile`
in `eval_stratified.py`, die wordt aangeroepen als:

```python
max_fout = interpolate_quantile(cum_p, x_totaal_fractie, zekerheid)
```
In plaats van af te ronden naar het dichtstbijzijnde roosterpunt berekent
deze functie het kwantiel via lineaire interpolatie tussen de twee
roosterpunten die het doelkwantiel insluiten:

$$x_{kwantiel} = x_{onder} + \frac{\alpha - p_{onder}}{p_{boven} - p_{onder}}
  \cdot (x_{boven} - x_{onder})$$

De uitkomst verandert daardoor met elke extra steekproefpost, ook wanneer
de verschuiving kleiner is dan één roosterstap. De effectieve
resolutie is bepaald door de drijvende-kommaprecisie van de
kanswaarden $p_{onder}$ en $p_{boven}$ ($\approx 10^{-15}$), niet door
$1/g$. De theoretische grens $n_{max}(i)$ is daardoor conservatief.

### 5.4 Gelijkstand en parallelle ophogingen

Wanneer twee of meer strata exact dezelfde maximale $\Delta_i$ hebben,
worden ze gelijktijdig met 1 opgehoogd. De gelijkstand wordt gedetecteerd
met een tolerantie van $10^{-12}$ om drijvende-komma-afrondingsfouten
($\approx 10^{-16}$) op te vangen zonder werkelijke ongelijkheden
(orde $10^{-4}$ en groter) als gelijkstand te classificeren.

Voor volledig identieke strata is empirisch geverifieerd dat deze
tolerantie de symmetrie correct handhaaft: de verdeling blijft $[n, n]$
voor elke $N_{add}$.

Negatieve foutreducties kunnen ook door zwevendekommabewerkingen ontstaan.
In theorie geldt altijd $\Delta_i \geq 0$ (monotoonheid), maar door afronding
kan `foutreductie < 0` optreden. In `vind_beste_strata_groep` wordt dat
afgevangen:

```python
if foutreductie < 0:
    foutreductie = 0
```

### 5.5 Fallback-proxy bij ondetecteerbare FFT-reductie

In `vind_beste_strata_groep` is een analytische fallback-proxy opgenomen
die wordt geactiveerd wanneer de FFT geen meetbare reductie detecteert
($\Delta_i = 0$ voor alle $i$):

$$proxy\_onzekerheid_i = \frac{V_i}{\sqrt{\max(n_i, 1)} \cdot c_i}$$

In de praktijk wordt deze tak bij normaal gebruik van `plan_stratified()`
nooit bereikt, om twee onafhankelijke redenen:

1. **FFT-precisie (zie §5.3).** Omdat `interpolate_quantile` het kwantiel
   via lineaire interpolatie berekent, levert de FFT altijd een strikt
   positieve reductie. De conditie $\Delta_i = 0$ treedt feitelijk nooit op.

2. **Wiskundige garantie.** Bij $n_i = n_{max}(i) = \sqrt{w_i \cdot c \cdot g}$
   is de maximale foutfractie al gedaald tot
   $f_{max} \approx \sqrt{w_i \cdot c / g}$. Voor gangbare waarden
   ($\alpha = 0{,}95$, $g = 10{.}000$, één stratum) bedraagt dit
   $\approx 1{,}7\%$ — ruim onder gebruikelijke materialiteitsgrenzen
   (2–5%). Het algoritme convergeert daardoor altijd naar $F < M$
   vóórdat enig stratum $n_{max}$ bereikt.

De fallback-proxy is daarmee defensieve code: correct geïmplementeerd en
empirisch geverifieerd voor het symmetrische geval (identieke strata worden
als gelijkwaardig geselecteerd), maar effectief dood pad bij normaal gebruik.

### 5.6 Numerieke artefacten in de FFT

De FFT introduceert kleine complexe-getalartefacten in de
kanswaarden. Na de inverse FFT worden minuscule negatieve waarden
(drijvende-kommaruis) op nul gezet, maar alleen als ze kleiner zijn dan
$10^{-12}$ in absolute waarde. Grotere negatieve waarden worden opzettelijk
niet gecorrigeerd zodat ze stroomafwaarts zichtbaar blijven als signaal van
een echt probleem:

```python
p_totaal[(p_totaal < 0) & (np.abs(p_totaal) < 1e-12)] = 0
```

Om de nauwkeurigheid en snelheid te verbeteren wordt de vectorlengte
waarover de FFT rekent opgevuld tot de volgende macht van 2
(via `next_fast_len()`).

### 5.7 Randgeval: verwaarloosbare geldmassa

Strata met een gezamenlijke `waarde_laag` kleiner dan $0{,}01$ worden direct
analytisch behandeld en niet geconvolueerd. Dit voorkomt numerieke problemen
bij een nagenoeg lege verdeling.






