"""Composer une taille de données avec des datasets (notebooks 09, 11 et 13)."""

from __future__ import annotations

import bisect
from collections.abc import Iterable

from .instance import TYPES, Instance


class Pool:
    """Réserve de datasets d'un type et d'un statut, triée par taille.

    Le tri permet de chercher par dichotomie (bisect) : quelques comparaisons au lieu d'un parcours complet."""

    def __init__(self, ids: Iterable[int], size: dict[int, int]):
        self._size = size
        self.ids = sorted(ids, key=size.__getitem__)
        self.sizes = [size[d] for d in self.ids]

    def take(self, i: int) -> int:
        self.sizes.pop(i)
        return self.ids.pop(i)

    def put(self, d: int) -> None:
        i = bisect.bisect_left(self.sizes, self._size[d])
        self.sizes.insert(i, self._size[d])
        self.ids.insert(i, d)

    def remove(self, d: int) -> None:
        """Retire le dataset d (utilisé pour annuler un mouvement)."""
        i = bisect.bisect_left(self.sizes, self._size[d])
        while self.ids[i] != d:
            i += 1
        self.take(i)


Pools = dict[tuple[str, int], Pool]


def new_pools(inst: Instance, exclude: set[int] = frozenset()) -> Pools:
    """Une réserve par (type, sous droits) : ('n', 0) = datasets n libres, ('n', 1) = sous droits."""
    by_key: dict[tuple[str, int], list[int]] = {(t, c): [] for t in TYPES for c in (0, 1)}
    for d in inst.size:
        if d not in exclude:
            by_key[(inst.dtype[d], inst.copyrighted[d])].append(d)
    return {key: Pool(ids, inst.size) for key, ids in by_key.items()}


def find_pair(sizes: list[int], a: int, b: int) -> tuple[int, int, int] | None:
    """Deux positions i < j avec sizes[i] + sizes[j] dans [a, b], somme la plus petite. Deux pointeurs : O(n)."""
    i, j, best = 0, bisect.bisect_right(sizes, b) - 1, None
    while i < j:
        s = sizes[i] + sizes[j]
        if s > b:
            j -= 1
        elif s < a:
            i += 1
        else:
            if best is None or s < best[0]:
                best = (s, i, j)
            j -= 1
    return best


def fill(pool: Pool, lower: int, upper: int) -> list[int] | None:
    """Prend des datasets dont la somme tombe dans [lower, upper]. Rend la liste, ou None (rien n'est pris).

    1. un dataset termine le remplissage : on prend le plus petit ;
    2. sinon, une paire le termine : on prend celle de plus petite somme ;
    3. sinon, on prend le plus gros qui rentre, et on recommence."""
    taken: list[int] = []
    total = 0
    while total < lower:
        a, b = lower - total, upper - total
        i = bisect.bisect_left(pool.sizes, a)
        if i < len(pool.sizes) and pool.sizes[i] <= b:
            total += pool.sizes[i]
            taken.append(pool.take(i))
            continue
        pair = find_pair(pool.sizes, a, b) if pool.sizes and a <= 2 * pool.sizes[-1] else None
        if pair:
            _, i, j = pair
            total += pool.sizes[i] + pool.sizes[j]
            taken.append(pool.take(j))
            taken.append(pool.take(i))
            continue
        j = bisect.bisect_right(pool.sizes, b) - 1
        if j < 0:
            break
        total += pool.sizes[j]
        taken.append(pool.take(j))
    if lower <= total <= upper:
        return taken
    for d in taken:
        pool.put(d)
    return None


def fill_mixed(inst: Instance, pools: list[Pool], lower: int, upper: int) -> list[int] | None:
    """Remplit un besoin en mélangeant plusieurs réserves (libres et sous droits).

    Utile pour un modèle à demi-valeur : il peut combiner les deux statuts dans un même besoin. Les notebooks ne le
    faisaient pas ; c'est un test sur 1_example qui l'a révélé (le modèle 1 a besoin d'un dataset de chaque)."""
    owner = {d: p for p in pools for d in p.ids}
    got = fill(Pool(owner, inst.size), lower, upper)
    if got is None:
        return None
    for d in got:
        owner[d].remove(d)
    return got


def give(inst: Instance, pools: Pools, needs: list, statuses: tuple[int, ...]) -> list[int] | None:
    """Remplit tous les besoins donnés. statuses : (0,) = libre seulement ; (1, 0) = sous droits d'abord.

    Rend la liste des datasets, ou None : dans ce cas, tout ce qui avait été pris est rendu."""
    got: list[int] = []
    for t, lo, hi in needs:
        res = None
        for s in statuses:
            res = fill(pools[(t, s)], lo, hi)
            if res is not None:
                break
        if res is None and len(statuses) > 1:
            res = fill_mixed(inst, [pools[(t, s)] for s in statuses], lo, hi)
        if res is None:
            for d in got:
                pools[(inst.dtype[d], inst.copyrighted[d])].put(d)
            return None
        got += res
    return got


def no_full_models(inst: Instance) -> set[int]:
    """Modèles dont un besoin ne peut pas être rempli en données libres seules (notebook 15)."""
    pools = new_pools(inst)
    result = set()
    for m, needs in inst.needs.items():
        for t, lo, hi in needs:
            if lo <= hi:
                got = fill(pools[(t, 0)], lo, hi)
                if got is None:
                    result.add(m)
                else:
                    for d in got:
                        pools[(t, 0)].put(d)
    return result
