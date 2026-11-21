"""The Mesa model must reproduce the teacher's script exactly for the same seed."""

import contextlib
import io
import random
from pathlib import Path

import pytest

from electoral import Config, ElectionModel

BASELINE = Path(__file__).resolve().parent.parent / "proceso_electoral-1.py"

# Event types the baseline prints (the model logs a few more, for the frontend)
PRINTED = {
    "voter_turned_away",
    "voter_abandoned",
    "queue_joined",
    "verification_started",
    "document_invalid",
    "booth_started",
    "urn_started",
    "voter_finished",
    "earthquake",
    "voter_evacuated",
    "station_reopened",
}


class FixedRandom(random.Random):
    def __init__(self, seed):
        super().__init__(seed)
        self._locked = True

    def seed(self, *args, **kwargs):  # the baseline calls random.seed() at import: ignore it
        if not getattr(self, "_locked", False):
            super().seed(*args, **kwargs)


def run_baseline(seed: int, p_quake: float):
    src = BASELINE.read_text()
    assert "PROB_SISMO_POR_MINUTO = 0.0002" in src
    src = src.replace("PROB_SISMO_POR_MINUTO = 0.0002", f"PROB_SISMO_POR_MINUTO = {p_quake}")
    rng = FixedRandom(seed)
    ns = {"__name__": "baseline"}
    # The baseline does `import random`; make that resolve to our seeded generator
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        return rng if name == "random" else real_import(name, *a, **k)

    out = io.StringIO()
    builtins.__import__ = fake_import
    try:
        with contextlib.redirect_stdout(out):
            exec(compile(src, str(BASELINE), "exec"), ns)
    finally:
        builtins.__import__ = real_import
    text = out.getvalue()
    events, _, results = text.partition("\nRESULTADOS")
    return events.strip("\n").splitlines(), results, ns


def model_lines(model):
    lines = []
    for e in model.log:
        if e["type"] not in PRINTED:
            continue
        if e["type"] == "queue_joined" and e["queue"] != "verification":
            continue
        lines.append(f"{e['t']:3} | {e['message']}")
    return lines


@pytest.mark.parametrize("seed", [1, 2, 3, 42, 2026])
@pytest.mark.parametrize("p_quake", [0.0, 0.01])
def test_same_run_as_baseline(seed, p_quake):
    base_lines, _, ns = run_baseline(seed, p_quake)

    model = ElectionModel(Config(p_earthquake_per_minute=p_quake), seed=seed)
    model.run_to_end()

    assert model_lines(model) == base_lines

    # Final results agree too
    base_votes = {p: sum(1 for v in ns["votantes"] if v.partido == p) for p in ns["partidos"]}
    assert model.results()["votes"] == base_votes
    base_avg = sum(v.salida - v.llegada for v in ns["votantes"]) / ns["N"]
    assert model.results()["average_minutes_all"] == pytest.approx(base_avg)


def test_earthquake_path_is_exercised():
    # Guard against the parametrisation silently never triggering an earthquake
    model = ElectionModel(Config(p_earthquake_per_minute=0.01), seed=1)
    model.run_to_end()
    assert any(e["type"] == "earthquake" for e in model.log)
