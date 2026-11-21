"""Simulation parameters. Defaults reproduce the teacher's baseline script."""

from dataclasses import dataclass, fields, replace


@dataclass(frozen=True)
class Config:
    n_voters: int = 200
    arrival_range: tuple[int, int] = (1, 4)  # minutes between arrivals
    n_verifiers: int = 3
    verification_range: tuple[int, int] = (2, 7)
    n_booths: int = 2
    booth_range: tuple[int, int] = (3, 9)
    urn_range: tuple[int, int] = (4, 10)  # single urn
    p_valid_document: float = 0.90
    # Abandonment on arrival, by verification-queue length (fractions of n_voters)
    abandon_low_frac: float = 0.20
    abandon_mid_frac: float = 0.40
    abandon_probs: tuple[float, float, float] = (0.10, 0.40, 0.80)
    parties: tuple[str, ...] = ("Rojo", "Azul")
    # Earthquake (external event)
    p_earthquake_per_minute: float = 0.0002
    closure_minutes: int = 20
    p_return: float = 0.60
    # Which free verifier a voter picks: "first" (baseline) or "random"
    verifier_policy: str = "first"

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """Build from user input (e.g. JSON). Unknown keys and bad values raise ValueError."""
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"unknown config keys: {sorted(unknown)}")
        data = {k: tuple(v) if isinstance(v, list) else v for k, v in data.items()}
        cfg = replace(cls(), **data)
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if self.n_voters < 1 or self.n_verifiers < 1 or self.n_booths < 1:
            raise ValueError("n_voters, n_verifiers and n_booths must be >= 1")
        for name in ("arrival_range", "verification_range", "booth_range", "urn_range"):
            lo, hi = getattr(self, name)
            if not (1 <= lo <= hi):
                raise ValueError(f"{name} must satisfy 1 <= low <= high")
        for name in ("p_valid_document", "p_earthquake_per_minute", "p_return"):
            if not 0 <= getattr(self, name) <= 1:
                raise ValueError(f"{name} must be in [0, 1]")
        if not all(0 <= p <= 1 for p in self.abandon_probs):
            raise ValueError("abandon_probs must be in [0, 1]")
        if self.verifier_policy not in ("first", "random"):
            raise ValueError("verifier_policy must be 'first' or 'random'")
        if not self.parties:
            raise ValueError("parties must not be empty")
