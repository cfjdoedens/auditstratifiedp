"""Inlezen van ``theorie.qmd`` voor de Theorie-tab van de Streamlit-app.

Het Quarto-document is de enige bron van de theorietekst. De app gebruikt
een kleine, bewust beperkte lezer (geen Quarto nodig op de server):

* de ``title`` uit de YAML-kop;
* tekst vóór de eerste ``## ``-kop is de inleiding;
* elke ``## ``-kop begint een sectie (in de app een uitklapper);
* een ``{python}``-codeblok met ``#| label: fig-...`` is een figuur; het
  bijschrift staat in ``#| fig-cap: "..."`` (op één regel);
* HTML-commentaar wordt genegeerd;
* alle overige tekst is gewone markdown (met ``$...$`` en ``$$...$$``).
"""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Figuur:
    label: str
    bijschrift: str = ""


@dataclass
class Sectie:
    titel: str
    blokken: list = field(default_factory=list)  # str (markdown) of Figuur


@dataclass
class Theorie:
    titel: str
    inleiding: str
    secties: list[Sectie]


_CODEBLOK_START = re.compile(r"^```\{python\}\s*$")
_OPTIE = re.compile(r"^#\|\s*([\w-]+):\s*(.*?)\s*$")


def _ontquote(waarde: str) -> str:
    if len(waarde) >= 2 and waarde[0] == waarde[-1] and waarde[0] in "\"'":
        return waarde[1:-1]
    return waarde


def parseer_theorie_qmd(tekst: str) -> Theorie:
    """Zet de inhoud van een theorie.qmd om in titel, inleiding en secties."""
    tekst = re.sub(r"<!--.*?-->", "", tekst, flags=re.DOTALL)
    regels = tekst.replace("\r\n", "\n").split("\n")

    titel = ""
    if regels and regels[0].strip() == "---":
        try:
            einde = regels.index("---", 1)
        except ValueError as fout:
            raise ValueError("YAML-kop in het qmd-bestand is niet gesloten.") from fout
        for regel in regels[1:einde]:
            m = re.match(r"^title:\s*(.*?)\s*$", regel)
            if m:
                titel = _ontquote(m.group(1))
        regels = regels[einde + 1 :]

    inleiding_regels: list[str] = []
    secties: list[Sectie] = []
    huidige: list[str] = inleiding_regels
    sectie: Sectie | None = None

    def sluit_tekstblok() -> None:
        nonlocal huidige
        if sectie is not None and huidige:
            blok = "\n".join(huidige).strip()
            if blok:
                sectie.blokken.append(blok)
        huidige = []

    i = 0
    while i < len(regels):
        regel = regels[i]
        if _CODEBLOK_START.match(regel):
            opties: dict[str, str] = {}
            i += 1
            while i < len(regels) and not regels[i].startswith("```"):
                m = _OPTIE.match(regels[i])
                if m:
                    opties[m.group(1)] = _ontquote(m.group(2))
                i += 1
            label = opties.get("label")
            if label is None:
                raise ValueError(
                    "Een {python}-blok in het qmd-bestand mist '#| label: ...'."
                )
            if sectie is None:
                raise ValueError("Een figuur staat vóór de eerste '## '-kop.")
            sluit_tekstblok()
            sectie.blokken.append(Figuur(label, opties.get("fig-cap", "")))
        elif regel.startswith("## "):
            sluit_tekstblok()
            sectie = Sectie(regel[3:].strip())
            secties.append(sectie)
        else:
            huidige.append(regel)
        i += 1
    sluit_tekstblok()

    return Theorie(titel, "\n".join(inleiding_regels).strip(), secties)


def lees_theorie_qmd(pad: str | Path) -> Theorie:
    return parseer_theorie_qmd(Path(pad).read_text(encoding="utf-8"))
