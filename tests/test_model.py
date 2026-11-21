import pytest

from electoral import Config, ElectionModel


def test_deterministic_for_same_seed():
    a, b = ElectionModel(seed=7), ElectionModel(seed=7)
    a.run_to_end()
    b.run_to_end()
    assert a.log == b.log


def test_step_is_one_minute_and_log_is_ordered():
    m = ElectionModel(seed=3)
    m.step()
    assert m.clock == 1
    m.run_to_end()
    assert [e["seq"] for e in m.log] == list(range(1, len(m.log) + 1))
    assert all(a["t"] <= b["t"] for a, b in zip(m.log, m.log[1:], strict=False))
    assert not m.running


def test_events_since_never_misses():
    m = ElectionModel(seed=3)
    seen, seq = [], 0
    while m.running:
        m.step()
        new = m.events_since(seq)
        seen += new
        seq = m.last_seq
    assert seen == m.log


def test_every_voter_ends_in_a_terminal_state():
    m = ElectionModel(seed=11)
    m.run_to_end()
    assert all(v.location == "exited" for v in m.voters)
    r = m.results()
    assert sum(r["voters_by_state"].values()) == m.config.n_voters
    assert sum(r["votes"].values()) == r["voters_by_state"].get("finished", 0)


def test_resources_never_oversubscribed():
    m = ElectionModel(Config(p_earthquake_per_minute=0.01), seed=5)
    while m.running:
        m.step()
        s = m.snapshot()
        busy = [x["voter_id"] for x in s["verifiers"] + s["booths"] if x["voter_id"]]
        if s["urn"]["voter_id"]:
            busy.append(s["urn"]["voter_id"])
        queued = [i for q in s["queues"].values() for i in q]
        assert len(set(busy + queued)) == len(busy + queued)  # nobody in two places


def test_random_verifier_policy_runs():
    m = ElectionModel(Config(verifier_policy="random"), seed=9)
    m.run_to_end()
    used = {e["resource"] for e in m.log if e["type"] == "verification_started"}
    assert used == {0, 1, 2}


def test_config_validation():
    with pytest.raises(ValueError):
        Config.from_dict({"nope": 1})
    with pytest.raises(ValueError):
        Config.from_dict({"p_return": 2})
    assert Config.from_dict({"n_voters": 10, "booth_range": [2, 3]}).booth_range == (2, 3)
