# TC2008B.CH.model

Mesa model of a single INE polling station. Consumed by the API repo (`TC2008B.CH.api`) as a git submodule.
See `PROJECT_CONTEXT.md` for the challenge context, decisions and open questions.

```
uv sync
uv run pytest
```

```python
from electoral import Config, ElectionModel

m = ElectionModel(Config(), seed=1)  # same seed, same run
m.run_to_end()  # or m.step() = one simulated minute
m.events_since(0)
m.snapshot()
m.results()
```

`proceso_electoral-1.py` is the teacher's script, kept untouched as the reference for the parity tests.
