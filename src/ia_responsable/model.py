"""Modèle agrégé, résolu par SCIP via OR-Tools (notebooks 11 à 16).

Variables (binaires) :
- x[i] : modèle i à pleine valeur (données libres uniquement) ;
- y[i] : modèle i à demi-valeur ;
- w[s] : modèle s (un seul besoin) utilisé comme source ;
- c[i,t] : besoin t du modèle i couvert par une source (c[i,t] <= y[i]).

Les sources d'un même type sont interchangeables : on compte, par type, autant de besoins couverts que de
sources, et on apparie après la résolution (notebook 14)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from ortools.linear_solver import pywraplp

from .instance import TYPES, Instance

ENERGY_SCALE = 1e9  # énergie en milliards : coefficients ~10^3 au lieu de ~10^12 (notebooks 13 et 14)


@dataclass
class Selection:
    full: list[int] = field(default_factory=list)
    half: list[int] = field(default_factory=list)
    sources: list[int] = field(default_factory=list)
    covered: list[tuple[int, str]] = field(default_factory=list)


@dataclass
class SolverInfo:
    status: str
    objective: int
    bound: float
    seconds: float

    @property
    def gap(self) -> float:
        return self.bound - self.objective


def solve(
    inst: Instance,
    seconds: float = 300,
    possible_sources: bool | None = None,
    total_margin: float = 1.0,
    no_full: set[int] = frozenset(),
    force_energy_constraint: bool = False,
) -> tuple[Selection, SolverInfo]:
    """Construit et résout le modèle agrégé.

    possible_sources : autoriser les sources sur les besoins remplissables. None = automatique, vrai si les
    données manquent (inst.data_is_scarce).
    total_margin : part de l'offre totale utilisable, pour absorber le gaspillage de l'attribution (notebook 15).
    no_full : modèles interdits à pleine valeur.
    force_energy_constraint : écrire la contrainte d'énergie même si elle est redondante (démonstration du
    piège numérique, notebook 14)."""
    if possible_sources is None:
        possible_sources = inst.data_is_scarce
    t0 = time.time()
    S = pywraplp.Solver.CreateSolver("SCIP")
    models = list(inst.value)
    x = {m: S.BoolVar(f"x{m}") for m in models if m not in inst.impossible and m not in no_full}
    y = {m: S.BoolVar(f"y{m}") for m in models}
    w = {s: S.BoolVar(f"w{s}") for s in inst.mono}
    c = {}
    for m, needs in inst.needs.items():
        for t, lo, hi in needs:
            if lo > hi:
                c[(m, t)] = y[m]  # besoin impossible : forcément une source
            elif possible_sources:
                c[(m, t)] = S.BoolVar(f"c{m}_{t}")
                S.Add(c[(m, t)] <= y[m])

    for m in models:  # un seul rôle par modèle
        S.Add((x[m] if m in x else 0) + y[m] + (w[m] if m in w else 0) <= 1)

    # Une contrainte redondante, avec des coefficients énormes, peut fausser le solveur (notebook 14)
    if inst.energy_is_binding or force_energy_constraint:
        E = ENERGY_SCALE
        S.Add(
            sum(inst.energy[m] / E * x[m] for m in x)
            + sum(inst.energy[m] / E * y[m] for m in y)
            + sum(inst.energy[s] / E * w[s] for s in w)
            <= inst.energy_cap / E
        )

    for t in TYPES:
        # Autant de besoins couverts que de sources. Écrite même si la somme est vide (notebook 13).
        S.Add(sum(v for (m, tt), v in c.items() if tt == t) == sum(w[s] for s in w if inst.mono[s] == t))
        S.Add(sum(inst.lower[m][t] * x[m] for m in x if t in inst.lower[m]) <= inst.free_supply[t])
        S.Add(
            sum(inst.lower[m][t] * x[m] for m in x if t in inst.lower[m])
            + sum(inst.lower[m][t] * (y[m] - c.get((m, t), 0)) for m in y if t in inst.lower[m])
            + sum(inst.lower[s][t] * w[s] for s in w if inst.mono[s] == t)
            <= inst.total_supply[t] * total_margin
        )

    S.Maximize(sum(inst.value[m] * x[m] for m in x) + sum((inst.value[m] // 2) * y[m] for m in y))
    S.SetTimeLimit(int(seconds * 1000))
    params = pywraplp.MPSolverParameters()
    params.SetDoubleParam(params.RELATIVE_MIP_GAP, 0.0)  # tolérance d'arrêt nulle (notebook 12)
    status = S.Solve(params)

    def val(v) -> int:
        return round(v.solution_value())

    sel = Selection(
        full=[m for m in x if val(x[m])],
        half=[m for m in y if val(y[m])],
        sources=[s for s in w if val(w[s])],
        covered=[(m, t) for (m, t), v in c.items() if val(v)],
    )
    used = sum(inst.energy[m] for m in sel.full + sel.half + sel.sources)
    if used > inst.energy_cap:
        raise RuntimeError(f"énergie exacte dépassée : {used} > {inst.energy_cap}")
    info = SolverInfo(
        status="OPTIMAL" if status == pywraplp.Solver.OPTIMAL else "FEASIBLE",
        objective=round(S.Objective().Value()),
        bound=S.Objective().BestBound(),
        seconds=time.time() - t0,
    )
    return sel, info
