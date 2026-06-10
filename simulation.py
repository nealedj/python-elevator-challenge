"""
A more realistic simulation harness for the elevator challenge.

The README test harness drives the elevator by pressing its buttons directly.
Here we model the people instead: passengers arrive over time, press the call
button on their floor, board when the elevator stops going their way, select
their destination, and get off when they reach it. The simulation records how
long everybody waits, so scheduling regressions show up as stranded passengers
or blown wait-time bounds.

The scenario suite lives in SCENARIOS.md. To run it:
$ python -m doctest SCENARIOS.md -o NORMALIZE_WHITESPACE
"""
from elevator import ElevatorLogic, UP, DOWN, FLOOR_COUNT


class Passenger(object):
    def __init__(self, name, origin, destination):
        assert 1 <= origin <= FLOOR_COUNT
        assert 1 <= destination <= FLOOR_COUNT
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


class Building(object):
    """
    Simulates the elevator together with the passengers using it.

    Each tick, passengers due to arrive show up and call the elevator, then
    the elevator moves one floor or pauses, exactly like the README harness.
    Whenever the elevator is stopped, riders at their destination get off and
    waiting passengers board, but only if the elevator is committed to the
    direction they want to go -- just like real people reading the direction
    indicator above the door.
    """

    def __init__(self, logic=None, starting_floor=1, verbose=True):
        self.logic = logic if logic is not None else ElevatorLogic()
        self.current_floor = starting_floor
        self.motor_direction = None
        self.logic.callbacks = self._Callbacks(self)
        self.verbose = verbose
        self.time = 0
        self.arrivals = {}      # time -> passengers appearing then
        self.waiting = []       # at their floor, call button pressed
        self.riding = []
        self.delivered = []
        self.all_passengers = []

    class _Callbacks(object):
        def __init__(self, outer):
            self._outer = outer

        @property
        def current_floor(self):
            return self._outer.current_floor

        @property
        def motor_direction(self):
            return self._outer.motor_direction

        @motor_direction.setter
        def motor_direction(self, direction):
            self._outer.motor_direction = direction

    def schedule(self, time, passenger):
        """Have a passenger show up at their origin floor at the given time."""
        assert time > self.time
        self.arrivals.setdefault(time, []).append(passenger)
        self.all_passengers.append(passenger)

    def press(self, floor, direction):
        """
        A call with nobody behind it, like an impatient passenger pressing
        both buttons, or someone who gives up and takes the stairs.
        """
        self.logic.on_called(floor, direction)

    def tick(self):
        self.time += 1
        for passenger in self.arrivals.pop(self.time, ()):
            self._passenger_arrives(passenger)

        if self.motor_direction == UP:
            self._move(1)
        elif self.motor_direction == DOWN:
            self._move(-1)
        else:
            self.logic.on_ready()
            if self.motor_direction is None:
                self._exchange_passengers()

        assert self.current_floor >= 1
        assert self.current_floor <= FLOOR_COUNT
        if self.motor_direction == UP:
            assert all(p.destination > self.current_floor for p in self.riding)
        elif self.motor_direction == DOWN:
            assert all(p.destination < self.current_floor for p in self.riding)

    def run(self, ticks):
        for _ in range(ticks):
            self.tick()

    def run_until_idle(self, limit=500):
        """Run until nothing is happening and nothing is scheduled to happen."""
        for _ in range(limit):
            if self.idle:
                return
            self.tick()
        assert False, "the elevator never finished its work"

    @property
    def idle(self):
        return (self.motor_direction is None and self.logic.direction is None
                and not self.arrivals and not self.waiting and not self.riding)

    @property
    def everyone_delivered(self):
        return len(self.delivered) == len(self.all_passengers)

    @property
    def max_wait(self):
        return max(p.wait_time for p in self.delivered)

    @property
    def max_total_time(self):
        return max(p.total_time for p in self.delivered)

    def report(self):
        for p in self.all_passengers:
            if p.delivered_at is None:
                print("%s: floor %s -> %s, STRANDED" % (p.name, p.origin, p.destination))
            else:
                print("%s: floor %s -> %s, waited %s, door to door %s"
                      % (p.name, p.origin, p.destination, p.wait_time, p.total_time))

    def _passenger_arrives(self, passenger):
        passenger.arrived_at = self.time
        if (self.motor_direction is None and self.current_floor == passenger.origin
                and self.logic.direction in (None, passenger.direction)):
            # The elevator is already waiting here with its doors open.
            self._board(passenger)
        else:
            self.waiting.append(passenger)
            self.logic.on_called(passenger.origin, passenger.direction)

    def _move(self, delta):
        self.current_floor += delta
        self._emit("%s..." % self.current_floor)
        self.logic.on_floor_changed()
        if self.motor_direction is None:
            self._exchange_passengers()

    def _exchange_passengers(self):
        floor = self.current_floor
        for passenger in [p for p in self.riding if p.destination == floor]:
            self.riding.remove(passenger)
            passenger.delivered_at = self.time
            self.delivered.append(passenger)
            self._emit("<%s out>" % passenger.name)
        while True:
            # Board one at a time: the first boarder may commit an idle
            # elevator to a direction, shutting out passengers going the
            # other way.
            eligible = [p for p in self.waiting if p.origin == floor
                        and self.logic.direction in (None, p.direction)]
            if not eligible:
                break
            self.waiting.remove(eligible[0])
            self._board(eligible[0])

    def _board(self, passenger):
        passenger.boarded_at = self.time
        self.riding.append(passenger)
        self._emit("<%s in>" % passenger.name)
        self.logic.on_floor_selected(passenger.destination)

    def _emit(self, token):
        if self.verbose:
            print(token, end=' ')
