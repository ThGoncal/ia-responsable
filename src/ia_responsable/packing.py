"""Attribution des datasets à une sélection, et appariement des sources (notebooks 12 à 15)."""

from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Callable

from .fill import give, new_pools
from .instance import Instance
from .model import Selection

Plan = dict[str, list[list[int]]]
OrderKey = Callable[[int, list], object]


def small_needs_first(m: int, needs: list) -> object:
    return sum(lo for _, lo, _ in needs)


def most_constrained_first(m: int, needs: list) -> object:
    """Servir d'abord ceux qui ont le moins de choix : borne haute la plus petite (notebook 12)."""
    return (min((hi for _, _, hi in needs), default=0), sum(lo for _, lo, _ in needs))


def noisy_orders(inst: Instance, n: int, seed: int = 0, spread: float = 0.2) -> dict[str, OrderKey]:
    """n ordres « petits besoins d'abord » bruités de ±spread : recherche à départs multiples (notebook 13)."""
    rng = random.Random(seed)
    orders = {}
    for k in range(n):
        noise = {m: rng.uniform(1 - spread, 1 + spread) for m in inst.value}
        orders[f"bruité {k}"] = lambda m, needs, nz=noise: sum(lo for _, lo, _ in needs) * nz[m]
    return orders


REFERENCE_ORDERS: dict[str, OrderKey] = {
    "petits besoins": small_needs_first,
    "plus contraints": most_constrained_first,
}


def pack(inst: Instance, sel: Selection, order_key: OrderKey) -> tuple[Plan, int]:
    """Attribue les datasets dans une file unique triée par order_key. Rend (plan, nombre d'échecs)."""
    pools = new_pools(inst)
    covered = defaultdict(set)
    for m, t in sel.covered:
        covered[m].add(t)
    jobs = [(m, inst.needs[m], (0,), "plein") for m in sel.full]
    jobs += [(m, [n for n in inst.needs[m] if n[0] not in covered[m]], (1, 0), "demi") for m in sel.half]
    jobs += [(s, inst.needs[s], (1, 0), "source") for s in sel.sources]

    data: dict[int, list[int]] = {}
    failed = []
    for m, needs, statuses, kind in sorted(jobs, key=lambda j: order_key(j[0], j[1])):
        got = give(inst, pools, needs, statuses)
        if got is None:
            failed.append((m, kind))
        else:
            data[m] = got
    for m, kind in failed:  # seconde chance à demi-valeur pour les modèles pleins
        if kind == "plein":
            got = give(inst, pools, inst.needs[m], (1, 0))
            if got is not None:
                data[m] = got

    # Appariement sources -> besoins couverts, type par type
    available = defaultdict(list)
    for s in sel.sources:
        if s in data:
            available[inst.mono[s]].append(s)
    model_mappings = []
    for m in sel.half:
        if m not in data:
            continue
        pairs = []
        for t in covered[m]:
            if available[t]:
                pairs.append((available[t].pop(), m))
        if len(pairs) == len(covered[m]):
            model_mappings += pairs
        else:  # cible incomplète : on la retire, une cible mal servie invaliderait tout (notebook 12)
            for s, _ in pairs:
                available[inst.mono[s]].append(s)
            data.pop(m)
    for unused in available.values():  # sources sans cible : on les retire
        for s in unused:
            data.pop(s)

    plan = {
        "dataMappings": [[int(d), int(m)] for m, ds in data.items() for d in ds],
        "modelMappings": [[int(s), int(m)] for s, m in model_mappings],
    }
    return plan, len(failed)
