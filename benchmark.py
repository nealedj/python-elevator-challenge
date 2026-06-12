"""
Head-to-head comparison of the two dispatchers on the passenger simulation.

Runs both ElevatorLogic (the sweep/LOOK algorithm from elevator.py) and
EfficientElevatorLogic (LOOK plus anticipatory parking) over many randomized
traffic patterns and reports passenger wait and door-to-door times.

$ python benchmark.py
"""
import random

from elevator import ElevatorLogic, FLOOR_COUNT
from efficient_elevator import EfficientElevatorLogic
from simulation import Building, Passenger


def random_trip(rng, pattern):
    floors = range(1, FLOOR_COUNT + 1)
    if pattern == 'up-peak':       # morning: everybody from the lobby
        origin = 1 if rng.random() < 0.8 else rng.choice(floors)
        destination = rng.choice(floors)
    elif pattern == 'down-peak':   # evening: everybody to the lobby
        origin = rng.choice(floors)
        destination = 1 if rng.random() < 0.8 else rng.choice(floors)
    else:                          # interfloor: uniform
        origin = rng.choice(floors)
        destination = rng.choice(floors)
    while destination == origin:
        destination = rng.choice(floors)
    return origin, destination


def simulate(logic_class, seed, pattern, passengers, horizon):
    rng = random.Random(seed)
    building = Building(logic=logic_class(), verbose=False)
    for i in range(passengers):
        origin, destination = random_trip(rng, pattern)
        building.schedule(rng.randrange(1, horizon),
                          Passenger('P%03d' % i, origin, destination))
    building.run_until_idle(limit=10000)
    assert building.everyone_delivered, (logic_class.__name__, pattern, seed)
    return building.delivered


def main(seeds=200):
    loads = [
        ('light traffic', 8, 240),
        ('rush hour', 30, 120),
        ('crush load', 60, 120),
    ]
    contenders = [ElevatorLogic, EfficientElevatorLogic]

    print('%-14s %-10s %-24s %9s %9s %9s' % (
        'load', 'pattern', 'dispatcher', 'avg wait', 'avg trip', 'max trip'))
    for load_name, passengers, horizon in loads:
        for pattern in ('interfloor', 'up-peak', 'down-peak'):
            for logic_class in contenders:
                waits, trips, worst = [], [], 0
                for seed in range(seeds):
                    delivered = simulate(logic_class, seed, pattern,
                                         passengers, horizon)
                    waits.extend(p.wait_time for p in delivered)
                    trips.extend(p.total_time for p in delivered)
                    worst = max(worst, max(p.total_time for p in delivered))
                print('%-14s %-10s %-24s %9.2f %9.2f %9d' % (
                    load_name, pattern, logic_class.__name__,
                    sum(waits) / float(len(waits)),
                    sum(trips) / float(len(trips)), worst))
        print()


if __name__ == '__main__':
    main()
