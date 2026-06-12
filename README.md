# Python Elevator Challenge — and the Simulation Lab It Grew Into

[![tests](https://github.com/nealedj/python-elevator-challenge/actions/workflows/tests.yml/badge.svg)](https://github.com/nealedj/python-elevator-challenge/actions/workflows/tests.yml)

This repository started life as Miles Shang's classic interview challenge: *implement the business logic for a simplified elevator* — decide whether to go up, go down, or stop, and pass a battery of doctests. The original challenge document is preserved, tests and all, in [tests/CHALLENGE.md](tests/CHALLENGE.md).

It has since grown into something bigger: a small, dependency-free **elevator simulation lab** that builds up, layer by layer, from one car sweeping six floors to a destination-dispatch bank moving 5,000 commuters through an eleven-storey office tower — with every layer specified and verified by literate test suites you can read like a story.

## The layers

| Layer | Code | Suite |
|---|---|---|
| Sweep ("LOOK") logic — the challenge solution | [`elevators/elevator.py`](elevators/elevator.py) | [tests/CHALLENGE.md](tests/CHALLENGE.md) |
| LOOK + anticipatory parking | [`elevators/efficient_elevator.py`](elevators/efficient_elevator.py) | [tests/SCENARIOS.md](tests/SCENARIOS.md) |
| Passenger simulation, one car | [`elevators/simulation.py`](elevators/simulation.py) | [tests/SCENARIOS.md](tests/SCENARIOS.md) |
| A bank of six cars with a group dispatcher | [`elevators/cluster.py`](elevators/cluster.py) | [tests/CLUSTER.md](tests/CLUSTER.md) |
| Destination dispatch (lobby kiosks) | [`elevators/destination.py`](elevators/destination.py) | [tests/DESTINATION.md](tests/DESTINATION.md) |

Each suite raises the realism a notch:

- **[CHALLENGE.md](tests/CHALLENGE.md)** drives the logic by pressing buttons in a script: directionality, direction changes, en-passant pickups, fuzz testing.
- **[SCENARIOS.md](tests/SCENARIOS.md)** simulates the *people*: passengers arrive over time, board only when the car is going their way, and the harness records everybody's wait — rush hours, near misses, phantom calls, a car that fills up, and randomized stress tests with hard delivery guarantees.
- **[CLUSTER.md](tests/CLUSTER.md)** scales to a bank of six cars on eleven floors, with a group controller assigning each hall call to the car with the best estimated time of arrival, finite capacities, and overflow re-dispatch.
- **[DESTINATION.md](tests/DESTINATION.md)** is the endgame: passengers key their destination into a kiosk *before* boarding, and the controller groups same-floor passengers into the same car — then proves it can absorb a 5,000-person morning rush, a surge at double intensity, and a full 14,000-trip working day.

A code review of the whole stack — including the saturation analysis that led to the destination dispatcher's burst-demand fixes — lives in [docs/REVIEW.md](docs/REVIEW.md).

## Usage

No dependencies; any modern Python 3 works (CI runs 3.11–3.13).

Run the test suites from the repository root:

```sh
python -m doctest tests/CHALLENGE.md   -o NORMALIZE_WHITESPACE
python -m doctest tests/SCENARIOS.md   -o NORMALIZE_WHITESPACE
python -m doctest tests/CLUSTER.md     -o NORMALIZE_WHITESPACE
python -m doctest tests/DESTINATION.md -o NORMALIZE_WHITESPACE
```

Compare the two single-car dispatchers over randomized traffic patterns:

```sh
python -m elevators.benchmark
```

Or drive a simulation yourself:

```python
>>> from elevators import Building, Passenger
>>> b = Building()
>>> b.schedule(1, Passenger('Ann', 1, 4))
>>> b.schedule(1, Passenger('Bob', 1, 6))
>>> b.run_until_idle()
<Ann in> <Bob in> 2... 3... 4... <Ann out> 5... 6... <Bob out>
>>> b.report()
Ann: floor 1 -> 4, waited 0, door to door 3
Bob: floor 1 -> 6, waited 0, door to door 6

```

Swap in the bank for the big building:

```python
>>> from elevators import DestinationBank
>>> bank = DestinationBank(verbose=False)   # 11 floors, 6 cars, capacity 10
>>> for i in range(100):
...     bank.schedule(1 + i % 30, Passenger('P%02d' % i, 1, 2 + i % 10))
>>> bank.run_until_idle()
>>> bank.everyone_delivered
True
>>> bank.average_wait < 10
True

```

## Taking the original challenge

Want to solve it yourself? Replace the logic in [`elevators/elevator.py`](elevators/elevator.py) with a naive stub and work through [tests/CHALLENGE.md](tests/CHALLENGE.md) until every example passes — then see how your implementation holds up against the passenger-level suites.

## License

[MIT](LICENSE) — original challenge © 2016 Miles Shang.
