# Realistic Elevator Scenarios

The tests in `README.md` drive the elevator by pressing its buttons in a script. This alternative suite is one level more realistic: it simulates the *people*. Passengers arrive over time, press the call button on their floor, board only when the elevator stops there committed to the direction they want — just like real people reading the indicator above the door — select their destination once inside, and get off when they reach it.

The harness lives in `simulation.py` and is instrumented: it records when each passenger arrived, boarded, and was delivered, so we can make assertions about waiting times, not just button presses. It also checks invariants on every tick: the elevator must stay within the building, and it must never carry a passenger *away* from their destination.

Simplifications: the car has unlimited capacity, and moving one floor, pausing, or exchanging passengers each takes exactly one tick.

To run this suite:

    python -m doctest SCENARIOS.md -o NORMALIZE_WHITESPACE

Output conventions match the README — `3...` means the elevator moved to floor 3 — plus `<Ann in>` and `<Ann out>` for boardings and deliveries.

    >>> from simulation import Building, Passenger, UP, DOWN, FLOOR_COUNT

## Morning rush

Ann and Bob are waiting in the lobby when the building opens; Ann works on 4, Bob on 6. Cy shows up moments after the elevator leaves.

    >>> b = Building()
    >>> b.schedule(1, Passenger('Ann', 1, 4))
    >>> b.schedule(1, Passenger('Bob', 1, 6))
    >>> b.schedule(2, Passenger('Cy', 1, 3))
    >>> b.run_until_idle()
    <Ann in> <Bob in> 2... 3... 4... <Ann out> 5... 6... <Bob out>
    5... 4... 3... 2... 1... <Cy in> 2... 3... <Cy out>

Ann and Bob share the car and are dropped off in floor order on a single up sweep. Cy missed the doors by one tick, and the price is steep: the elevator finishes its sweep and comes all the way back down before he can board.

    >>> b.report()
    Ann: floor 1 -> 4, waited 0, door to door 3
    Bob: floor 1 -> 6, waited 0, door to door 6
    Cy: floor 1 -> 3, waited 11, door to door 14

## Evening rush

Quitting time. Dee on 6, Eli on 4, and Fay on 3 all head for the lobby, calling the elevator a tick apart. The elevator climbs past Eli and Fay first — it is on its way up, and they want to go down — then collects all three on one down sweep.

    >>> b = Building()
    >>> b.schedule(1, Passenger('Dee', 6, 1))
    >>> b.schedule(2, Passenger('Eli', 4, 1))
    >>> b.schedule(3, Passenger('Fay', 3, 1))
    >>> b.run_until_idle()
    2... 3... 4... 5... 6... <Dee in> 5... 4... <Eli in> 3... <Fay in>
    2... 1... <Dee out> <Eli out> <Fay out>

Note the fairness of the sweep: Dee called first and waited longest for the car, but everybody's door-to-door time is within a couple of ticks of everybody else's.

    >>> b.report()
    Dee: floor 6 -> 1, waited 5, door to door 13
    Eli: floor 4 -> 1, waited 7, door to door 12
    Fay: floor 3 -> 1, waited 8, door to door 11

## Crossing traffic on the same floor

Gus and Hal are both on floor 4, but Gus wants to go up one floor and Hal wants the lobby. The elevator starts at the top of the building. Gus pressed his button first, so the elevator heads for floor 4 — but it arrives *going down*, so only Hal boards. Gus watches the doors close and waits for the elevator to come back up for him.

    >>> b = Building(starting_floor=6)
    >>> b.schedule(1, Passenger('Gus', 4, 5))
    >>> b.schedule(1, Passenger('Hal', 4, 1))
    >>> b.run_until_idle()
    5... 4... <Hal in> 3... 2... 1... <Hal out> 2... 3... 4... <Gus in> 5... <Gus out>

Directionality has a cost: Gus called first but is delivered last.

    >>> b.report()
    Gus: floor 4 -> 5, waited 10, door to door 12
    Hal: floor 4 -> 1, waited 2, door to door 6

## The phantom up call

Somebody on floor 5 pressed the up button and took the stairs. Then Pia arrives on 5, wanting the lobby. The elevator answers the stale up call first: it arrives at 5 showing UP, and Pia — who knows better than to board an elevator going the wrong way — stays put. Since nobody wants to go further up, the elevator closes its doors, reopens them going DOWN one tick later, and Pia boards.

    >>> b = Building()
    >>> b.press(5, UP)
    >>> b.schedule(1, Passenger('Pia', 5, 1))
    >>> b.run_until_idle()
    2... 3... 4... 5... <Pia in> 4... 3... 2... 1... <Pia out>

The direction change is invisible in the movement trace but visible in the clock: the trip up takes four ticks, yet Pia waits five — the extra tick is the elevator clearing its phantom up commitment at her floor.

    >>> b.report()
    Pia: floor 5 -> 1, waited 5, door to door 10

## Just in time, just missed

Quin rides from the lobby toward 6. Rex appears on 3 just *before* the elevator gets there and is picked up en passant, without delaying anyone. Sam appears on 3 just as the elevator is already passing — and pays for those two ticks with a full round trip.

    >>> b = Building()
    >>> b.schedule(1, Passenger('Quin', 1, 6))
    >>> b.schedule(3, Passenger('Rex', 3, 5))
    >>> b.schedule(5, Passenger('Sam', 3, 4))
    >>> b.run_until_idle()
    <Quin in> 2... 3... <Rex in> 4... 5... <Rex out> 6... <Quin out>
    5... 4... 3... <Sam in> 4... <Sam out>

    >>> b.report()
    Quin: floor 1 -> 6, waited 0, door to door 7
    Rex: floor 3 -> 5, waited 0, door to door 3
    Sam: floor 3 -> 4, waited 7, door to door 9

## Rush hour stress test

Finally, the torture test: thirty passengers with random origins, destinations, and arrival times, all crowding into a two-minute window. Every passenger must be delivered — no one may be stranded or starved — and the per-tick invariants (stay inside the building, never drive a rider away from their destination) must hold throughout.

    >>> import random
    >>> def rush_hour(seed, passengers=30, horizon=120):
    ...     rng = random.Random(seed)
    ...     b = Building(verbose=False)
    ...     for i in range(passengers):
    ...         origin = rng.randrange(1, FLOOR_COUNT + 1)
    ...         destination = rng.randrange(1, FLOOR_COUNT + 1)
    ...         while destination == origin:
    ...             destination = rng.randrange(1, FLOOR_COUNT + 1)
    ...         b.schedule(rng.randrange(1, horizon), Passenger('P%02d' % i, origin, destination))
    ...     b.run_until_idle(limit=2000)
    ...     return b

One fixed seed, examined closely:

    >>> b = rush_hour(2026)
    >>> b.everyone_delivered
    True
    >>> b.max_wait
    16
    >>> b.max_total_time
    18

And twenty more seeds, held to a hard service guarantee. A sweep over six floors costs at most five moves plus a handful of stops, so even at rush hour nobody should ever spend more than thirty ticks door to door — the sweep algorithm's no-starvation property in numbers.

    >>> all(rush_hour(seed).everyone_delivered for seed in range(20))
    True
    >>> max(rush_hour(seed).max_total_time for seed in range(20)) <= 30
    True
