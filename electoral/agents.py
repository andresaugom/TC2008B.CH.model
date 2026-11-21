"""Voter agent. State codes are stable identifiers meant for the frontend."""

import mesa

EN_ROUTE = "en_route"
WAITING_VERIFICATION = "waiting_verification"
VERIFYING = "verifying"
WAITING_BOOTH = "waiting_booth"
IN_BOOTH = "in_booth"
WAITING_URN = "waiting_urn"
AT_URN = "at_urn"
FINISHED = "finished"
ABANDONED = "abandoned"
INVALID_DOCUMENT = "invalid_document"
EVACUATED = "evacuated"  # left because of the earthquake, may come back
ABANDONED_EARTHQUAKE = "abandoned_earthquake"

# States in which the voter is physically inside the station (evacuated by an earthquake)
IN_STATION = (WAITING_VERIFICATION, VERIFYING, WAITING_BOOTH, IN_BOOTH, WAITING_URN, AT_URN)

# Where the frontend should draw a voter in each state
LOCATION = {
    EN_ROUTE: "outside",
    WAITING_VERIFICATION: "queue_verification",
    VERIFYING: "verifier",
    WAITING_BOOTH: "queue_booth",
    IN_BOOTH: "booth",
    WAITING_URN: "queue_urn",
    AT_URN: "urn",
    EVACUATED: "outside",
    FINISHED: "exited",
    ABANDONED: "exited",
    INVALID_DOCUMENT: "exited",
    ABANDONED_EARTHQUAKE: "exited",
}


class Voter(mesa.Agent):
    def __init__(self, model, voter_id: int):
        super().__init__(model)
        self.voter_id = voter_id
        self.state = EN_ROUTE
        self.arrival = 0
        self.exit_time = 0
        self.party = None
        self.slot = None  # verifier/booth index while being served
        self.event_token = None  # id of the only valid pending event (invalidates stale ones)
        self.evacuated = False

    def decide_to_queue(self, queue_len: int) -> bool:
        """Baseline rule: abandonment probability grows with the verification queue."""
        cfg = self.model.config
        n = cfg.n_voters
        low, mid, high = cfg.abandon_probs
        if queue_len < round(n * cfg.abandon_low_frac):
            p = low
        elif queue_len < round(n * cfg.abandon_mid_frac):
            p = mid
        else:
            p = high
        return not (self.model.random.random() < p)

    def document_is_valid(self) -> bool:
        return self.model.random.random() < self.model.config.p_valid_document

    def choose_party(self) -> str:
        self.party = self.model.random.choice(self.model.config.parties)
        return self.party

    @property
    def location(self) -> str:
        return LOCATION[self.state]

    @property
    def minutes_in_station(self) -> int:
        return self.exit_time - self.arrival
