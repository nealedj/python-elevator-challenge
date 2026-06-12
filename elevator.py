FLOOR_COUNT = 6


class Direction(int):
    UP = 1
    DOWN = 2

    def __invert__(self):
        if self == self.UP: return DOWN
        return UP


UP = Direction(Direction.UP)
DOWN = Direction(Direction.DOWN)


class ElevatorLogic(object):
    """
    Elevator business logic implementing a "sweep" algorithm.

    The elevator commits to a direction and services every request that lies
    ahead of it in that direction before turning around. While it is committed,
    floor selections that contradict the direction are ignored. Calls are never
    forgotten, but a call in the opposite direction is only serviced when the
    elevator has nothing left to do further ahead. When the elevator stops at a
    floor that called it in both directions, it clears one direction at a time,
    pausing once in between, like real elevators that close and reopen their
    doors to signal that they have turned around.

    The tests are integrated into `README.md`. To run the tests:
    $ python -m doctest README.md -o NORMALIZE_WHITESPACE
    """
    def __init__(self):
        self.callbacks = None
        # The direction the elevator considers itself to be going, which
        # persists while it is stopped. None means it is idle and free to go
        # either way.
        self.direction = None
        # Pending calls as (floor, direction) pairs, oldest first. An idle
        # elevator heads toward the floor that called first.
        self.calls = []
        # Floors selected from inside the elevator.
        self.selections = set()

    def on_called(self, floor, direction):
        """
        This is called when somebody presses the up or down button to call the elevator.
        This could happen at any time, whether or not the elevator is moving.
        The elevator could be requested at any floor at any time, going in either direction.

        floor: the floor that the elevator is being called to
        direction: the direction the caller wants to go, up or down
        """
        if (self._stopped and floor == self.callbacks.current_floor
                and self.direction in (None, direction)):
            # The elevator is already waiting here, going the right way, so
            # the call is serviced on the spot.
            return
        if (floor, direction) not in self.calls:
            self.calls.append((floor, direction))

    def on_floor_selected(self, floor):
        """
        This is called when somebody on the elevator chooses a floor.
        This could happen at any time, whether or not the elevator is moving.
        Any floor could be requested at any time.

        floor: the floor that was requested
        """
        towards = self._direction_to(floor)
        if towards is None:
            # Selecting the floor the elevator is already at does nothing. In
            # particular, a selection made just as the elevator passes the
            # floor has missed the boat.
            return
        if self.direction is not None and towards != self.direction:
            # The selection contradicts the current direction, so it is
            # ignored entirely.
            return
        self.direction = towards
        self.selections.add(floor)

    def on_floor_changed(self):
        """
        This lets you know that the elevator has moved one floor up or down.
        You should decide whether or not you want to stop the elevator.
        """
        floor = self.callbacks.current_floor
        moving = self.callbacks.motor_direction
        should_stop = False

        if floor in self.selections:
            self.selections.remove(floor)
            should_stop = True

        if (floor, moving) in self.calls:
            self.calls.remove((floor, moving))
            self.direction = moving
            should_stop = True
        elif (floor, ~moving) in self.calls and not self._requests_beyond(floor, moving):
            # Nothing requires going further, so the elevator stops for the
            # caller going the other way and turns around.
            self.calls.remove((floor, ~moving))
            self.direction = ~moving
            should_stop = True

        if should_stop:
            self.callbacks.motor_direction = None

    def on_ready(self):
        """
        This is called when the elevator is ready to go.
        Maybe passengers have embarked and disembarked. The doors are closed,
        time to actually move, if necessary.
        """
        floor = self.callbacks.current_floor

        if self.direction is None:
            # Idle: head toward the floor that called first.
            if self.calls:
                towards = self._direction_to(self.calls[0][0])
                if towards is None:
                    self.calls.pop(0)
                else:
                    self._set_motor(towards)
            return

        if self._requests_beyond(floor, self.direction):
            self._set_motor(self.direction)
        elif (floor, ~self.direction) in self.calls:
            # Reopen the doors for the caller going the other way. The old
            # direction is cleared, but the elevator waits one step before
            # moving on.
            self.calls.remove((floor, ~self.direction))
            self.direction = ~self.direction
        elif self._requests_beyond(floor, ~self.direction):
            self._set_motor(~self.direction)
        else:
            self.direction = None

    def _set_motor(self, direction):
        self.direction = direction
        self.callbacks.motor_direction = direction

    @property
    def _stopped(self):
        return self.callbacks.motor_direction is None

    def _requests_beyond(self, floor, direction):
        """Is any call or selection strictly beyond this floor, going this way?"""
        floors = [f for f, _ in self.calls]
        floors.extend(self.selections)
        if direction == UP:
            return any(f > floor for f in floors)
        return any(f < floor for f in floors)

    def _direction_to(self, floor):
        if floor > self.callbacks.current_floor: return UP
        if floor < self.callbacks.current_floor: return DOWN
        return None
