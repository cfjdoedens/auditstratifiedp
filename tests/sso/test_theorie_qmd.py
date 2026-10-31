from pathlib import Path

import pytest

from auditstat.sso.schema_figuren import THEORIE_FIGUREN
from auditstat.sso.theorie_qmd import Figuur, lees_theorie_qmd, parseer_theorie_qmd

QMD = Path(__file__).resolve().parents[2] / "theorie.qmd"

VOORBEELD = """---
title: "Titel"
---

Inleiding.

<!-- verborgen -->

## Een

Tekst één.

```{python}
#| label: fig-x
#| fig-cap: "Bijschrift"
print(1)
```

Tekst twee.

## Twee

Alleen tekst.
"""


def test_parseer_voorbeeld():
    t = parseer_theorie_qmd(VOORBEELD)
    assert t.titel == "Titel"
    assert t.inleiding == "Inleiding."
    assert [s.titel for s in t.secties] == ["Een", "Twee"]
    assert t.secties[0].blokken == [
        "Tekst één.",
        Figuur("fig-x", "Bijschrift"),
        "Tekst twee.",
    ]
    assert t.secties[1].blokken == ["Alleen tekst."]


def test_blok_zonder_label_geeft_value_error():
    with pytest.raises(ValueError, match="label"):
        parseer_theorie_qmd("## A\n\n```{python}\nprint(1)\n```\n")


def test_echte_theorie_qmd_is_consistent():
    t = lees_theorie_qmd(QMD)
    assert len(t.secties) == 5
    figuren = [b for s in t.secties for b in s.blokken if isinstance(b, Figuur)]
    assert {f.label for f in figuren} == set(THEORIE_FIGUREN)
    assert all(f.bijschrift for f in figuren)
