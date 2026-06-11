# Destination Dispatch

The bank in [CLUSTER.md](CLUSTER.md) is a *conventional* group: passengers press up or down, and the controller learns where they are going only after they board. This suite models what busy towers actually install: a **destination dispatch** system, simulating the requirements of an office building with **5,000 people working on its 11 floors**, served by the same six cars.

With destination dispatch there are no up/down buttons and no buttons in the car. Passengers key their destination into a lobby kiosk *before* boarding; the controller — which now knows every origin–destination pair up front — assigns them a car on the spot, and the kiosk display sends them to it. Knowing destinations in advance lets the controller do the one thing that genuinely raises a bank's handling capacity: **group passengers going to the same floor into the same car**. A car that leaves the lobby for one or two floors instead of seven turns around far sooner.

The implementation is `destination.py`. Assignment uses the marginal-cost heuristic real systems use: estimate each car's pickup time, add a toll for every *new* stop the passenger would add to that car's plan (scaled by how many people already share the plan, since they all suffer the new stop), and heavily penalize a car whose boarding group is already at capacity (cars hold 10). The cheapest car wins — and grouping emerges from the cost function by itself. Finding the true optimum online is intractable; this is the practical frontier. The cars themselves are unchanged: each still runs the LOOK-with-parking logic from `efficient_elevator.py`.

To run this suite:

    python -m doctest DESTINATION.md -o NORMALIZE_WHITESPACE

    >>> import random
    >>> from destination import DestinationBank
    >>> from cluster import ElevatorBank
    >>> from elevator import ElevatorLogic
    >>> from simulation import Passenger

## The kiosk knows where you're going

Four people reach the lobby together: Ann and Bob work on 8, Cam and Dot on 3. The kiosk pairs them by destination — Ann and Bob get car A, Cam and Dot get car B — and each car runs *nonstop* to its one floor. (Plain LOOK cars here, so the trace isn't cluttered by parking moves.)

    >>> bank = DestinationBank(make_logic=ElevatorLogic)
    >>> bank.schedule(1, Passenger('Ann', 1, 8))
    >>> bank.schedule(1, Passenger('Bob', 1, 8))
    >>> bank.schedule(1, Passenger('Cam', 1, 3))
    >>> bank.schedule(1, Passenger('Dot', 1, 3))
    >>> bank.run_until_idle()
    <Ann in A> <Bob in A> <Cam in B> <Dot in B> A2... B2... A3... B3...
    <Cam out B> <Dot out B> A4... A5... A6... A7... A8... <Ann out A> <Bob out A>
    >>> bank.report()
    Ann: floor 1 -> 8, car A, waited 0, door to door 7
    Bob: floor 1 -> 8, car A, waited 0, door to door 7
    Cam: floor 1 -> 3, car B, waited 0, door to door 2
    Dot: floor 1 -> 3, car B, waited 0, door to door 2

The conventional bank, given the identical four, piles everyone into whichever car opens first. Ann and Bob ride a milk run — their trip costs an extra tick for the stop at 3, and that's with only four passengers. Multiply by a full lobby and the difference becomes the morning.

    >>> bank = ElevatorBank()
    >>> bank.schedule(1, Passenger('Ann', 1, 8))
    >>> bank.schedule(1, Passenger('Bob', 1, 8))
    >>> bank.schedule(1, Passenger('Cam', 1, 3))
    >>> bank.schedule(1, Passenger('Dot', 1, 3))
    >>> bank.run_until_idle()
    <Ann in A> <Bob in A> <Cam in A> <Dot in A> A2... A3... <Cam out A> <Dot out A>
    A4... A5... A6... A7... A8... <Ann out A> <Bob out A>
    >>> bank.report()
    Ann: floor 1 -> 8, car A, waited 0, door to door 8
    Bob: floor 1 -> 8, car A, waited 0, door to door 8
    Cam: floor 1 -> 3, car A, waited 0, door to door 2
    Dot: floor 1 -> 3, car A, waited 0, door to door 2

## The morning rush: 5,000 people through the lobby

Now the real test. All 5,000 employees — 500 per office floor — arrive at the lobby across a one-hour window (3,600 ticks).

    >>> def morning_rush(bank, seed=7, staff=5000, window=3600, floors=11):
    ...     rng = random.Random(seed)
    ...     home = [f for f in range(2, floors + 1)
    ...             for _ in range(staff // (floors - 1))]
    ...     rng.shuffle(home)
    ...     for i, f in enumerate(home):
    ...         bank.schedule(1 + rng.randrange(window), Passenger('M%04d' % i, 1, f))
    ...     bank.run_until_idle(limit=200000)
    ...     return bank

Destination dispatch absorbs the entire hour as it happens: the average employee waits under four ticks, nobody's door-to-door trip exceeds 34, and the lobby is clear 27 ticks after the last arrival.

    >>> dd = morning_rush(DestinationBank(verbose=False))
    >>> dd.everyone_delivered
    True
    >>> dd.average_wait
    3.59
    >>> dd.max_total_time
    34
    >>> dd.time
    3627

The conventional bank, on the *identical* traffic, saturates. Its handling capacity falls below the arrival rate — each lobby load scatters across seven or eight floors, so every round trip is too slow — and the queue compounds for the whole hour. The average wait is not a typo, and the last commuter reaches their desk 1,664 ticks after the rush ended.

    >>> conv = morning_rush(ElevatorBank(verbose=False))
    >>> conv.everyone_delivered
    True
    >>> conv.average_wait
    830.05
    >>> conv.max_total_time
    1666
    >>> conv.time
    5264

## The evening is not the problem

Going home is easy mode for any dispatcher: a down sweep collects passengers floor by floor and everyone shares the same destination, so grouping is automatic. The conventional bank nearly keeps up — destination dispatch wins on the margin, not by an order of magnitude. The morning, not the evening, is why towers buy these systems.

    >>> def evening_rush(bank, seed=8, staff=5000, window=3600, floors=11):
    ...     rng = random.Random(seed)
    ...     home = [f for f in range(2, floors + 1)
    ...             for _ in range(staff // (floors - 1))]
    ...     rng.shuffle(home)
    ...     for i, f in enumerate(home):
    ...         bank.schedule(1 + rng.randrange(window), Passenger('E%04d' % i, f, 1))
    ...     bank.run_until_idle(limit=200000)
    ...     return bank
    >>> evening_rush(DestinationBank(verbose=False)).average_wait
    5.29
    >>> evening_rush(ElevatorBank(verbose=False)).average_wait
    5.86

## A full working day

Finally, the whole day on one continuous clock, one tick per simulated second: 5,000 people in across the eight-o'clock hour, 2,000 of them out and back at lunch, and 5,000 out again at five — 14,000 trips.

    >>> def working_day(bank, seed=2026, staff=5000, floors=11):
    ...     rng = random.Random(seed)
    ...     home = [f for f in range(2, floors + 1)
    ...             for _ in range(staff // (floors - 1))]
    ...     rng.shuffle(home)
    ...     for i, f in enumerate(home):
    ...         bank.schedule(1 + rng.randrange(3600), Passenger('M%04d' % i, 1, f))
    ...     out_to_lunch = list(range(staff))
    ...     rng.shuffle(out_to_lunch)
    ...     for i in out_to_lunch[:2000]:
    ...         out = 7201 + rng.randrange(1500)
    ...         bank.schedule(out, Passenger('L%04d-out' % i, home[i], 1))
    ...         bank.schedule(out + 1600 + rng.randrange(500),
    ...                       Passenger('L%04d-back' % i, 1, home[i]))
    ...     for i, f in enumerate(home):
    ...         bank.schedule(14401 + rng.randrange(3600), Passenger('E%04d' % i, f, 1))
    ...     bank.run_until_idle(limit=300000)
    ...     return bank
    >>> day = working_day(DestinationBank(verbose=False))
    >>> len(day.all_passengers)
    14000
    >>> day.everyone_delivered
    True

Per phase — (trips, average wait, worst wait, worst door to door):

    >>> def phase(bank, prefix):
    ...     ps = [p for p in bank.delivered if p.name.startswith(prefix)]
    ...     waits = [p.wait_time for p in ps]
    ...     return (len(ps), round(sum(waits) / float(len(waits)), 2),
    ...             max(waits), max(p.total_time for p in ps))
    >>> phase(day, 'M')
    (5000, 3.55, 22, 34)
    >>> phase(day, 'L')
    (4000, 4.22, 23, 35)
    >>> phase(day, 'E')
    (5000, 5.35, 24, 35)

Across all 14,000 trips the average wait is under four and a half seconds of simulated time, and no employee ever spends more than 35 ticks door to door — through the heaviest hour this building has.

    >>> day.average_wait
    4.38
    >>> day.max_total_time
    35

And the guarantee is not a lucky seed: three more mornings, three more full deliveries.

    >>> all(morning_rush(DestinationBank(verbose=False), seed=s).everyone_delivered
    ...     for s in (1, 2, 3))
    True
