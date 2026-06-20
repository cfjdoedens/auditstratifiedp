# 📊 auditstratified (Python Editie)
Een Python-pakket voor het plannen en evalueren van gestratificeerde
steekproeven, conform HARo (Handboek Auditing Rijksoverheid).
Oorspronkelijk ontwikkeld als R-pakket en interactieve Shiny-applicatie, is dit
 nu gemigreerd naar Python. 
## ✨ Kenmerken

- 🎯 Gestratificeerd Plannen: Berekent automatisch de meest efficiënte, 
optimale steekproefverdeling over meerdere strata (Stap 1).
- 📈 Geavanceerde Evaluatie: Voegt foutkanskrommes van afzonderlijke steekproeven
samen via pijlsnelle FFT-convolutie of Monte Carlo simulaties.
- 🏛️ HARo-integratie: Ingebouwde rekenregels voor het Handboek Auditing
Rijksoverheid (IHR, IBR, CAR).
- 🚀 Vectorized & Snel: Gebouwd op Pandas, NumPy en SciPy voor optimale
performance.
## 💻 Installatie
Je kunt dit pakket eenvoudig lokaal installeren of direct inlezen in een
cloud-omgeving (zoals Jupyter of Colab).

1. Clone deze repository:
```bash
git clone https://github.com/cfjdoedens/auditstratifiedp.git
cd auditstratifiedp
```

2. Installeer de afhankelijkheden:
```bash
pip install -r requirements.txt
```
## 🚀 Aan de slag 

1. Een steekproef plannen
Het klimalgoritme zoekt automatisch de optimale verdeling om onder de gestelde
materialiteit te blijven.
```python
import pandas as pd 
from auditstratified.plan_stratified import plan_stratified

# Definieer de strata en de HARo-risico's
data = pd.DataFrame({
    'naam': ['Subsidies', 'Inkoop'],
    'waarde_laag': [1000000.0, 500000.0],    
    'waarde_hoog': [0, 0],
    'verwachte_foutfractie': [0.01, 0.005],
    'ihr': ['M', 'L'], 'ibr': ['M', 'L'], 'car': ['M', 'L'],
    'materialiteit': [0.03, 0.03],
    'fout_hoog': [0.0, 0.0],
    'goed_hoog': [100000.0, 50000.0]
})

# Bereken het optimale plan 
plan = plan_stratified(steekproeven=data, materialiteit=0.03, zekerheid=0.95)
print(plan[['naam', 'n_basis', 'n_definitief']]) 
print(f"Verwachte eindfout: {plan.attrs['geplande_max_fout_totaal']:.4f}")
```

2. Een getrokken steekproef evalueren
Na de uitvoering van de controle kun je de gevonden fouten (k_laag of bedragen
in het hoogstratum) evalueren.
```python
from auditstratified.eval_stratified import eval_stratified

# Voeg de testresultaten (zoals n_laag en k_laag) toe aan je dataset.
data['n_laag'] = [60, 30] 
data['k_laag'] = [1, 0]

# Voer de evaluatie uit met FFT-convolutie.
resultaat = eval_stratified(steekproeven=data, zekerheid=0.95, methode="FFT samen")

# Rapporteer de resultaten.
print(f"Maximale fout (convolutie): {resultaat['max_fout_convolutie']:.4f}")
print(f"In euro's: € {resultaat['max_fout_convolutie_geld']:,.2f}")
```
## 🧪 Testen van het algoritme
Het pakket bevat tests om het pakket te valideren:

- Functionele tests, met onder meer praktijkgevallen.
- Tests of de verschillende convolutiealgoritmen dezelfde uitkomst geven. 
- Tests of de uitkomsten overeenkomen met de uitkomsten van dit pakket als R-pakket.

Om de tests (30+ stuks) uit te voeren:
```bash
python -m pytest
```
## ☁️ Google Colab (Demo)
Werken in de cloud zonder installatie? Maak een leeg Colab notebook aan en plak
dit in de eerste cel:
```bash
# Kloon de repository en installeer de bibliotheken; voer dit uit in een code-cel.
!git clone https://github.com/cfjdoedens/auditstratifiedp.git
!pip install -r auditstratifiedp/requirements.txt

# Voeg het juiste pad toe aan het Python-zoekpad.
import sys
sys.path.append('/content/auditstratifiedp')

```

Vervolgens kun je de functies direct gebruiken.

## 📄 Licentie

Dit pakket is vrijgegeven onder de
[European Union Public Licence v1.2 (EUPL-1.2)](https://joinup.ec.europa.eu/collection/eupl/eupl-text-eupl-12).
Je mag het pakket vrij gebruiken, aanpassen en verspreiden, mits afgeleide werken
onder dezelfde licentie worden gepubliceerd.

## 🤝 Bijdragen

Bijdragen zijn welkom. Open een [issue](https://github.com/cfjdoedens/auditstratifiedp/issues)
voor een bugreport of idee, of dien een pull request in. Zorg er bij een pull
request voor dat de bestaande tests slagen (`python -m pytest`) en voeg waar
nodig nieuwe tests toe.
