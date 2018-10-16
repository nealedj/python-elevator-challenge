import operator


FLOOR_COUNT = 6

class Direction(int):
    UP = 1
    DOWN = 2

    def __invert__(self):
        if self == self.UP: return self.DOWN
        return self.UP


UP = Direction(Direction.UP)
DOWN = Direction(Direction.DOWN)


class ElevatorLogic(object):
    """
    An incorrect implementation. Can you make it pass all the tests?

    Fix the methods below to implement the correct logic for elevators.
    The tests are integrated into `README.md`. To run the tests:
    $ python -m doctest -v README.md

    To learn when each method is called, read its docstring.
    To interact with the world, you can get the current floor from the
    `current_floor` property of the `callbacks` object, and you can move the
    elevator by setting the `motor_direction` property. See below for how this is done.
    """
    def __init__(self):
        # Feel free to add any instance variables you want.
        self.destination_floor = None
        self.callbacks = None
        self.pickup_orders = []
        self.dropoff_orders = []

    def on_called(self, floor, direction):
        """
        This is called when somebody presses the up or down button to call the elevator.
        This could happen at any time, whether or not the elevator is moving.
        The elevator could be requested at any floor at any time, going in either direction.

        floor: the floor that the elevator is being called to
        direction: the direction the caller wants to go, up or down
        """
        if self._going_in_same_direction(floor) or not self.has_orders:
            self.pickup_orders.append((floor, direction))

    def on_floor_selected(self, floor):
        """
        This is called when somebody on the elevator chooses a floor.
        This could happen at any time, whether or not the elevator is moving.
        Any floor could be requested at any time.

        floor: the floor that was requested
        """
        self.dropoff_orders.append(floor)

    def on_floor_changed(self):
        """
        This lets you know that the elevator has moved one floor up or down.
        You should decide whether or not you want to stop the elevator.
        """
        current_floor = self.callbacks.current_floor

        # if anybody wants to get off at the current floor, stop
        if current_floor in self.dropoff_orders:
            self.dropoff_orders.remove(current_floor)
            self.pause()
            return

        # if somebody wants to be picked up to go in the same direction as the elevator, stop
        same_direction_order = (current_floor, self.callbacks.motor_direction)
        if same_direction_order in self.pickup_orders:
            self.pickup_orders.remove(same_direction_order)
            self.pause()
            return

        # if there are dropoff orders in the same direction that the lift is going then keep going
        up_floors, down_floors = self._split_up_down_dropoff_orders(current_floor)
        if ((self.going_down and down_floors) or (self.going_up and up_floors)):
            # keep going
            return

        # if somebody wants to be picked up to go in the opposite direction of the lift then stop
        opposite_direction_order = (current_floor, ~self.callbacks.motor_direction)
        if opposite_direction_order in self.pickup_orders:
            self.pickup_orders.remove(opposite_direction_order)
            self.pause()
            return

        # if not self.has_orders:
        #     self.pause()

    def on_ready(self):
        """
        This is called when the elevator is ready to go.
        Maybe passengers have embarked and disembarked. The doors are closed,
        time to actually move, if necessary.
        """
        current_floor = self.callbacks.current_floor

        destination_floor, preferred_direction = self._get_destination_floor()
        if destination_floor > current_floor:
            self.callbacks.motor_direction = UP
        elif destination_floor < current_floor:
            self.callbacks.motor_direction = DOWN

    def pause(self):
        self.callbacks.motor_direction = None

    @property
    def going_up(self):
        return self.callbacks.motor_direction == UP

    @property
    def going_down(self):
        return self.callbacks.motor_direction == DOWN

    @property
    def stopped(self):
        return not self.callbacks.motor_direction

    @property
    def has_orders(self):
        return self.pickup_orders or self.dropoff_orders

    def _split_up_down_dropoff_orders(self, current_floor):
        grouped = {
            current_floor < order: order
            for order in self.dropoff_orders
            if order != current_floor
        }

        up, down = grouped.get(True, []), grouped.get(False, [])
        return up, down

    def _get_destination_floor(self):
        dropoff_floor = next(iter(self.dropoff_orders), None)
        order = next(iter(self.pickup_orders), None)
        if dropoff_floor:
            return dropoff_floor, self._get_direction_to_floor(dropoff_floor)
        
        if order:
            return order

        return None, None

    def _going_in_same_direction(self, floor):
        direction_to_floor = self._get_direction_to_floor(floor)
        current_direction = self.callbacks.motor_direction
        pending_direction = self._get_destination_floor()[1]

        return (
            direction_to_floor == current_direction or
            direction_to_floor == pending_direction
        )

    def _get_direction_to_floor(self, floor):
        op_map = (
            (operator.lt, Direction.DOWN),
            (operator.gt, Direction.UP),
            (operator.eq, None),
        )
        return next(
            value for op, value in op_map
            if op(floor, self.callbacks.current_floor)
        )

    def status(self):
        print("""
dropoff_orders: {},
self.pickup_orders: {},
current_floor: {},
motor_direction: {}
""".format(
    self.dropoff_orders,
    self.pickup_orders,
    self.callbacks.current_floor,
    self.callbacks.motor_direction
))
