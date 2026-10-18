"""Solution modifiable, complétion et réparation (notebooks 10, 11, 14 et 15)."""

from __future__ import annotations

from .fill import give, new_pools
from .instance import Instance
from .packing import Plan


class State:
    """Solution modifiable avec journal d'annulation. Les sources et leurs cibles sont gelées."""

    def __init__(self, inst: Instance, plan: Plan, no_full: set[int] = frozenset()):
        self.inst = inst
        self.no_full = no_full
        self.frozen = {x for pair in plan["modelMappings"] for x in pair}
        self.frozen_data = [p for p in plan["dataMappings"] if p[1] in self.frozen]
        self.frozen_sources = plan["modelMappings"]
        self.data: dict[int, list[int]] = {}
        for d, m in plan["dataMappings"]:
            if m not in self.frozen:
                self.data.setdefault(m, []).append(d)
        self.pools = new_pools(inst, exclude={d for d, _ in plan["dataMappings"]})
        self.full = {m: not any(inst.copyrighted[d] for d in ds) for m, ds in self.data.items()}
        self.energy = sum(inst.energy[m] for m in self.data) + sum(inst.energy[m] for m in self.frozen)
        # Une cible peut avoir plusieurs sources : on compte chaque cible une seule fois.
        targets = {m for _, m in self.frozen_sources}
        self.score = sum(self.value(m) for m in self.data) + sum(inst.value[m] // 2 for m in targets)
        self.log: list = []

    def value(self, m: int) -> int:
        return self.inst.value[m] if self.full[m] else self.inst.value[m] // 2

    def _put_back(self, ds: list[int]) -> None:
        for d in ds:
            self.pools[(self.inst.dtype[d], self.inst.copyrighted[d])].put(d)

    def remove(self, m: int) -> None:
        self.score -= self.value(m)
        ds, full = self.data.pop(m), self.full.pop(m)
        self._put_back(ds)
        self.energy -= self.inst.energy[m]
        self.log.append(("remove", m, ds, full))

    def add(self, m: int, statuses: tuple[int, ...]) -> bool:
        if self.energy + self.inst.energy[m] > self.inst.energy_cap:
            return False
        if statuses == (0,) and m in self.no_full:
            return False
        got = give(self.inst, self.pools, self.inst.needs[m], statuses)
        if got is None:
            return False
        self.data[m] = got
        self.full[m] = not any(self.inst.copyrighted[d] for d in got)
        self.energy += self.inst.energy[m]
        self.score += self.value(m)
        self.log.append(("add", m, None, None))
        return True

    def undo(self) -> None:
        """Annule tout le journal, du plus récent au plus ancien."""
        while self.log:
            op, m, ds, full = self.log.pop()
            if op == "add":
                self.score -= self.value(m)
                self._put_back(self.data.pop(m))
                self.full.pop(m)
                self.energy -= self.inst.energy[m]
            else:
                for d in ds:
                    self.pools[(self.inst.dtype[d], self.inst.copyrighted[d])].remove(d)
                self.data[m], self.full[m] = ds, full
                self.energy += self.inst.energy[m]
                self.score += self.value(m)

    def plan(self) -> Plan:
        mappings = [[int(d), int(m)] for m, ds in self.data.items() for d in ds] + self.frozen_data
        return {"dataMappings": mappings, "modelMappings": self.frozen_sources}


def complete(s: State) -> int:
    """Ajoute des modèles non choisis avec les datasets restants, par valeur par unité de donnée décroissante."""
    inst = s.inst
    candidates = [m for m in inst.value if m not in s.data and m not in s.frozen and m not in inst.impossible]
    candidates.sort(key=lambda m: -inst.value[m] / max(1, sum(inst.lower[m].values())))
    added = 0
    for m in candidates:
        s.log = []
        if s.add(m, (0,)) or s.add(m, (1, 0)):
            added += 1
    return added


def repair(s: State, max_partners: int | None = 20) -> int:
    """Passe des modèles à demi-valeur à pleine valeur, directement ou en échangeant les données libres
    avec un modèle plein moins précieux qui partage un type (notebooks 11 et 13)."""
    inst = s.inst
    types_of = {m: {t for t, _, _ in needs} for m, needs in inst.needs.items()}

    def gain(m: int) -> int:
        return inst.value[m] - inst.value[m] // 2

    n_repairs, improved = 0, True
    while improved:
        improved = False
        for b in sorted([m for m in s.data if not s.full[m]], key=gain, reverse=True):
            if b not in s.data or s.full[b]:
                continue
            s.log = []
            s.remove(b)
            if s.add(b, (0,)):
                n_repairs += 1
                improved = True
                continue
            s.undo()
            partners = sorted(
                (a for a in s.data if s.full[a] and types_of[a] & types_of[b] and gain(a) < gain(b)), key=gain
            )
            for a in partners[:max_partners]:
                s.log = []
                s.remove(a)
                s.remove(b)
                if s.add(b, (0,)) and s.add(a, (1, 0)):
                    n_repairs += 1
                    improved = True
                    break
                s.undo()
    return n_repairs
