# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os
import sys
# Laat Sphinx direct in de src-map kijken.
sys.path.insert(0, os.path.abspath('../../src'))

project = 'auditstratified'
copyright = '2026, Crist-Jan Doedens'
author = 'Crist-Jan Doedens'
release = '0.1'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',   # Haalt docstrings uit je code
    'sphinx.ext.napoleon'   # Vertaalt de NumPy-stijl naar HTML
]

templates_path = ['_templates']
exclude_patterns = []

language = 'nl'

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'pydata_sphinx_theme'
html_static_path = ['_static']
