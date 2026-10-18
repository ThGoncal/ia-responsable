"""Recuit simulé en finition, à partir d'une solution existante (notebook 10).

Critère de Metropolis : un mouvement qui fait perdre delta points est accepté avec la probabilité exp(-delta / T).
À T -> 0, le recuit devient une descente (on n'accepte que les gains)."""

from __future__ import annotations

import math
import random

from .instance import Instance
from .packing import Plan
from .repair import State


def _move_upgrade(s: State, rng: random.Random) -> bool:
    """Un modèle à demi-valeur passe à pleine valeur, s'il reste des données libres."""
    halves = [m for m in s.data if not s.full[m]]
    if not halves:
        return False
    b = rng.choice(halves)
    s.remove(b)
    return s.add(b, (0,))


def _move_exchange(s: State, rng: random.Random) -> bool:
    """Un modèle plein cède ses données libres à un modèle à demi-valeur qui partage un type."""
    halves = [m for m in s.data if not s.full[m]]
    if not halves:
        return False
    b = rng.choice(halves)
    types_b = {t for t, _, _ in s.inst.needs[b]}
    fulls = [m for m in s.data if s.full[m] and types_b & {t for t, _, _ in s.inst.needs[m]}]
    if not fulls:
        return False
    a = rng.choice(fulls)
    s.remove(a)
    s.remove(b)
    return s.add(b, (0,)) and s.add(a, (1, 0))


def _move_ruin(s: State, rng: random.Random, candidates: list[int], k: int = 2, tries: int = 80) -> bool:
    """Ruiner et recréer : on retire k modèles, puis on comble avec des candidats absents."""
    if len(s.data) < k:
        return False
    for m in rng.sample(list(s.data), k):
        s.remove(m)
    absent = [m for m in candidates if m not in s.data and m not in s.frozen]
    inst = s.inst
    for m in sorted(rng.sample(absent, min(tries, len(absent))), key=lambda m: -inst.value[m] / inst.energy[m]):
        if s.energy + inst.energy[m] <= inst.energy_cap:
            s.add(m, (0,)) or s.add(m, (1, 0))
    return True


def anneal(
    inst: Instance,
    plan: Plan,
    n_iter: int = 20_000,
    t_start: float = 0.01,
    t_end: float = 0.001,
    seed: int = 0,
    no_full: set[int] = frozenset(),
) -> tuple[Plan, int]:
    """Recuit depuis `plan`. Par défaut T quasi nulle : sur nos instances, la descente fait au moins aussi bien."""
    rng = random.Random(seed)
    s = State(inst, plan, no_full)
    candidates = sorted(
        (m for m in inst.value if m not in inst.impossible), key=lambda m: -(inst.value[m] // 2) / inst.energy[m]
    )[: max(1500, 2 * len(s.data))]
    moves = [
        (_move_upgrade, 0.2),
        (_move_exchange, 0.4),
        (lambda s_, r: _move_ruin(s_, r, candidates), 0.4),
    ]
    funcs, weights = [f for f, _ in moves], [w for _, w in moves]
    best_score, best_plan = s.score, s.plan()
    for it in range(n_iter):
        T = t_start * (t_end / t_start) ** (it / n_iter)
        s.log = []
        before = s.score
        ok = rng.choices(funcs, weights)[0](s, rng)
        delta = s.score - before
        if ok and (delta >= 0 or rng.random() < math.exp(delta / T)):
            if s.score > best_score:
                best_score, best_plan = s.score, s.plan()
        else:
            s.undo()
    return best_plan, best_score
