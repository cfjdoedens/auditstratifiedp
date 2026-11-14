"""
auditstat.postensteek: evaluatie van één enkele steekproef (binomiaal of
hypergeometrisch), een omzetting van de SAS-macro ``%eval_distribution``.
"""

from .eval_distribution import eval_distribution, plot_eval_distribution

__all__ = ["eval_distribution", "plot_eval_distribution"]
