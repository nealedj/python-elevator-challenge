"""
An alternative elevator dispatcher tuned for the passenger simulation.

The logic in `elevator.py` implements the classic sweep ("LOOK") algorithm.
Benchmarking on the passenger model in `simulation.py` (see benchmark.py)
shows that LOOK's sweeps are essentially unbeatable *while the car has work
to do*, at least in a six floor building: a nearest-call-first greedy
dispatcher -- the textbook "more efficient" alternative -- measures WORSE
than LOOK on every traffic pattern at every load, because stopping for
opposite-direction callers commits the car to their whole trip and breaks up
the batching that sweeps get for free.

What LOOK ignores completely is where the car waits when it has nothing to
do: it strands the car wherever the last sweep ended, which is usually the
top or bottom of the building. This dispatcher keeps LOOK's trip scheduling
unchanged and adds anticipatory parking: when the car goes idle, it
relocates to the median floor of recent call origins (defaulting to the
middle of the building), so it is already near the next passenger when they
arrive. During a morning rush it learns to wait at the lobby, which is
exactly what real elevators are programmed to do.

Measured against plain LOOK over 200 random seeds per cell (benchmark.py):
average wait drops by about a third in light lobby-heavy traffic and never
gets worse, while heavy-load performance and LOOK's no-starvation guarantee
are untouched. Parking trips are cancelled the moment a real call arrives.

This dispatcher targets the passenger model in `simulation.py` and
tests/SCENARIOS.md. It deliberately does not pass the challenge suite in
tests/CHALLENGE.md, whose tests require the car to stay where it stops.
"""
from collections import deque

from .elevator import ElevatorLogic, UP, DOWN, FLOOR_COUNT

# How many recent call origins to remember when choosing where to park.
PARKING_MEMORY = 20


class EfficientElevatorLogic(ElevatorLogic):
    def __init__(self, home_floor=None, floors=FLOOR_COUNT):
        """`floors` sets the default home floor (the middle of the building);
        pass it whenever the building is taller than the challenge's six
        floors, or pass `home_floor` to pick the parking spot directly."""
        ElevatorLogic.__init__(self)
        self.parking = False
        self._park_target = None
        self._home_floor = home_floor or (floors + 1) // 2
        self._recent_origins = deque(maxlen=PARKING_MEMORY)

    def on_called(self, floor, direction):
        self._recent_origins.append(floor)
        ElevatorLogic.on_called(self, floor, direction)

    def on_floor_changed(self):
        if self.parking:
            # A parking trip carries nobody and owes nobody anything: cancel
            # it the moment real work shows up, or stop on reaching the spot.
            if (self.calls or self.selections
                    or self.callbacks.current_floor == self._park_target):
                self.parking = False
                self.callbacks.motor_direction = None
            return
        ElevatorLogic.on_floor_changed(self)

    def on_ready(self):
        self.parking = False
        ElevatorLogic.on_ready(self)
        if (self.callbacks.motor_direction is None and self.direction is None
                and not self.calls and not self.selections):
            target = self._preferred_parking_floor()
            if target != self.callbacks.current_floor:
                self._park_target = target
                self.parking = True
                self.callbacks.motor_direction = (
                    UP if target > self.callbacks.current_floor else DOWN)

    def _preferred_parking_floor(self):
        """The median floor of recent demand; the home floor if unknown."""
        if not self._recent_origins:
            return self._home_floor
        ranked = sorted(self._recent_origins)
        return ranked[len(ranked) // 2]
