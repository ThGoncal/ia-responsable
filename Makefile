# Concours Euro-Information 2026 — « IA responsable »
# Usage : make <cible> [DATASET=2_medium]

DATASET   ?= 1_example
DATASETS  := 1_example 2_medium 3_free 4_precise 5_energy 6_shortage 7_big
RUN       := uv run
IMAGE     := ia-responsable
# Les données en lecture seule, les solutions en écriture, avec l'utilisateur courant (fichiers à son nom)
DOCKER_RUN := docker run --rm --user $$(id -u):$$(id -g) \
	-v $(CURDIR)/datasets:/app/datasets:ro -v $(CURDIR)/solutions:/app/solutions

.PHONY: help install requirements solve score score-all test lint format notebooks build solve-docker score-all-docker clean

help:  ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

install:  ## Installe les dépendances (uv sync)
	uv sync

requirements:  ## Régénère requirements.txt depuis uv.lock (à lancer après tout changement de dépendance)
	uv export --format requirements.txt --no-default-groups --no-hashes --no-emit-project -o requirements.txt

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

build:  ## Construit l'image Docker
	docker build -t $(IMAGE) .

solve-docker:  ## Résout une instance dans le conteneur : make solve-docker DATASET=2_medium
	$(DOCKER_RUN) $(IMAGE) --dataset $(DATASET)

score-all-docker:  ## Vérifie les 7 solutions dans le conteneur
	@for d in $(DATASETS); do \
		echo "== $$d"; \
		$(DOCKER_RUN) --entrypoint python $(IMAGE) test_solution.py \
			-d datasets/$$d.json -s solutions/$${d}_main.json || exit 1; \
	done

clean:  ## Supprime les fichiers temporaires
	find . -type d \( -name __pycache__ -o -name .ipynb_checkpoints -o -name .pytest_cache -o -name .ruff_cache \) -prune -exec rm -rf {} +
