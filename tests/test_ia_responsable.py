"""Tests rapides (quelques secondes). Les instances du concours ne sont pas versionnées :
les tests qui en ont besoin sont ignorés si le fichier manque."""

import json
from pathlib import Path

import pytest

from ia_responsable import instance
from ia_responsable.cli import official_score
from ia_responsable.fill import Pool, fill, find_pair
from ia_responsable.packing import REFERENCE_ORDERS, pack
from ia_responsable.pipeline import plan_value, run
from ia_responsable.repair import State, complete, repair

ROOT = Path(__file__).resolve().parents[1]
DATASETS = ROOT / "datasets"
ALL = ["1_example", "2_medium", "3_free", "4_precise", "5_energy", "6_shortage", "7_big"]


def needs_dataset(name):
    return pytest.mark.skipif(not (DATASETS / f"{name}.json").exists(), reason=f"datasets/{name}.json absent")


# --- fill : composer une taille avec des datasets -------------------------------------------------------------


def make_pool(sizes):
    size = dict(enumerate(sizes))
    return Pool(size.keys(), size), size


def test_find_pair_returns_smallest_sum_in_window():
    sizes = [1, 3, 4, 7, 9]
    s, i, j = find_pair(sizes, 10, 11)
    assert s == 10 and sizes[i] + sizes[j] == 10


def test_fill_respects_bounds_and_takes_datasets():
    pool, size = make_pool([4000, 5000, 6000, 9000])
    got = fill(pool, 10_000, 10_000)
    assert sum(size[d] for d in got) == 10_000
    assert len(pool.ids) == 4 - len(got)


def test_fill_failure_leaves_pool_untouched():
    pool, _ = make_pool([10, 20, 30])
    before = list(pool.ids)
    assert fill(pool, 1000, 1100) is None
    assert pool.ids == before


# --- instance --------------------------------------------------------------------------------------------------


@needs_dataset("1_example")
def test_load_example():
    inst = instance.load(DATASETS / "1_example.json")
    assert len(inst.value) == 5 and len(inst.size) == 5
    assert inst.energy_is_binding
    assert set(inst.mono) == {0, 2, 3, 4}


# --- solutions publiées : elles doivent rester valides --------------------------------------------------------


@pytest.mark.parametrize("name", ALL)
def test_published_solution_is_valid(name):
    if not (DATASETS / f"{name}.json").exists():
        pytest.skip(f"datasets/{name}.json absent")
    plan = json.loads((ROOT / "solutions" / f"{name}_main.json").read_text())
    inst = instance.load(DATASETS / f"{name}.json")
    score, valid, message = official_score(ROOT, inst.text, plan)
    assert valid, message
    assert plan_value(inst, plan) == score  # notre calcul de valeur coïncide avec le correcteur officiel


# --- pipeline complet ------------------------------------------------------------------------------------------


@needs_dataset("1_example")
def test_pipeline_finds_optimum_on_example():
    inst = instance.load(DATASETS / "1_example.json")
    plan, report = run(inst, seconds=10)
    score, valid, _ = official_score(ROOT, inst.text, plan)
    assert valid and score == 12_946


@needs_dataset("2_medium")
def test_pack_and_repair_produce_valid_plan_on_medium():
    from ia_responsable.model import solve

    inst = instance.load(DATASETS / "2_medium.json")
    sel, info = solve(inst, seconds=20)
    plan, _ = pack(inst, sel, REFERENCE_ORDERS["plus contraints"])
    state = State(inst, plan)
    complete(state)
    repair(state)
    final = state.plan()
    score, valid, message = official_score(ROOT, inst.text, final)
    assert valid, message
    assert state.score == score  # le score tenu à jour par State est exact
    assert score > 270_000
