# Realistic Elevator Scenarios

The tests in `README.md` drive the elevator by pressing its buttons in a script. This alternative suite is one level more realistic: it simulates the *people*. Passengers arrive over time, press the call button on their floor, board only when the elevator stops there committed to the direction they want — just like real people reading the indicator above the door — select their destination once inside, and get off when they reach it.

The harness lives in `simulation.py` and is instrumented: it records when each passenger arrived, boarded, and was delivered, so we can make assertions about waiting times, not just button presses. It also checks invariants on every tick: the elevator must stay within the building, and it must never carry a passenger *away* from their destination.

Simplifications: the car has unlimited capacity by default (pass `Building(capacity=...)` to model a finite car), and moving one floor, pausing, or exchanging passengers each takes exactly one tick.

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

## A car that fills up

The suite's traffic never crowds the car — its heaviest scenarios peak at five simultaneous riders — so by default capacity is unlimited, as the laws of physics are someone else's department. But the harness can model a real car: give it a finite capacity, and whoever finds it full watches the doors close and waits for it to come around again. Kim, Lee, and Max all head down from 3 in a car that holds two.

    >>> b = Building(capacity=2)
    >>> b.schedule(1, Passenger('Kim', 3, 1))
    >>> b.schedule(1, Passenger('Lee', 3, 1))
    >>> b.schedule(1, Passenger('Max', 3, 1))
    >>> b.run_until_idle()
    2... 3... <Kim in> <Lee in> 2... 1... <Kim out> <Lee out> 2... 3... <Max in>
    2... 1... <Max out>

Max pays for the second round trip, but he is never forgotten:

    >>> b.report()
    Kim: floor 3 -> 1, waited 2, door to door 5
    Lee: floor 3 -> 1, waited 2, door to door 5
    Max: floor 3 -> 1, waited 8, door to door 11

## Rush hour stress test

Finally, the torture test: thirty passengers with random origins, destinations, and arrival times, all crowding into a two-minute window. Every passenger must be delivered — no one may be stranded or starved — and the per-tick invariants (stay inside the building, never drive a rider away from their destination) must hold throughout.

    >>> import random
    >>> def rush_hour(seed, passengers=30, horizon=120, make_logic=lambda: None):
    ...     rng = random.Random(seed)
    ...     b = Building(logic=make_logic(), verbose=False)
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

## A more efficient dispatcher

The sweep algorithm in `elevator.py` is what the README's tests mandate, and benchmarking (`python benchmark.py`) shows its trip scheduling is hard to beat: a textbook nearest-call-first greedy dispatcher measures *worse* on every traffic pattern, because stopping for an opposite-direction caller commits the car to that passenger's whole trip and breaks up the batching that sweeps get for free.

What the sweep ignores is where the car waits when it has nothing to do: it strands itself wherever the last sweep ended, usually at the top or bottom of the building. The dispatcher in `efficient_elevator.py` keeps the sweep scheduling and adds anticipatory parking — when idle, it relocates toward the median floor of recent call origins, so it is already nearby when the next passenger shows up.

    >>> from elevator import ElevatorLogic
    >>> from efficient_elevator import EfficientElevatorLogic

Watch where the car goes after delivering Ann to the top floor: instead of waiting at 6, it heads back to the middle of the building.

    >>> b = Building(logic=EfficientElevatorLogic())
    >>> b.schedule(1, Passenger('Ann', 1, 6))
    >>> b.run_until_idle()
    <Ann in> 2... 3... 4... 5... 6... <Ann out> 5... 4... 3...

So when Bea calls from floor 2, the car is one floor away instead of four. Parking trips carry nobody and owe nobody anything, so a real call cancels them mid-flight.

    >>> b.schedule(b.time + 1, Passenger('Bea', 2, 5))
    >>> b.run_until_idle()
    2... <Bea in> 3... 4... 5... <Bea out> 4... 3... 2...
    >>> b.report()
    Ann: floor 1 -> 6, waited 0, door to door 5
    Bea: floor 2 -> 5, waited 1, door to door 5

Note that the second time it parked at floor 2, not 3 — it has started learning where the demand is.

    >>> b.current_floor
    2

On a quiet, lobby-heavy morning — the situation real buildings face every day — parking cuts the average wait by more than a third compared to the standard dispatcher:

    >>> def quiet_morning(make_logic, seeds=20):
    ...     waits = []
    ...     for seed in range(seeds):
    ...         rng = random.Random(seed)
    ...         b = Building(logic=make_logic(), verbose=False)
    ...         for i in range(8):
    ...             origin = 1 if rng.random() < 0.8 else rng.randrange(2, FLOOR_COUNT + 1)
    ...             destination = rng.randrange(2, FLOOR_COUNT + 1)
    ...             while destination == origin:
    ...                 destination = rng.randrange(2, FLOOR_COUNT + 1)
    ...             b.schedule(rng.randrange(1, 240), Passenger('P%d' % i, origin, destination))
    ...         b.run_until_idle(limit=2000)
    ...         assert b.everyone_delivered
    ...         waits.extend(p.wait_time for p in b.delivered)
    ...     return round(sum(waits) / float(len(waits)), 2)
    >>> quiet_morning(ElevatorLogic)
    2.95
    >>> quiet_morning(EfficientElevatorLogic)
    1.8

And it still honors the same hard service guarantees under rush hour load:

    >>> all(rush_hour(seed, make_logic=EfficientElevatorLogic).everyone_delivered
    ...     for seed in range(20))
    True
    >>> max(rush_hour(seed, make_logic=EfficientElevatorLogic).max_total_time
    ...     for seed in range(20)) <= 30
    True
