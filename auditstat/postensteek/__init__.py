"""
auditstat.postensteek: evaluatie van één enkele steekproef (binomiaal of
hypergeometrisch), een omzetting van de SAS-macro ``%evalueer_postensteek``.
"""

from .evalueer_postensteek import evalueer_postensteek, plot_evalueer_postensteek

__all__ = ["evalueer_postensteek", "plot_evalueer_postensteek"]
