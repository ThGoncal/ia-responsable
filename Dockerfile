# Image d'exécution du solveur « IA responsable »
#
#   make build                          (ou : docker build -t ia-responsable .)
#   make solve-docker DATASET=2_medium
#
# Les versions sont figées : Python 3.12 et requirements.txt, généré depuis uv.lock (make requirements).

FROM python:3.12-slim

WORKDIR /app

# Les dépendances d'abord : cette couche reste en cache tant que requirements.txt ne change pas.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Puis le code : le package et le correcteur officiel.
COPY src ./src
COPY test_solution.py .

ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1

# Utilisateur sans droits d'administration
RUN useradd --create-home solver && mkdir -p datasets solutions && chown solver:solver solutions
USER solver

# une commande en deux morceaux:
# ENTRYPOINT est la partie fixe. Elle reste en place.
# CMD est la partie par défaut. Tout argument passé après le nom de l’image la remplace.
ENTRYPOINT ["python", "-m", "ia_responsable.cli", "--root", "/app"]
CMD ["--dataset", "1_example"]
