# The Elevator Bank

The single-car scenarios in [SCENARIOS.md](SCENARIOS.md) end where real office buildings begin. This suite models a far more complex setup: a **bank of six elevators** (cars A through F) serving an **eleven-story** office tower, with a group controller deciding which car answers which call.

The harness lives in `cluster.py`. Each car independently runs the unmodified LOOK logic from `elevator.py` — which never needed to know how tall the building is — while the group controller handles dispatch the way modern systems do:

- When a passenger presses a hall button, the controller estimates every car's time of arrival at that floor (straight-line distance for an idle car; distance along the current sweep plus a toll per pending stop; or the round trip via the end of the sweep) and assigns the call to the quickest car.
- A hall lantern tells the passenger which car will serve them, so they board that car and only that car. Same-direction calls on the same floor share one assignment.
- Cars hold at most **10 passengers**. Whoever finds their car full is handed back to the dispatcher and dealt to the next-best car.

The same per-tick invariants from the single-car suite are enforced for every car: stay inside the building, and never carry a rider away from their destination.

To run this suite:

    python -m doctest CLUSTER.md -o NORMALIZE_WHITESPACE

Movement tokens are prefixed with the car's name — `C6...` means car C moved to floor 6 — and boardings name the car: `<Pia in C>`.

    >>> from cluster import ElevatorBank
    >>> from simulation import Passenger

## Six cars, one call

The cars are spread through the building. Pia, on floor 6, wants to go down to 2. Cars C (floor 5) and D (floor 7) are both one floor away; the controller breaks the tie alphabetically and sends C. Note that the other five cars never move.

    >>> bank = ElevatorBank(starting_floors=[1, 3, 5, 7, 9, 11])
    >>> bank.positions()
    A:1 B:3 C:5 D:7 E:9 F:11
    >>> bank.schedule(1, Passenger('Pia', 6, 2))
    >>> bank.run_until_idle()
    C6... <Pia in C> C5... C4... C3... C2... <Pia out C>
    >>> bank.report()
    Pia: floor 6 -> 2, car C, waited 1, door to door 6

## Morning arrivals spread across the bank

All six cars start at the lobby. Ann and Bob arrive together and share car A. Cam shows up one tick later — car A has already left, so he steps into car B, and his short hop to floor 3 doesn't have to wait behind Ann and Bob's long rides. Dot takes car C to the top floor. Three cars work in parallel; nobody waits at all.

    >>> bank = ElevatorBank()
    >>> bank.schedule(1, Passenger('Ann', 1, 8))
    >>> bank.schedule(1, Passenger('Bob', 1, 9))
    >>> bank.schedule(2, Passenger('Cam', 1, 3))
    >>> bank.schedule(3, Passenger('Dot', 1, 11))
    >>> bank.run_until_idle()
    <Ann in A> <Bob in A> <Cam in B> A2... <Dot in C> A3... B2... A4... B3... <Cam out B>
    C2... A5... C3... A6... C4... A7... C5... A8... <Ann out A> C6... C7... A9... <Bob out A>
    C8... C9... C10... C11... <Dot out C>
    >>> bank.report()
    Ann: floor 1 -> 8, car A, waited 0, door to door 7
    Bob: floor 1 -> 9, car A, waited 0, door to door 9
    Cam: floor 1 -> 3, car B, waited 0, door to door 2
    Dot: floor 1 -> 11, car C, waited 0, door to door 10

## A crowd bigger than one car

A meeting on floor 7 lets out and twelve people head for the lobby at once. All twelve calls share one assignment, so car A answers — but it holds only ten. The two left on the landing go back to the dispatcher, which sends car B up for them. Everybody gets home.

    >>> bank = ElevatorBank(verbose=False)
    >>> for i in range(12):
    ...     bank.schedule(1, Passenger('P%02d' % i, 7, 1))
    >>> bank.run_until_idle()
    >>> bank.everyone_delivered
    True
    >>> sorted({p.assigned_car.name for p in bank.delivered})
    ['A', 'B']
    >>> bank.max_wait
    13

The unlucky pair waited 13 ticks — the time for car B to climb seven floors after the dispatcher learned car A was full.

## A workday morning, with and without the bank

Finally, the full picture: a hundred passengers over two hundred ticks, weighted toward the morning pattern (60% start at the lobby), on eleven floors.

    >>> import random
    >>> def workday(seed, cars=6, passengers=100, horizon=200, floors=11):
    ...     rng = random.Random(seed)
    ...     bank = ElevatorBank(floors=floors, cars=cars, verbose=False)
    ...     for i in range(passengers):
    ...         if rng.random() < 0.6:
    ...             origin, destination = 1, rng.randrange(2, floors + 1)
    ...         else:
    ...             origin = rng.randrange(1, floors + 1)
    ...             destination = rng.randrange(1, floors + 1)
    ...             while destination == origin:
    ...                 destination = rng.randrange(1, floors + 1)
    ...         bank.schedule(rng.randrange(1, horizon),
    ...                       Passenger('P%03d' % i, origin, destination))
    ...     bank.run_until_idle(limit=20000)
    ...     return bank

With six cars, the average passenger barely waits:

    >>> cluster = workday(2026)
    >>> cluster.everyone_delivered
    True
    >>> cluster.average_wait
    3.82
    >>> cluster.max_total_time
    33

Run the *identical* traffic against a single car and the morning falls apart — five times the average wait, and somebody spends 110 ticks getting to work:

    >>> lone = workday(2026, cars=1)
    >>> lone.everyone_delivered
    True
    >>> lone.average_wait
    18.8
    >>> lone.max_total_time
    110

And the hard guarantees hold across twenty different mornings: every passenger is always delivered, within a bounded door-to-door time, no matter how the crowd shakes out.

    >>> all(workday(seed).everyone_delivered for seed in range(20))
    True
    >>> max(workday(seed).max_total_time for seed in range(20)) <= 45
    True
