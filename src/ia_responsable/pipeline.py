"""Pipeline complet : contrôle préalable -> SCIP -> attribution -> appariement -> complétion -> réparation."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from .fill import no_full_models
from .instance import Instance
from .model import SolverInfo, solve
from .packing import REFERENCE_ORDERS, Plan, noisy_orders, pack
from .repair import State, complete, repair

log = logging.getLogger(__name__)


def plan_value(inst: Instance, plan: Plan) -> int:
    """Valeur d'un plan selon les règles du concours (sans vérifier sa validité : voir test_solution.py)."""
    defiled: dict[int, int] = {}
    for d, m in plan["dataMappings"]:
        defiled[m] = defiled.get(m, 0) | inst.copyrighted[d]
    sources = {s for s, _ in plan["modelMappings"]}
    for _, m in plan["modelMappings"]:
        defiled[m] = 1
    return sum(inst.value[m] // 2 if dirty else inst.value[m] for m, dirty in defiled.items() if m not in sources)


@dataclass
class Report:
    solver: SolverInfo
    orders: list[dict] = field(default_factory=list)
    best_order: str = ""
    score: int = 0
    seconds: float = 0.0


def run(
    inst: Instance,
    seconds: float = 300,
    n_noisy: int = 0,
    n_finish: int = 2,
    total_margin: float = 1.0,
    max_partners: int | None = 20,
    possible_sources: bool | None = None,
    seed: int = 0,
) -> tuple[Plan, Report]:
    """Résout une instance.

    n_noisy : nombre d'ordres d'attribution bruités en plus des deux ordres de référence.
    n_finish : nombre de meilleures attributions que l'on complète et répare.
    max_partners : limite de la réparation (None = tous les partenaires, à éviter sur les grosses instances)."""
    t0 = time.time()
    no_full = no_full_models(inst)
    log.info("contrôle préalable : %d modèle(s) interdit(s) à pleine valeur", len(no_full))

    sel, info = solve(inst, seconds, possible_sources=possible_sources, total_margin=total_margin, no_full=no_full)
    log.info("SCIP %s : objectif %s, borne %.1f (%.0f s)", info.status, f"{info.objective:,}", info.bound, info.seconds)

    orders = dict(REFERENCE_ORDERS) | noisy_orders(inst, n_noisy, seed)
    packed = []
    for name, key in orders.items():
        plan, n_failed = pack(inst, sel, key)
        packed.append((plan_value(inst, plan), name, n_failed, plan))
    packed.sort(key=lambda r: -r[0])

    report = Report(solver=info)
    best: tuple[int, str, Plan] = (-1, "", {"dataMappings": [], "modelMappings": []})
    for value0, name, n_failed, plan in packed[:n_finish]:
        state = State(inst, plan, no_full)
        added = complete(state)
        n_rep = repair(state, max_partners)
        final = state.plan()
        value = plan_value(inst, final)
        report.orders.append(
            dict(ordre=name, ratés=n_failed, après_attribution=value0, ajouts=added, réparations=n_rep, score=value)
        )
        log.info("ordre %-16s : %s -> %s", name, f"{value0:,}", f"{value:,}")
        if value > best[0]:
            best = (value, name, final)

    report.score, report.best_order, report.seconds = best[0], best[1], time.time() - t0
    return best[2], report
