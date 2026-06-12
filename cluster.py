"""
A bank of elevators serving an office tower.

This builds on the passenger model in `simulation.py` and scales it up: a
group of cars shares one set of hall buttons in a building taller than any
single sweep is quick to cover. The interesting new problem is dispatch --
deciding which car answers which call.

The group controller here works like a modern destination-dispatch lobby:
when a passenger presses a hall button, the controller estimates each car's
time of arrival at that floor (idle distance, or distance along the current
sweep plus a toll per pending stop, or the round trip via the end of the
sweep) and assigns the call to the quickest car. A hall lantern tells the
passenger which car will serve them, so they board that car and only that
car. Same-direction calls on the same floor share one assignment.

Each car runs the unmodified LOOK logic from `elevator.py`, which never
needed to know how tall the building is. Cars have finite capacity: when a
car fills up, whoever is left on the landing is handed to the next-best car.

`make_logic` factories should bind the building's height where the logic
needs it -- e.g. `lambda: EfficientElevatorLogic(floors=floors)` -- since
the bank calls them with no arguments.

The scenario suite lives in CLUSTER.md. To run it:
$ python -m doctest CLUSTER.md -o NORMALIZE_WHITESPACE
"""
from elevator import ElevatorLogic, UP, DOWN

# Estimated ticks a car spends on each stop already on its plate.
STOP_COST = 2

CAR_NAMES = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'


class Car(object):
    def __init__(self, bank, name, starting_floor, make_logic):
        self.bank = bank
        self.name = name
        self.current_floor = starting_floor
        self.motor_direction = None
        self.logic = make_logic()
        self.logic.callbacks = self._Callbacks(self)
        self.riding = []

    @property
    def tag(self):
        """How this car appears in trace tokens: ' A', or nothing for the
        anonymous car of a single-elevator building."""
        return ' ' + self.name if self.name else ''

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

    def step(self):
        if self.motor_direction == UP:
            self._move(1)
        elif self.motor_direction == DOWN:
            self._move(-1)
        else:
            self.logic.on_ready()
            if self.motor_direction is None:
                self.bank._exchange(self)

        assert 1 <= self.current_floor <= self.bank.floors
        if self.motor_direction == UP:
            assert all(p.destination > self.current_floor for p in self.riding)
        elif self.motor_direction == DOWN:
            assert all(p.destination < self.current_floor for p in self.riding)

    def _move(self, delta):
        self.current_floor += delta
        self.bank._emit("%s%s..." % (self.name, self.current_floor))
        self.logic.on_floor_changed()
        if self.motor_direction is None:
            self.bank._exchange(self)


class ElevatorBank(object):
    """A building with several elevators behind one set of hall buttons."""

    _never_finished = "the bank never finished its work"

    def __init__(self, floors=11, cars=6, capacity=10, starting_floors=None,
                 verbose=True, make_logic=ElevatorLogic, car_names=None):
        self.floors = floors
        self.capacity = capacity
        self.verbose = verbose
        if starting_floors is None:
            starting_floors = [1] * cars
        assert len(starting_floors) == cars
        if car_names is None:
            car_names = CAR_NAMES
        self.cars = [Car(self, car_names[i], starting_floors[i], make_logic)
                     for i in range(cars)]
        self.time = 0
        self.arrivals = {}
        self.waiting = []
        self.delivered = []
        self.all_passengers = []

    def schedule(self, time, passenger):
        assert time > self.time
        assert 1 <= passenger.origin <= self.floors
        assert 1 <= passenger.destination <= self.floors
        self.arrivals.setdefault(time, []).append(passenger)
        self.all_passengers.append(passenger)

    def tick(self):
        self.time += 1
        for passenger in self.arrivals.pop(self.time, ()):
            passenger.arrived_at = self.time
            passenger.assigned_car = None
            self.waiting.append(passenger)
        for passenger in list(self.waiting):
            if passenger.assigned_car is None:
                self._place(passenger)
        for car in self.cars:
            car.step()

    def run(self, ticks):
        for _ in range(ticks):
            self.tick()

    def run_until_idle(self, limit=5000):
        for _ in range(limit):
            if self.idle:
                return
            self.tick()
        assert False, self._never_finished

    @property
    def idle(self):
        return (not self.arrivals and not self.waiting
                and all(car.motor_direction is None
                        and car.logic.direction is None
                        and not car.riding for car in self.cars))

    @property
    def everyone_delivered(self):
        return len(self.delivered) == len(self.all_passengers)

    @property
    def max_wait(self):
        return max(p.wait_time for p in self.delivered)

    @property
    def max_total_time(self):
        return max(p.total_time for p in self.delivered)

    @property
    def average_wait(self):
        waits = [p.wait_time for p in self.delivered]
        return round(sum(waits) / float(len(waits)), 2)

    def positions(self):
        print(' '.join('%s:%s' % (car.name, car.current_floor)
                       for car in self.cars))

    def report(self):
        for p in self.all_passengers:
            if p.delivered_at is None:
                print("%s: floor %s -> %s, STRANDED" % (p.name, p.origin, p.destination))
            else:
                print("%s: floor %s -> %s, car %s, waited %s, door to door %s"
                      % (p.name, p.origin, p.destination, p.assigned_car.name,
                         p.wait_time, p.total_time))

    # -- dispatch ---------------------------------------------------------

    def _place(self, passenger):
        """Board a passenger on the spot if possible, else assign them a car."""
        for car in self.cars:
            if (car.motor_direction is None
                    and car.current_floor == passenger.origin
                    and car.logic.direction in (None, passenger.direction)
                    and len(car.riding) < self.capacity):
                self.waiting.remove(passenger)
                self._board(passenger, car)
                return
        self._assign(passenger)

    def _assign(self, passenger):
        # Same-direction calls on the same floor share one car assignment.
        for other in self.waiting:
            if (other is not passenger and other.assigned_car is not None
                    and other.origin == passenger.origin
                    and other.direction == passenger.direction):
                passenger.assigned_car = other.assigned_car
                return
        # Never register a call with a car that would treat it as already
        # serviced (stopped at the floor, pointing the right way): if such a
        # car had room, _place would have boarded; it is full, so wait for it
        # to leave and try again next tick.
        candidates = [car for car in self.cars
                      if not (car.motor_direction is None
                              and car.current_floor == passenger.origin
                              and car.logic.direction in (None, passenger.direction))]
        if not candidates:
            return
        best = min(candidates,
                   key=lambda car: (self._estimate(car, passenger.origin,
                                                   passenger.direction), car.name))
        passenger.assigned_car = best
        best.logic.on_called(passenger.origin, passenger.direction)

    def _estimate(self, car, floor, direction):
        """Roughly how long this car needs to reach a hall call."""
        position = car.current_floor
        committed = car.logic.direction
        pending = len(car.logic.calls) + len(car.logic.selections)
        if committed is None:
            return abs(floor - position)
        on_the_way = (committed == direction
                      and ((committed == UP and floor >= position)
                           or (committed == DOWN and floor <= position)))
        if on_the_way:
            return abs(floor - position) + STOP_COST * pending
        # The car must ride out its sweep, then come back for this call.
        extent = self._sweep_extent(car)
        return (abs(extent - position) + abs(extent - floor)
                + STOP_COST * pending)

    def _sweep_extent(self, car):
        """The furthest floor the car is currently committed to."""
        floors = [call[0] for call in car.logic.calls]
        floors.extend(car.logic.selections)
        if car.logic.direction == UP:
            ahead = [f for f in floors if f > car.current_floor]
            return max(ahead) if ahead else car.current_floor
        ahead = [f for f in floors if f < car.current_floor]
        return min(ahead) if ahead else car.current_floor

    # -- passenger movement -----------------------------------------------

    def _exchange(self, car):
        floor = car.current_floor
        for passenger in [p for p in car.riding if p.destination == floor]:
            car.riding.remove(passenger)
            passenger.delivered_at = self.time
            self.delivered.append(passenger)
            self._emit("<%s out%s>" % (passenger.name, car.tag))
        boarded = 0
        while len(car.riding) < self.capacity:
            # Eligibility is rechecked after every boarder: the first one
            # may commit an idle car to a direction, shutting out waiting
            # passengers going the other way.
            eligible = [p for p in self.waiting if p.origin == floor
                        and p.assigned_car is car
                        and car.logic.direction in (None, p.direction)]
            if not eligible:
                break
            passenger = self._pick_boarder(car, eligible, boarded)
            self.waiting.remove(passenger)
            self._board(passenger, car)
            boarded += 1
        # Whoever could have boarded but found the car full goes back to the
        # dispatcher and is dealt to another car next tick.
        for passenger in self.waiting:
            if (passenger.origin == floor and passenger.assigned_car is car
                    and car.logic.direction in (None, passenger.direction)):
                passenger.assigned_car = None

    def _pick_boarder(self, car, eligible, boarded):
        """Which eligible passenger boards next: first come, first served."""
        return eligible[0]

    def _board(self, passenger, car):
        passenger.boarded_at = self.time
        passenger.assigned_car = car
        car.riding.append(passenger)
        self._emit("<%s in%s>" % (passenger.name, car.tag))
        car.logic.on_floor_selected(passenger.destination)

    def _emit(self, token):
        if self.verbose:
            print(token, end=' ')
