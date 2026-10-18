# Concours Euro-Information 2026 — « IA responsable »
# Usage : make <cible> [DATASET=2_medium]

DATASET   ?= 1_example
DATASETS  := 1_example 2_medium 3_free 4_precise 5_energy 6_shortage 7_big
RUN       := uv run

.PHONY: help install solve score score-all test lint format notebooks clean

help:  ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

install:  ## Installe les dépendances (uv sync)
	uv sync

solve:  ## Résout une instance : make solve DATASET=2_medium
	$(RUN) python -m ia_responsable.cli --dataset $(DATASET)

score:  ## Vérifie une solution : make score DATASET=2_medium
	$(RUN) python test_solution.py -d datasets/$(DATASET).json -s solutions/$(DATASET)_main.json --details

score-all:  ## Vérifie les 7 solutions
	@for d in $(DATASETS); do \
		echo "== $$d"; \
		$(RUN) python test_solution.py -d datasets/$$d.json -s solutions/$${d}_main.json || exit 1; \
	done

test:  ## Lance les tests
	$(RUN) pytest -q

lint:  ## Vérifie le style du code
	$(RUN) ruff check src tests

format:  ## Formate le code
	$(RUN) ruff format src tests

notebooks:  ## Exécute tous les notebooks (long : jusqu'à 25 min pour 7_big)
	$(RUN) jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=-1 notebooks/*.ipynb

clean:  ## Supprime les fichiers temporaires
	find . -type d \( -name __pycache__ -o -name .ipynb_checkpoints -o -name .pytest_cache -o -name .ruff_cache \) -prune -exec rm -rf {} +
