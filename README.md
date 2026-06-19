# 📊 auditstratified (Python Editie)
Een Python-pakket voor het plannen en evalueren van gestratificeerde
steekproeven, conform de HARo-methodiek van de Rijksoverheid.
Oorspronkelijk ontwikkeld als R-pakket en interactieve Shiny-applicatie, is deze
krachtige wiskundige rekenmotor nu volledig gemigreerd naar Python. Dit maakt
het algoritme direct toegankelijk voor data science teams, analytics-afdelingen
(zoals de ADR) en cloud-omgevingen zoals Google Colab.
## ✨ Kenmerken
🎯 Gestratificeerd Plannen: Berekent automatisch de meest efficiënte, wiskundig
optimale steekproefverdeling over meerdere strata (Stap 1).
📈 Geavanceerde Evaluatie: Voegt foutkanskrommes van afzonderlijke steekproeven
samen via pijlsnelle FFT-convolutie of Monte Carlo simulaties.
🏛️ HARo-integratie: Ingebouwde rekenregels voor het Handboek Auditing
Rijksoverheid (IHR, IBR, CAR).
🚀 Vectorized & Snel: Gebouwd op Pandas, NumPy en SciPy voor optimale
performance.
## 💻 Installatie
Je kunt dit pakket eenvoudig lokaal installeren of direct inlezen in een
cloud-omgeving (zoals Jupyter of Colab).
1. Clone deze repository:
```bash
git clone https://github.com/cfjdoedens/auditstratifiedp.git 
cd auditstratified
```
2. Installeer de afhankelijkheden:
```bash
pip install -r requirements.txt
```
## 🚀 Snel aan de slag (Quick Start)
1. Een steekproef plannen
Het klimalgoritme zoekt automatisch de optimale verdeling om onder de gestelde
materialiteit te blijven.
```python
import pandas as pd from auditstratified.plan_stratified import plan_stratified

# Definieer de strata en de HARo-risico's
data = pd.DataFrame({
    'naam': ['Subsidies', 'Inkoop'],
    'waarde_laag': [1000000.0, 500000.0],
    'verwachte_foutfractie': [0.01, 0.005],
    'ihr': ['M', 'L'], 'ibr': ['M', 'L'], 'car': ['M', 'L'],
    'materialiteit': [0.03, 0.03],
    'fout_hoog': [0.0, 0.0],
    'goed_hoog': [100000.0, 50000.0]
})

# Bereken het optimale plan 
plan = plan_stratified(steekproeven=data,
materialiteit=0.03, zekerheid=0.95)
print(plan[['naam', 'n_basis', 'n_definitief']]) 
print(f"Verwachte eindfout:
{plan.attrs['geplande_max_fout_totaal']:.4f}")
```
2. Een getrokken steekproef evalueren
Na de uitvoering van de controle kun je de gevonden fouten (k_laag of bedragen
in het hoogstratum) evalueren.
```python
from auditstratified.eval_stratified import eval_stratified

# Voeg de testresultaten (zoals n_laag en k_laag) toe aan je dataset... 
data['n_laag'] = [60, 30] # data['k_laag'] = [1, 0]
resultaat = eval_stratified(steekproeven=data, zekerheid=0.95, methode="FFT
samen")
print(f"Maximale fout (convolutie): {resultaat['max_fout_convolutie']:.4f}")
print(f"In euro's: € {resultaat['max_fout_convolutie_geld']:,.2f}")
```
## 🧪 Testen van het algoritme
Het pakket bevat een uitgebreide en rigoureuze test-suite die de
Python-uitkomsten (tot ver achter de komma) bewijst ten opzichte van het
originele R-pakket. Praktijkcases zoals het LNV 2023 dossier en Paul van
Batenburg worden hiermee gevalideerd.
Om de tests (30+ stuks) uit te voeren:
```bash
python -m pytest
```
## ☁️ Google Colab (Demo)
Werken in de cloud zonder installatie? Maak een leeg Colab notebook aan en plak
dit in de eerste cel:
!git clone https://github.com/cfjdoedens/auditstratifiedp.git !pip install -r
auditstratified/requirements.txt import sys;
sys.path.append('/content/auditstratified')
Vervolgens kun je de functies direct gebruiken.
