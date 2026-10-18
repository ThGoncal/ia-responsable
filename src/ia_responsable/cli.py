"""Ligne de commande : uv run python -m ia_responsable.cli --dataset 2_medium"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import sys
from pathlib import Path

from . import instance, pipeline

# Réglages qui ont donné les meilleurs résultats (notebooks 11 à 16)
PRESETS: dict[str, dict] = {
    "1_example": dict(seconds=10),
    "2_medium": dict(seconds=300),
    "3_free": dict(seconds=120),
    "4_precise": dict(seconds=900, n_noisy=40, n_finish=42, max_partners=None),
    "5_energy": dict(seconds=300, n_noisy=4),
    "6_shortage": dict(seconds=900, n_noisy=200, n_finish=5, total_margin=0.985, max_partners=None),
    "7_big": dict(seconds=600),
}


def official_score(root: Path, dataset_text: str, plan: dict) -> tuple[int, bool, str]:
    """Note un plan avec le correcteur officiel du concours (test_solution.py, à la racine du projet)."""
    spec = importlib.util.spec_from_file_location("test_solution", root / "test_solution.py")
    if spec is None or spec.loader is None:
        raise FileNotFoundError(f"test_solution.py introuvable dans {root}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.getSolutionScore(json.dumps(plan), dataset_text, show_details=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Résout une instance du concours « IA responsable ».")
    parser.add_argument("--dataset", required=True, help="nom de l'instance, par exemple 2_medium")
    parser.add_argument("--root", default=".", help="racine du projet (datasets/, solutions/, test_solution.py)")
    parser.add_argument("--seconds", type=float, help="limite de temps du solveur")
    parser.add_argument("--noisy", type=int, dest="n_noisy", help="nombre d'ordres d'attribution bruités")
    parser.add_argument("--finish", type=int, dest="n_finish", help="nombre d'attributions complétées et réparées")
    parser.add_argument("--margin", type=float, dest="total_margin", help="part de l'offre totale utilisable")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

    root = Path(args.root)
    inst = instance.load(root / "datasets" / f"{args.dataset}.json")
    options = PRESETS.get(args.dataset, {}).copy()
    options.update(
        {
            k: v
            for k, v in vars(args).items()
            if k in {"seconds", "n_noisy", "n_finish", "total_margin"} and v is not None
        }
    )
    logging.info("%s : %d modèles, %d datasets | %s", inst.name, len(inst.value), len(inst.size), options)

    plan, report = pipeline.run(inst, **options)
    score, valid, message = official_score(root, inst.text, plan)
    logging.info("score officiel : %s | valide : %s %s", f"{score:,}", valid, message)
    if not valid:
        return 1

    out_dir = root / "solutions"
    out_dir.mkdir(exist_ok=True)
    (out_dir / f"{inst.name}_last.json").write_text(json.dumps(plan))
    main_file = out_dir / f"{inst.name}_main.json"
    current = official_score(root, inst.text, json.loads(main_file.read_text()))[0] if main_file.exists() else 0
    if score > current:
        main_file.write_text(json.dumps(plan))
        logging.info("%s mis à jour : %s -> %s", main_file.name, f"{current:,}", f"{score:,}")
    else:
        logging.info("%s inchangé (%s)", main_file.name, f"{current:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
