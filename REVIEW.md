# Code Review: `claude/elevator-simulation-1v9ltq`

A review of the elevator simulation stack — `elevator.py` (LOOK logic),
`efficient_elevator.py` (LOOK + anticipatory parking), `simulation.py`
(single-car passenger harness), `cluster.py` (six-car bank with a group
dispatcher), and `destination.py` (destination dispatch) — covering
(1) structure, readability and maintainability, and (2) throughput
optimisations for the destination dispatcher under burst demand.

All four doctest suites pass on this branch. Every measurement quoted
below was reproduced on this branch with the scripts described in the
appendix.

> **Status:** the two Part 2 fixes (§2.3) have since been applied on
> this branch — Fix A in `DestinationBank._cost`, Fix B as a
> `_pick_boarder` boarding-order hook on `ElevatorBank` overridden by
> `DestinationBank` — and DESTINATION.md gained a "Twice the rush"
> scenario pinning the surge behaviour. The structural items in Part 1
> and the further ideas in §2.4 remain open.

---

## Part 1 — Structure, readability, maintainability

The code is in good shape overall: small modules, literate doctest
suites, invariants asserted every tick, and a clear layering story
(logic → single car → bank → destination bank). The findings below are
ordered by impact.

### 1.1 `simulation.Building` and `cluster.ElevatorBank` duplicate the harness

`cluster.py` re-implements most of `simulation.py` rather than building
on it:

- `_Callbacks` is copied verbatim (`simulation.py:65-79` vs
  `cluster.py:43-57`).
- `schedule`, `tick`, `run`, `run_until_idle`, `idle`,
  `everyone_delivered`, `max_wait`, `max_total_time`, `report`, `_emit`,
  the move/exchange/board passenger plumbing, and the per-tick safety
  assertions all exist twice with small drifts.

The drifts are already visible: `average_wait` exists only on the bank;
`Building.report` and `ElevatorBank.report` format differently; the
single car asserts `current_floor <= FLOOR_COUNT` while the bank asserts
against `self.bank.floors`. Any future change to the passenger model
(e.g. per-passenger boarding time, see §2.5) must be made twice.

**Recommendation:** make `Building` a bank of one. `Car` plus
`ElevatorBank` already generalise everything `Building` does; `Building`
could be a thin subclass (or alias) of `ElevatorBank` with
`cars=1` and the car prefix suppressed in the trace tokens, or both
could share an extracted harness base (passenger ledger, clock,
metrics, reporting). One passenger-exchange implementation, one set of
invariant assertions.

### 1.2 Building height is half module-constant, half parameter

`FLOOR_COUNT = 6` (`elevator.py:1`) is baked into `simulation.py`'s
schedule assertions and into `EfficientElevatorLogic`'s default home
floor, while `ElevatorBank` takes `floors=11` as a parameter. The trap:
`ElevatorBank(make_logic=EfficientElevatorLogic)` silently gives every
car a home floor of 3 in an 11-storey building — `DestinationBank`
works around this by computing `home = (floors + 1) // 2` and passing
it in (`destination.py:42-44`), but nothing stops the next caller from
hitting it.

**Recommendation:** make the floor count a constructor parameter
everywhere (logic objects only need it for the parking default;
`Building` can take `floors=FLOOR_COUNT`). Keep the module constant
only as the README-suite default.

### 1.3 The dispatcher reaches into the logic's internals

`ElevatorBank._estimate` and `_sweep_extent` (`cluster.py:207-232`)
read `car.logic.calls`, `car.logic.selections` and
`car.logic.direction` directly. That couples the group controller to
`ElevatorLogic`'s private representation: any alternative logic plugged
in via `make_logic` must expose the same attribute shapes, and a future
change to how LOOK stores calls breaks dispatch estimation invisibly.

**Recommendation:** give the logic a small read-only query surface —
e.g. `committed_direction`, `pending_stop_count`,
`furthest_commitment(from_floor)` — and have the bank estimate against
that. This also documents what a dispatcher is allowed to know.

### 1.4 Quadratic dispatch scan (correctness fine, scaling poor)

`DestinationBank._cost` (`destination.py:79`) rebuilds the list of
passengers assigned to each car by scanning `self.waiting`, and `_cost`
runs for every car for every unassigned passenger every tick. During a
queue of W waiting passengers that is O(W² × cars) per tick. This is
why the saturated runs in Part 2 take minutes of wall-clock: the
window-1200 morning rush spends 129 s simulating, versus 1.4 s once
queues stay short.

**Recommendation:** maintain incremental indexes on the bank —
`assigned_to: {car: set(passenger)}` and per-car planned-floor
sets/counters, updated in `_place`, `_board` and the bounce path of
`_exchange`. Assignment cost lookup becomes O(1) per car and the
algorithm's behaviour is unchanged.

### 1.5 Exact statistical golden values make the suites brittle

The narrative doctests with full traces (`<Ann in A> A2...`) are
excellent and should stay byte-exact. But assertions like
`dd.average_wait == 3.59` and `phase(day, 'M') == (5000, 3.55, 22, 34)`
(DESTINATION.md, CLUSTER.md) pin the heuristic's exact output: any
tweak to `STOP_COST`, the cost function, or even dict iteration order
fails a dozen tests that are really asserting "the bank keeps up".

**Recommendation:** keep exact traces for the small scenarios; for the
statistical scenarios assert bounds (`dd.average_wait < 5`,
`dd.max_total_time <= 40`) so the suite expresses the actual guarantee
and survives tuning. (Part 2 proposes tuning.)

### 1.6 Smaller items

- **Stray file:** the empty `test` file at the repo root is left over
  from an early commit and should be deleted.
- **`Direction(int)` with `__invert__`** (`elevator.py:4-14`) is clever
  but surprising: `Direction.UP` the class attribute is a plain `int`,
  only the module-level `UP`/`DOWN` singletons invert correctly, and
  `~` on an unexpected int value returns `UP` silently. An
  `enum.IntEnum` with an `opposite()` method (or module function) says
  the same thing without the trap.
- **`CAPACITY_PENALTY = 10000` is a soft infinity** layered into an
  otherwise meaningful cost in ticks. Returning a sentinel (or
  excluding full-group cars from candidacy unless no other car exists)
  separates "this car is a bad choice" from "this car is forbidden".
  Part 2 shows the current formulation also has a behavioural cost.
- **Private cross-object calls:** `Car.step` calls
  `self.bank._exchange(self)` and `self.bank._emit(...)`; the
  underscore names suggest these are internal to `ElevatorBank`, but
  they are really the Car↔Bank contract. Either drop the underscores or
  move the exchange into `Car`.
- **`_choose` tie-breaking** via `(cost, car.name) < (best_cost,
  best.name)` (`destination.py:73`) reads awkwardly and would be
  clearer as a single `min()` over `(cost, name)` tuples, mirroring
  `_assign` in `cluster.py`.
- **CI scope:** the workflow only triggers on pushes to `master` plus
  PRs; pushes to feature branches without a PR run nothing. Adding the
  feature-branch pattern (or `workflow_dispatch`) keeps the suites
  honest during development. Pinning a benchmark *runtime* budget is
  not advisable, but `benchmark.py` on CI currently takes the bulk of
  the job time; a `--quick` seed-count flag would help.

---

## Part 2 — Throughput under burst demand

### 2.1 Where the current dispatcher saturates

The DESTINATION.md morning rush (5,000 staff, 11 floors, 6 cars,
capacity 10) spread over 3,600 ticks is 1.39 passengers/tick and the
bank absorbs it easily. Compressing the same demand finds the cliff:

| window | pax/tick | avg wait | max trip | clear-out after rush |
|-------:|---------:|---------:|---------:|---------------------:|
| 3600 | 1.39 | 3.6 | 34 | 27 |
| 2400 | 2.08 | 4.3 | 31 | 29 |
| 2100 | 2.38 | 5.9 | 37 | 33 |
| 1800 | 2.78 | **182.9** | **393** | 401 |
| 1500 | 3.33 | **340.2** | **700** | 710 |

Between 2.4 and 2.8 passengers/tick the queue stops draining and wait
times go from single digits to hundreds. That cliff is far below what
the hardware can do: a full car running express to one floor averages a
~13-tick round trip, so six cars should sustain roughly 4+ passengers
per tick *if grouping holds*.

### 2.2 Root cause: destination grouping collapses exactly at saturation

Measuring distinct destination floors per departing lobby load:

| window | avg load | distinct destinations (full loads) |
|-------:|---------:|------------------------------------:|
| 3600 | 3.4 | 3.7 |
| 1800 | 9.5 | **6.3** |

A random 10-passenger sample over 10 floors averages ~6.5 distinct
destinations — at saturation the "destination dispatch" loads are
statistically indistinguishable from no grouping at all. The system
degenerates into the conventional bank precisely when grouping is its
entire reason to exist (compare CLUSTER.md's conventional bank, which
DESTINATION.md shows hitting 830-tick average waits on this traffic).

Two mechanisms cause the collapse:

1. **The overflow branch of the cost function drops the grouping
   term.** `destination.py:83-84` returns `CAPACITY_PENALTY + eta` once
   a car's boarding group is full. Every car costs ≈10,000-and-change,
   `eta` differences are noise, so the 61st-and-later passenger in the
   queue is assigned with no destination affinity whatsoever — and
   assignments are sticky until a full-car bounce.
2. **Boarding is FIFO, not grouped.** `ElevatorBank._exchange`
   (`cluster.py:243-250`) boards eligible passengers in arrival order.
   Once the assigned mob for a car is destination-mixed (per mechanism
   1), the first ten in line are a random mix, and the car departs on a
   seven-stop milk run.

### 2.3 Fixes, prototyped and measured

Two independent, few-line fixes were prototyped (as subclasses, no
production code touched) and benchmarked on the same morning-rush
traffic, same seed:

- **Fix A — keep grouping in the overflow cost.** Compute the
  new-stop toll in all cases and *add* `CAPACITY_PENALTY` when the
  boarding group is full, instead of replacing the toll with it. Late
  assignments then still cluster by destination.
- **Fix B — board by destination group.** At the lobby exchange, board
  the longest-waiting passenger's destination group first (preserving
  the no-starvation guarantee), then fill remaining capacity with the
  largest destination groups among the eligible. FIFO within a group.

| window | pax/tick | current avg wait | Fix A | Fix B | A + B |
|-------:|---------:|-----------------:|------:|------:|------:|
| 3600 | 1.39 | 3.6 | 3.6 | 3.6 | 3.6 |
| 1800 | 2.78 | 182.9 | 55.3 | 19.8 | **18.7** |
| 1500 | 3.33 | 340.2 | 197.9 | 32.0 | **21.5** |
| 1200 | 4.17 | 495.4 | 281.3 | 125.5 | **37.3** |

Max door-to-door time at window 1200 falls from 1,008 ticks to 117,
and the post-rush clear-out from 1,017 ticks to 65. Below saturation
(window 3600) all variants produce byte-identical traces, so the
existing doctest suites are unaffected. Wall-clock simulation time at
window 1200 drops from 129 s to 1.4 s as a side effect of queues
staying short (the §1.4 quadratic scan stops mattering).

**Recommendation:** apply both. Fix B is the high-order bit and lives
naturally in `DestinationBank` as an override of the boarding order
(the kiosk *knows* destinations; sorting the boarding queue by group is
exactly what real kiosk displays accomplish by physically directing
passengers to car doors). Fix A is a two-line reshuffle of `_cost`.
Keep the starvation guard in Fix B — pure largest-group-first would
strand a lone passenger to an unpopular floor behind an endless stream
of popular-floor groups; seeding with the longest-waiting passenger's
group caps their wait at one round trip, and the measured max waits
confirm it (97–111 ticks at loads where the current code reaches 992).

### 2.4 Further optimisations worth exploring (not prototyped)

- **Re-evaluate sticky assignments.** A passenger assigned to a distant
  car keeps it even if a better car frees up; reassignment currently
  happens only via the full-car bounce. Periodically re-running
  `_choose` for queued passengers (cheap once §1.4's indexes exist)
  would also let the dispatcher consolidate groups it split earlier.
- **Up-peak sectoring.** The classic capacity move: when most recent
  origins are the lobby, partition floors into contiguous sectors
  (2–4 / 5–7 / 8–11) and dedicate pairs of cars to sectors. It bounds
  the highest reversal floor per trip, not just the stop count. With
  grouping fixed (§2.3) the marginal gain may be small at this
  building's size, but it is the next lever if demand grows.
- **A dwell/hold policy at the lobby.** Cars currently depart the tick
  after boarding whoever is present. Just below saturation, holding a
  partially full car 2–3 ticks when more passengers for its planned
  floors are queueing raises load factor at a small wait cost. Only
  worthwhile under detected up-peak; measure before adopting.
- **Model per-passenger boarding time.** `_exchange` boards any number
  of passengers in one tick, which flatters dense loads. One tick per
  boarding passenger (or per group) would make the throughput numbers
  more honest and would slightly favour fewer-stop schedules, i.e. it
  strengthens the case for grouping. This belongs in the shared
  harness of §1.1 so both suites get it.

---

## Appendix — reproducing the measurements

All experiments used the DESTINATION.md `morning_rush` shape: 5,000
passengers, lobby origin, uniform destinations 2–11, seed 7, arrival
times uniform over the stated window, `run_until_idle`.

- Saturation sweep (§2.1): run `morning_rush` at each window and record
  `average_wait`, `max_wait`, `max_total_time`, and `bank.time − window`.
- Grouping measurement (§2.2): bucket `bank.delivered` by
  `(assigned_car, boarded_at)` — one bucket per physical car-load — and
  count `len(set(destinations))` per bucket.
- Fix prototypes (§2.3): `FixA` overrides `DestinationBank._cost` to
  always include the `new_stops` toll and add `CAPACITY_PENALTY` on
  top when the boarding group is full; `FixB` overrides `_exchange` to
  board the longest-waiting passenger's destination group first, then
  remaining groups by descending size.
