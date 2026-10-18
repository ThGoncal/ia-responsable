# IA responsable : du glouton au solveur exact

Résolution du **Concours de Code Euro-Information 2026** (« Pour une IA responsable »), repris après la clôture pour comparer trois familles d'algorithmes sur un même problème d'optimisation : **heuristiques gloutonnes**, **recuit simulé** et **programmation linéaire en nombres entiers** (OR-Tools / SCIP).

Résultat : **99,97 % du score maximal du concours** sur les 7 jeux de données. Le meilleur score du concours est égalé sur 2 d'entre eux.

---

## Le problème

Un centre de calcul doit choisir quels modèles d'IA entraîner sous un **plafond d'énergie**. Chaque modèle :

- rapporte une **valeur** et consomme de l'**énergie** ;
- a 1 à 4 **besoins en données** (types `n`, `t`, `i`, `c`), chacun défini par un intervalle `[lower, upper]` à remplir avec des **datasets** (chaque dataset ne sert qu'une fois) ;
- perd la **moitié de sa valeur** s'il utilise un dataset sous droits d'auteur ou des données générées ;
- peut servir de **source** de données à un autre modèle s'il n'a qu'un seul besoin. Sa valeur est alors perdue, mais son énergie reste comptée.

C'est un **sac à dos multidimensionnel** (énergie, données libres, données totales), combiné à un **problème d'affectation** (quels datasets pour quel besoin) et à un **problème d'appariement** (quelle source pour quelle cible). L'énoncé complet est dans [`docs/enonce_fr.md`](docs/enonce_fr.md).

## Résultats

| Jeu de données | Taille (modèles / datasets) | Notre score | Meilleur score du concours | Écart |
|---|---|---:|---:|---:|
| 1_example | 5 / 5 | 12 946 | 12 946 | **0** |
| 2_medium | 3 000 / 10 000 | 272 224 | 272 322 | −98 |
| 3_free | 5 000 / 20 000 | 523 758 | 523 758 | **0** (optimum prouvé) |
| 4_precise | 8 000 / 40 000 | 1 031 910 | 1 031 941 | −31 |
| 5_energy | 11 000 / 100 000 | 3 785 420 | 3 786 108 | −688 |
| 6_shortage | 15 000 / 5 000 | 668 822 | 669 798 | −976 |
| 7_big | 50 000 / 250 000 | 5 822 383 | 5 822 561 | −178 |
| **Classement** | | | | **6 997 940 / 7 000 000 points** |

Barème du concours : `1 000 000 × score / meilleur score` par jeu de données.

## La démarche

Chaque notebook correspond à une étape. Chaque étape a été motivée par une limite de la précédente.

| Notebook | Méthode | Ce qu'on y apprend |
|---|---|---|
| `07` | Visualisation des 7 instances | Chaque instance a sa propre contrainte active |
| `08` | Énumération exhaustive (`1_example`) | Sur 5 modèles, on peut tout essayer |
| `09` | Gloutons + relaxation linéaire (`2_medium`) | L'ordre de priorité fait tout ; une **borne supérieure** mesure l'écart à l'optimum |
| `10` | Recuit simulé (`2_medium`) | Partir d'une bonne solution : chauffer ne sert à rien ici |
| `11` | OR-Tools : SCIP vs CP-SAT (`2_medium`) | Modèle agrégé + attribution des datasets + réparation |
| `12` | `3_free` | « Optimal » veut dire « à la tolérance près » |
| `13` | `4_precise` | Concurrence pour les datasets ; recherche à départs multiples |
| `14` | `5_energy` | Agréger les sources ; un **faux optimum** causé par des coefficients de 10¹² |
| `15` | `6_shortage` | Diagnostiquer la perte, puis la corriger par une marge calibrée |
| `16` | `7_big` | À grande échelle, le meilleur modèle est celui qui suffit |

### Le pipeline final

```
instance JSON
   │
   ├─ 1. contrôle préalable      : besoins réalisables en données libres ?
   ├─ 2. modèle agrégé (SCIP)    : quels modèles, à quelle valeur, combien de sources ?
   ├─ 3. attribution (glouton)   : quels datasets pour chaque besoin, plusieurs ordres essayés
   ├─ 4. appariement             : quelle source pour quelle cible
   ├─ 5. complétion + réparation : combler les données restantes, échanger les données libres
   └─ 6. vérification            : correcteur officiel du concours
```

Le solveur raisonne sur des **quantités** de données (agrégation), ce qui le rend soluble jusqu'à 50 000 modèles. Les heuristiques traduisent ensuite sa réponse en **datasets réels**.

## Ce que ce projet m'a appris

1. **Regarder les données avant de choisir l'algorithme.** Selon l'instance, la contrainte active est l'énergie, les données libres, la précision des besoins ou les données totales. Le modèle mathématique a dû changer à chaque fois.
2. **Une borne est un instrument de mesure.** Elle dit combien il reste à gagner. Elle a aussi révélé deux erreurs : une hypothèse fausse sur les sources, puis un faux optimum numérique.
3. **Un solveur se règle et peut se tromper.** Tolérance d'arrêt par défaut, contrainte oubliée quand une liste est vide, coefficients trop grands, limite de temps non reproductible d'une machine à l'autre.
4. **Optimiser le modèle n'est pas optimiser la réalité.** Une sélection un peu moins bonne sur le papier peut donner un meilleur plan réel si elle est plus facile à découper en datasets.
5. **L'exact et l'heuristique se complètent.** Ni l'un ni l'autre n'aurait suffi seul.
6. **Les tests trouvent ce que les notebooks cachent.** En passant du notebook au package, un test sur `1_example` a révélé qu'un modèle à demi-valeur ne pouvait pas mélanger datasets libres et sous droits dans un même besoin. Cette limite était présente dans tous les notebooks.

## Structure du dépôt

```
.
├── README.md
├── Makefile
├── pyproject.toml / uv.lock
├── docs/
│   └── enonce_fr.md
├── datasets/                 # non versionné (voir « Données »)
├── .github/workflows/ci.yml  # ruff + pytest à chaque push
├── src/ia_responsable/
│   ├── instance.py           # chargement d'une instance, contraintes actives
│   ├── fill.py               # Pool, fill, find_pair : composer une taille avec des datasets
│   ├── model.py              # modèle agrégé OR-Tools / SCIP
│   ├── packing.py            # attribution des datasets, appariement des sources
│   ├── repair.py             # State, complétion, réparation
│   ├── annealing.py          # recuit simulé (finition)
│   ├── pipeline.py           # enchaînement complet des étapes
│   └── cli.py                # ligne de commande, réglages par instance
├── notebooks/                # 07 à 16 : la démarche, étape par étape
├── solutions/                # meilleures solutions (*_main.json)
├── tests/                    # tests pytest
└── test_solution.py          # correcteur officiel du concours
```

## Installation et utilisation

Prérequis : Python 3.12+ et [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/ThGoncal/<nom-du-depot>.git
cd <nom-du-depot>
uv sync
```

Placez les fichiers d'instance dans `datasets/`, puis :

```bash
make solve DATASET=2_medium      # résout une instance (solutions/2_medium_main.json n'est remplacé que s'il est battu)
make score DATASET=2_medium      # vérifie la solution avec le correcteur officiel
make score-all                   # vérifie les 7 solutions
make test                        # lance les tests
make notebooks                   # exécute les notebooks (long)
```

### Reproductibilité

- Le solveur SCIP est déterministe à modèle et version identiques, **sauf quand il s'arrête sur une limite de temps** : ce qu'il explore en N minutes dépend de la vitesse de la machine. Sur `4_precise`, le résultat varie ainsi d'une vingtaine de points d'une exécution à l'autre.
- Les ordres d'attribution aléatoires utilisent une graine fixe.
- Sur `6_shortage`, SCIP met plusieurs minutes à résoudre la seule relaxation linéaire de départ. Avec 5 minutes, selon la vitesse de la machine, il peut ne pas avoir fini et rendre une très mauvaise solution. Le réglage par défaut est donc de 15 minutes (`--seconds` pour le changer).
- Les durées d'exécution vont de quelques secondes (`1_example`, `3_free`) à environ 25 minutes (`7_big`).

## Données

Les fichiers d'instance appartiennent aux organisateurs du concours et **ne sont pas inclus** dans ce dépôt. Le format attendu est décrit dans [`docs/enonce_fr.md`](docs/enonce_fr.md).

## Technologies

Python · OR-Tools (SCIP, CP-SAT) · SciPy (`linprog`) · pandas · NumPy · matplotlib · Jupyter · uv

## Auteur

**Thierry Goncalves Novo** : physicien de formation, géomaticien et data scientist, en reconversion vers l'ingénierie IA / MLOps.
[GitHub](https://github.com/ThGoncal)
