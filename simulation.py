"""
A more realistic simulation harness for the elevator challenge.

The README test harness drives the elevator by pressing its buttons directly.
Here we model the people instead: passengers arrive over time, press the call
button on their floor, board when the elevator stops going their way, select
their destination, and get off when they reach it. The simulation records how
long everybody waits, so scheduling regressions show up as stranded passengers
or blown wait-time bounds.

The mechanics -- the tick loop, the passenger exchange at each stop, the
per-tick safety invariants, and the recorded metrics -- live in the multi-car
harness in `cluster.py`. A `Building` is an `ElevatorBank` with one anonymous
car of unlimited capacity, so dispatch is trivial (every call goes to the only
car) and the trace reads `2... <Ann in>` rather than `A2... <Ann in A>`.

The scenario suite lives in SCENARIOS.md. To run it:
$ python -m doctest SCENARIOS.md -o NORMALIZE_WHITESPACE
"""
from cluster import ElevatorBank
from elevator import ElevatorLogic, UP, DOWN, FLOOR_COUNT


class Passenger(object):
    def __init__(self, name, origin, destination):
        assert origin != destination
        self.name = name
        self.origin = origin
        self.destination = destination
        self.arrived_at = None
        self.boarded_at = None
        self.delivered_at = None

    @property
    def direction(self):
        return UP if self.destination > self.origin else DOWN

    @property
    def wait_time(self):
        return self.boarded_at - self.arrived_at

    @property
    def total_time(self):
        return self.delivered_at - self.arrived_at


class Building(ElevatorBank):
    """
    Simulates one elevator together with the passengers using it.

    Each tick, passengers due to arrive show up and call the elevator, then
    the elevator moves one floor or pauses, exactly like the README harness.
    Whenever the elevator is stopped, riders at their destination get off and
    waiting passengers board, but only if the elevator is committed to the
    direction they want to go -- just like real people reading the direction
    indicator above the door.
    """

    _never_finished = "the elevator never finished its work"

    def __init__(self, logic=None, starting_floor=1, verbose=True,
                 floors=FLOOR_COUNT):
        if logic is None:
            logic = ElevatorLogic()
        ElevatorBank.__init__(self, floors=floors, cars=1,
                              capacity=float('inf'),
                              starting_floors=[starting_floor],
                              verbose=verbose, make_logic=lambda: logic,
                              car_names=[''])

    @property
    def logic(self):
        return self.cars[0].logic

    @property
    def current_floor(self):
        return self.cars[0].current_floor

    @property
    def motor_direction(self):
        return self.cars[0].motor_direction

    @property
    def riding(self):
        return self.cars[0].riding

    def press(self, floor, direction):
        """
        A call with nobody behind it, like an impatient passenger pressing
        both buttons, or someone who gives up and takes the stairs.
        """
        self.logic.on_called(floor, direction)

    def run_until_idle(self, limit=500):
        """Run until nothing is happening and nothing is scheduled to happen."""
        ElevatorBank.run_until_idle(self, limit)

    def report(self):
        for p in self.all_passengers:
            if p.delivered_at is None:
                print("%s: floor %s -> %s, STRANDED" % (p.name, p.origin, p.destination))
            else:
                print("%s: floor %s -> %s, waited %s, door to door %s"
                      % (p.name, p.origin, p.destination, p.wait_time, p.total_time))

    def _assign(self, passenger):
        # There is only one car, so every call goes straight to it. No
        # shared assignments either: the logic hears each passenger's call
        # individually, so its parking heuristic learns from all of them.
        passenger.assigned_car = self.cars[0]
        self.logic.on_called(passenger.origin, passenger.direction)
