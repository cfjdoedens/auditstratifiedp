import time
import pandas as pd
import matplotlib.pyplot as plt
from auditstratified.plan_stratified import plan_stratified
from auditstratified.eval_stratified import eval_stratified
from auditstratified.plot_kanskromme import plot_kanskromme

print("--- SCRIPT GESTART ---", flush=True)

print("1. Data voorbereiden...", flush=True)
data = pd.DataFrame({
    "naam": ["Subsidies", "Inkoop"],
    "waarde_laag": [1000000.0, 500000.0],
    "verwachte_foutfractie": [0.01, 0.005],
    "ihr": ["M", "L"],
    "ibr": ["M", "L"],
    "car": ["M", "L"],
    "kosten": [5.0, 1.0],  # Subsidies kost 5× zoveel per waarneming als Inkoop.
    "waarde_hoog": [100000.0, 50000.0],
    "fout_hoog": [0.0, 0.0],
    "materialiteit": [0.03, 0.03],
})

print("2. Plannen (dit kan even duren door het klimalgoritme)...", flush=True)
t0 = time.time()
plan = plan_stratified(steekproeven=data, materialiteit=0.03, zekerheid=0.95)
t1 = time.time()
print(f"   Klaar met plannen in {t1 - t0:.1f} seconden!", flush=True)
print(plan[["naam", "kosten", "n_basis", "n_laag"]])
print(f"Verwachte eindfout: {plan.attrs['geplande_max_fout_totaal']:.4f}\n")

print("3. Evalueren...", flush=True)
# Voeg de testresultaten toe aan je dataset
data["n_laag"] = [60, 30]
data["k_laag"] = [1, 0]

# Voer de evaluatie uit met FFT-convolutie
resultaat = eval_stratified(steekproeven=data, zekerheid=0.95, methode="FFT samen")

# Rapporteer de resultaten
print(f"Maximale fout (convolutie): {resultaat['max_fout_convolutie']:.4f}")
geld = resultaat["max_fout_convolutie_geld"]
geld_nl = f"{geld:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
print(f"In euro's: € {geld_nl}\n")

print("4. Plot genereren (venster opent nu)...", flush=True)
fig = plot_kanskromme(resultaat)
plt.show()

print("--- SCRIPT SUCCESVOL AFGEROND ---")
