"""Polling-station model.

Design: the teacher's discrete-event logic (heapq of timestamped events, integer minutes) lives
inside a Mesa ``Model``. One ``step()`` advances the clock one minute and processes every event
due in that minute, so the Mesa step is the simulation tick and the logic matches the baseline
exactly (same RNG draw order, so a given seed gives the same run).

Every relevant state change is appended to ``model.log`` with a monotonically increasing ``seq``,
so a polling client can ask "what happened after seq N" and never miss a transient change.
"""

import heapq
import random
from collections import deque

import mesa

from . import agents as A
from .agents import Voter
from .config import Config


class ElectionModel(mesa.Model):
    def __init__(self, config: Config | None = None, seed: int | None = None):
        if seed is None:
            seed = random.SystemRandom().randrange(2**32)
        super().__init__(rng=seed)
        self.seed = seed
        self.config = config or Config()
        self.config.validate()

        self.clock = 0
        self.running = True
        self.station_open = True
        self.log: list[dict] = []

        self._heap: list[tuple] = []
        self._counter = 0

        self.verifiers: list[Voter | None] = [None] * self.config.n_verifiers
        self.booths: list[Voter | None] = [None] * self.config.n_booths
        self.urn_voter: Voter | None = None
        self.queues = {"verification": deque(), "booth": deque(), "urn": deque()}

        self.voters = [Voter(self, i + 1) for i in range(self.config.n_voters)]
        self._schedule_arrivals_and_earthquake()

    # ------------------------------------------------------------------ scheduling

    def _schedule(self, t, kind, voter=None, resource=-1):
        self._counter += 1
        if voter is not None:
            voter.event_token = self._counter
        heapq.heappush(self._heap, (t, self._counter, kind, voter, resource))

    def _schedule_arrivals_and_earthquake(self):
        cfg = self.config
        t = 0
        for v in self.voters:
            t += self.random.randint(*cfg.arrival_range)
            self._schedule(t, "arrival", v)
        # At most one earthquake: tested once per minute of the working day
        for minute in range(1, t + 60 + 1):
            if self.random.random() < cfg.p_earthquake_per_minute:
                self._schedule(minute, "earthquake")
                break

    # ------------------------------------------------------------------ log

    def _emit(self, t, kind, message, voter=None, **extra):
        entry = {
            "seq": len(self.log) + 1,
            "t": t,
            "type": kind,
            "voter_id": voter.voter_id if voter else None,
            **extra,
            "message": message,
        }
        self.log.append(entry)

    def events_since(self, seq: int = 0) -> list[dict]:
        return self.log[seq:]

    @property
    def last_seq(self) -> int:
        return len(self.log)

    # ------------------------------------------------------------------ clock

    def step(self):
        """Advance one simulated minute."""
        if not self.running:
            return
        self.clock += 1
        while self._heap and self._heap[0][0] <= self.clock:
            t, event_id, kind, voter, resource = heapq.heappop(self._heap)
            if voter is not None and voter.event_token != event_id:
                continue  # stale: the voter was evacuated after this was scheduled
            getattr(self, f"_on_{kind}")(t, voter, resource)
        if not self._heap:
            self.running = False

    def run_to_end(self):
        while self.running:
            self.step()

    # ------------------------------------------------------------------ event handlers

    def _on_arrival(self, t, voter, _):
        voter.arrival = t
        self._emit(t, "voter_arrived", f"Votante {voter.voter_id:02d} llega", voter)

        if not self.station_open:
            voter.state = A.ABANDONED
            voter.exit_time = t
            self._emit(
                t,
                "voter_turned_away",
                f"Votante {voter.voter_id:02d} encuentra la casilla cerrada por el sismo y se va",
                voter,
            )
            return

        if not voter.decide_to_queue(len(self.queues["verification"])):
            voter.state = A.ABANDONED
            voter.exit_time = t
            self._emit(
                t,
                "voter_abandoned",
                f"Votante {voter.voter_id:02d} decide abandonar la casilla",
                voter,
            )
            return

        self._join_verification_queue(t, voter, "decide formarse")

    def _join_verification_queue(self, t, voter, text):
        voter.state = A.WAITING_VERIFICATION
        self.queues["verification"].append(voter)
        self._emit(
            t, "queue_joined", f"Votante {voter.voter_id:02d} {text}", voter, queue="verification"
        )
        self._start_verifications(t)

    def _on_verification_done(self, t, voter, slot):
        self.verifiers[slot] = None
        voter.slot = None
        voter.state = A.WAITING_BOOTH
        self.queues["booth"].append(voter)
        self._emit(
            t,
            "verification_finished",
            f"Votante {voter.voter_id:02d} termina verificación {slot + 1}",
            voter,
            resource=slot,
        )
        self._emit(
            t,
            "queue_joined",
            f"Votante {voter.voter_id:02d} pasa a la fila de mamparas",
            voter,
            queue="booth",
        )
        self._start_verifications(t)
        self._start_booths(t)

    def _on_booth_done(self, t, voter, slot):
        self.booths[slot] = None
        voter.slot = None
        voter.state = A.WAITING_URN
        self.queues["urn"].append(voter)
        self._emit(
            t,
            "booth_finished",
            f"Votante {voter.voter_id:02d} termina mampara {slot + 1}",
            voter,
            resource=slot,
        )
        self._emit(
            t,
            "queue_joined",
            f"Votante {voter.voter_id:02d} pasa a la fila de la urna",
            voter,
            queue="urn",
        )
        self._start_urn(t)
        self._start_booths(t)

    def _on_urn_done(self, t, voter, _):
        self.urn_voter = None
        voter.state = A.FINISHED
        voter.exit_time = t
        self._emit(t, "voter_finished", f"Votante {voter.voter_id:02d} sale de la casilla", voter)
        self._start_urn(t)

    # --- resource assignment

    def _start_verifications(self, t):
        cfg = self.config
        while self.queues["verification"]:
            free = [i for i, v in enumerate(self.verifiers) if v is None]
            if not free:
                return
            i = free[0] if cfg.verifier_policy == "first" else self.random.choice(free)
            voter = self.queues["verification"].popleft()
            self.verifiers[i] = voter
            voter.slot = i
            voter.state = A.VERIFYING
            self._schedule(
                t + self.random.randint(*cfg.verification_range), "verification_done", voter, i
            )
            self._emit(
                t,
                "verification_started",
                f"Votante {voter.voter_id:02d} inicia verificación {i + 1}",
                voter,
                resource=i,
            )

    def _start_booths(self, t):
        cfg = self.config
        while self.queues["booth"] and None in self.booths:
            voter = self.queues["booth"].popleft()
            # Baseline: the document is checked when a booth is available for the voter
            if not voter.document_is_valid():
                voter.state = A.INVALID_DOCUMENT
                voter.exit_time = t
                self._emit(
                    t,
                    "document_invalid",
                    f"Votante {voter.voter_id:02d} tiene documento inválido y abandona la casilla",
                    voter,
                )
                continue
            i = self.booths.index(None)
            self.booths[i] = voter
            voter.slot = i
            voter.state = A.IN_BOOTH
            self._schedule(t + self.random.randint(*cfg.booth_range), "booth_done", voter, i)
            self._emit(
                t,
                "booth_started",
                f"Votante {voter.voter_id:02d} inicia mampara {i + 1}",
                voter,
                resource=i,
            )

    def _start_urn(self, t):
        if self.urn_voter is None and self.queues["urn"]:
            voter = self.queues["urn"].popleft()
            self.urn_voter = voter
            voter.state = A.AT_URN
            self._schedule(t + self.random.randint(*self.config.urn_range), "urn_done", voter, 1)
            voter.choose_party()  # vote recorded when the voter starts at the urn (baseline)
            self._emit(t, "urn_started", f"Votante {voter.voter_id:02d} inicia casilla", voter)

    # --- earthquake

    def _on_earthquake(self, t, _voter, _):
        cfg = self.config
        self.station_open = False
        affected = [v for v in self.voters if v.state in A.IN_STATION]
        self._emit(
            t,
            "earthquake",
            f"*** SISMO *** la casilla se evacúa ({len(affected)} votantes dentro)",
            affected_voters=[v.voter_id for v in affected],
        )

        for q in self.queues.values():
            q.clear()
        self.verifiers = [None] * cfg.n_verifiers
        self.booths = [None] * cfg.n_booths
        self.urn_voter = None  # a vote being cast is voided (party reset below)

        for voter in affected:
            if voter.state == A.AT_URN and voter.party is not None:
                voter.party = None
            voter.evacuated = True
            voter.slot = None
            voter.event_token = None
            if self.random.random() < cfg.p_return:
                voter.state = A.EVACUATED
                self._schedule(t + cfg.closure_minutes + self.random.randint(1, 5), "return", voter)
                self._emit(
                    t,
                    "voter_evacuated",
                    f"Votante {voter.voter_id:02d} evacúa y piensa regresar",
                    voter,
                    will_return=True,
                )
            else:
                voter.state = A.ABANDONED_EARTHQUAKE
                voter.exit_time = t
                self._emit(
                    t,
                    "voter_evacuated",
                    f"Votante {voter.voter_id:02d} evacúa y se va definitivamente",
                    voter,
                    will_return=False,
                )

        self._schedule(t + cfg.closure_minutes, "reopen")

    def _on_reopen(self, t, _voter, _):
        self.station_open = True
        self._emit(t, "station_reopened", "La casilla reabre tras la revisión")

    def _on_return(self, t, voter, _):
        if not voter.decide_to_queue(len(self.queues["verification"])):
            voter.state = A.ABANDONED_EARTHQUAKE
            voter.exit_time = t
            self._emit(
                t,
                "voter_abandoned",
                f"Votante {voter.voter_id:02d} regresa pero decide abandonar la casilla",
                voter,
            )
        else:
            self._join_verification_queue(t, voter, "regresa y se vuelve a formar")

    # ------------------------------------------------------------------ read side

    def snapshot(self) -> dict:
        """Full current state, for a client to (re)synchronise."""
        ids = lambda q: [v.voter_id for v in q]  # noqa: E731
        slot_view = lambda slots: [  # noqa: E731
            {"index": i, "voter_id": v.voter_id if v else None} for i, v in enumerate(slots)
        ]
        return {
            "time": self.clock,
            "running": self.running,
            "station_open": self.station_open,
            "last_seq": self.last_seq,
            "verifiers": slot_view(self.verifiers),
            "booths": slot_view(self.booths),
            "urn": {"voter_id": self.urn_voter.voter_id if self.urn_voter else None},
            "queues": {name: ids(q) for name, q in self.queues.items()},
            "voters": [
                {
                    "id": v.voter_id,
                    "state": v.state,
                    "location": v.location,
                    "slot": v.slot,
                    "arrival": v.arrival,
                    "exit": v.exit_time if v.location == "exited" else None,
                }
                for v in self.voters
            ],
        }

    def results(self) -> dict:
        cfg = self.config
        voters = self.voters
        completed = [v for v in voters if v.state == A.FINISHED]
        votes = {p: sum(1 for v in voters if v.party == p) for p in cfg.parties}
        top = max(votes.values())
        evacuated = [v for v in voters if v.evacuated]
        by_state: dict[str, int] = {}
        for v in voters:
            by_state[v.state] = by_state.get(v.state, 0) + 1
        return {
            "finished": not self.running,
            "time": self.clock,
            "per_voter": [
                {"id": v.voter_id, "state": v.state, "minutes": v.minutes_in_station}
                for v in voters
            ],
            # Baseline definition: over all voters, including abandoned / invalid document
            "average_minutes_all": sum(v.minutes_in_station for v in voters) / len(voters),
            "average_minutes_completed": (
                sum(v.minutes_in_station for v in completed) / len(completed) if completed else None
            ),
            "voters_by_state": by_state,
            "votes": votes,
            "winner": max(votes, key=votes.get),
            "tie": sum(1 for n in votes.values() if n == top) > 1,
            "earthquake": {
                "occurred": bool(evacuated) or any(e["type"] == "earthquake" for e in self.log),
                "evacuated": len(evacuated),
                "voted_afterwards": sum(1 for v in evacuated if v.state == A.FINISHED),
            },
        }
