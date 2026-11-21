# Project Context: INE Polling Station Simulation

Context document for the repo. It records what is known about the class challenge, where that knowledge comes from, and what is still open. Statuses are marked **[Confirmed]**, **[Suggested]**, **[Assumed]** or **[Open]**. Anything not marked confirmed should be treated as provisional until the teacher answers.

## 1. Course and challenge

- **Course:** Multi-agent systems and computational graphics (Tecnológico de Monterrey).
- **Challenge:** simulate a single INE polling station (*casilla*) during an election. **[Confirmed]**
- **Stack to use:** Python Mesa (simulation), a REST API, and a Unity frontend for visualization. **[Confirmed]**
- **Unity visualization:** 3D. **[Confirmed]**
- **Deliverable:** a demo of the simulation. No written report as far as is known. **[Assumed, not verified with the teacher]**
- **Architecture:** free. Neither the architecture nor the visual requirements are fixed by the teacher. The architecture in section 3 is only a suggestion from a course presentation. **[Confirmed]**

### Where this knowledge comes from

- One Teams class transcript (Nov 10, 2026, "Clase con socio formador"). It is heavily garbled by auto-transcription and covers only the start of the lecture and the closing minutes. It contains **no project requirements**. It only gives motivation: statistical methods help authorities estimate expected voters per station, estimate resource needs, detect irregularities and improve the efficiency and reliability of the voting process. It also says the next class is a Python programming lab implementing these concepts.
- The core simulation script `proceso_electoral.py`, provided by the teacher. Its comments are the only requirement-like statements available (section 4).
- A presentation slide with the suggested architecture (section 3).
- Earlier class meetings explaining the model and agents were held on Teams. They have not been seen by the author of this document.

## 2. Core simulation (provided baseline)

`proceso_electoral.py` is a pure discrete-event simulation (`heapq` event queue, integer minutes). It currently covers: voter arrival, nominal-list verification, booth (*mampara*), and the ballot box (*urna*). It does not use Mesa yet.

### Voter flow

Arrival → (may abandon) → verification queue → verifier → booth queue → (document check) → booth → ballot-box queue → urn → exit.

### Parameters in the baseline

| Item | Value |
|---|---|
| Voters (N) | 200 |
| Inter-arrival time | uniform integer 1–4 min |
| Verifiers | 3, service time uniform integer 2–7 min |
| Booths | 2, time uniform integer 3–9 min |
| Ballot box (urn) | 1 (single resource), time uniform integer 4–10 min |
| Document validity | 90% valid, checked when a booth becomes available for the voter |
| Abandonment (decided on arrival, by verification-queue length) | queue < 0.20·N → 10%; < 0.40·N → 40%; otherwise 80% |
| Vote | uniform choice between "Rojo" and "Azul", recorded when the voter starts at the urn |

### Event types

`Llegada`, `Verificar` (verification finished), `Mampara` (booth finished), `Casilla` (urn finished). A voter has at most one pending event at a time.

### Reported results

Per-voter time in the station, average time, votes per party, winning party.

### Requirement-like comments in the code **[Confirmed as written by the teacher, scope not verified]**

- Every event and relevant state change must be communicated to Unity for visualization. The comment says "en su reto", meaning in the student's own version of the challenge.
- The voter may choose which verifier to go to when more than one is free. The baseline always assigns the first free one.
- The baseline script covers only arrival, nominal-list verification and the booth. Later stages are expected to be extended.

### Known modeling notes on the baseline (for discussion, not yet decided)

- The "average time" divides by N and counts abandoned and invalid-document voters (their time is exit minus arrival). Whether the average should cover only voters who completed the process is **[Open]**.
- The abandonment threshold uses only the verification queue length, and only at arrival. Abandonment while waiting in later queues is not modeled. **[Open]**
- The document check happens at the booth stage, although the narrative suggests it belongs to verification. **[Open]**
- Mesa schedulers are tick-based, while the baseline is event-driven. **[Closed, see section 5]** The event queue is kept inside a Mesa `Model`; one `step()` = one simulated minute.

## 3. Suggested architecture (from course presentation) **[Suggested]**

The slide, "Proposed Challenge Architecture", shows two independent pipelines joined by HTTP polling.

**Simulation side (Python):** Mesa voter agents are updated by the Mesa scheduler/grid. State is extracted into a Flask JSON serializer, which a Flask API endpoint returns as JSON.

**Visualization side (Unity):** a Unity HTTP client issues `HTTP GET` requests and receives JSON data. It parses the data into a state manager, which updates positions of 3D GameObjects. The render engine then renders the scene.

**Asset pipeline:** Blender (3D modeling) exports FBX/OBJ files, which are imported into Unity Assets as the 3D models used by the GameObjects.

Design implications to settle:

- The suggested flow is pull-based (Unity polls with GET). The baseline code comment asks that every event be communicated to Unity. **[Closed, see section 5]** The model keeps an event log with sequence numbers and the API replays it with `?after=<seq>`.
- The API schema (voters, resources, queues, clock). **[Closed, provisional, see section 5 and the API repo README]**

## 4. Earthquake extension (in the current baseline file)

`proceso_electoral-1.py` (the file in this repo) already contains an earthquake external event that this document did not originally cover. **[Confirmed in code]** At most one per run, tested each minute with probability 0.0002. The station evacuates: queues and resources are emptied, a vote being cast is voided, and the station stays closed 20 minutes. Each evacuee returns with probability 0.60 (and then re-decides whether to queue), otherwise leaves for good. Voters arriving while closed leave. Note the baseline file is named `proceso_electoral-1.py`, not `proceso_electoral.py`.

## 5. Decisions taken in the implementation **[Provisional, change when the teacher answers]**

All reversible. Each one only fills an open question with the least surprising default.

- **Engine:** event queue (heapq, integer minutes) kept as is, wrapped in a Mesa `Model`; `step()` advances one minute and processes the events due. The same seed gives the same run as the teacher's script (checked by `tests/test_baseline_parity.py`, with and without earthquake).
- **Agents (open Q1):** only voters are Mesa agents. Verifiers, booths and the urn are model state, shown to the frontend as slots.
- **Clock (open Q2):** the client drives it with `POST /simulations/<id>/step`. No server-side autoplay.
- **Event log:** every relevant change is an entry with an increasing `seq`, stable `type` codes (English, snake_case) and the baseline's Spanish `message`. The party chosen is deliberately not in the log (ballot secrecy); it only appears in aggregate results.
- **Verifier choice:** `verifier_policy` = `first` (baseline, default) or `random`.
- **Metrics (open Q4):** baseline average over all voters is kept as `average_minutes_all`; `average_minutes_completed` is added alongside, so either definition can be chosen later without changing the model.
- **Parameters (open Q5):** all baseline values are fields of `Config` and can be overridden per simulation through the API.
- **Baseline modeling notes in section 2** are kept as given (open Q8), except that none of them is hard-wired.

## 6. Open questions for the teacher

1. Which agents are expected in Mesa: voters only, or also verifiers, booth staff and polling officials?
2. What must the REST API expose, and who drives the clock (Unity polling, or the simulation pushing)?
3. Which visual elements and states must the Unity scene show?
4. Which metrics must be reported (waiting time, queue lengths, abandonment rate, resource utilization)? The working assumption is the ones in the baseline.
5. Which parameters are fixed and which may vary (arrival rates, number of verifiers and booths, service times)?
6. Deliverables, deadline, team size and grading criteria. Confirm that there is no written report.
7. Is the single ballot box (urn) intended, given it is the likely bottleneck (4–10 min per voter against 2 booths)?
8. Should the baseline modeling choices in section 2 be kept as given?
