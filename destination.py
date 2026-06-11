"""
Destination dispatch for the elevator bank: the system busy towers use.

In the conventional bank (`cluster.py`) the controller learns a passenger's
destination only when they board and press a button. A destination dispatch
system replaces the hall buttons with lobby kiosks: passengers key in their
destination *before* boarding, the controller assigns them a car on the
spot, and the kiosk display sends them to it. There are no buttons in the
car.

Knowing every origin-destination pair up front lets the controller do the
one thing that actually raises a bank's capacity: group passengers heading
to the same floor into the same car. A car that leaves the lobby for one or
two floors instead of seven turns around far sooner, and during a morning
rush the whole bank behaves like a set of express trains.

Assignment uses a marginal-cost rule, the heuristic real systems use:
for each car, estimate the passenger's pickup time, add a toll for every
*new* stop this passenger would add to the car's plate (scaled by how many
people are already on that plate, since they all suffer the new stop), and
heavily penalize a car whose boarding group is already at capacity. The
cheapest car wins. Passengers for an already-planned floor add no new stop,
so destination grouping emerges from the cost function by itself. The
capacity penalty is added on top of the grouping toll, never instead of
it, so even passengers queued behind a full boarding group keep
clustering by destination.

Boarding order matters just as much as assignment when a queue is deep:
a car that boards first come, first served from a long mixed queue
leaves on a milk run no matter how cleverly the queue was assigned. So
when a car opens its doors, the longest-waiting passenger boards first
(nobody is ever starved), everyone else bound for a floor the car is
already stopping at follows, and any space left over goes to the
largest destination group still on the landing.

Cars are unchanged: each runs the LOOK logic with anticipatory parking from
`efficient_elevator.py`, so idle cars drift back toward recent demand (the
lobby, during the morning) on their own.

The scenario suite lives in DESTINATION.md. To run it:
$ python -m doctest DESTINATION.md -o NORMALIZE_WHITESPACE
"""
from cluster import ElevatorBank, STOP_COST
from efficient_elevator import EfficientElevatorLogic

# Added to the assignment cost of a car whose boarding group is already
# full. Added, not substituted: the grouping toll must survive, or every
# passenger assigned past the first sixty loses destination affinity and
# full cars leave on milk runs exactly when demand peaks.
CAPACITY_PENALTY = 10000


class DestinationBank(ElevatorBank):
    def __init__(self, floors=11, cars=6, capacity=10, starting_floors=None,
                 verbose=True, make_logic=None):
        if make_logic is None:
            home = (floors + 1) // 2
            make_logic = lambda: EfficientElevatorLogic(home_floor=home)
        ElevatorBank.__init__(self, floors=floors, cars=cars,
                              capacity=capacity,
                              starting_floors=starting_floors,
                              verbose=verbose, make_logic=make_logic)

    # The kiosk: assign by marginal cost over full origin-destination
    # knowledge, instead of sharing hall calls per direction.

    def _place(self, passenger):
        car, board_now = self._choose(passenger)
        if car is None:
            return  # every suitable car is full at the landing; retry next tick
        if board_now:
            self.waiting.remove(passenger)
            self._board(passenger, car)
        else:
            passenger.assigned_car = car
            car.logic.on_called(passenger.origin, passenger.direction)

    def _choose(self, passenger):
        best, best_cost, best_now = None, None, False
        for car in self.cars:
            ready_here = (car.motor_direction is None
                          and car.current_floor == passenger.origin
                          and car.logic.direction in (None, passenger.direction))
            if ready_here and len(car.riding) >= self.capacity:
                continue  # full car blocking the landing
            cost = self._cost(car, passenger)
            if best_cost is None or (cost, car.name) < (best_cost, best.name):
                best, best_cost, best_now = car, cost, ready_here
        return best, best_now

    def _cost(self, car, passenger):
        eta = self._estimate(car, passenger.origin, passenger.direction)
        assigned = [q for q in self.waiting if q.assigned_car is car]
        planned = {q.origin for q in assigned}
        planned.update(q.destination for q in assigned)
        planned.update(q.destination for q in car.riding)
        if car.motor_direction is None:
            planned.add(car.current_floor)  # already stopped here
        new_stops = ((passenger.origin not in planned)
                     + (passenger.destination not in planned))
        plate = len(car.riding) + len(assigned)
        cost = eta + STOP_COST * new_stops * (1 + plate)
        boarding_group = [q for q in assigned
                          if q.origin == passenger.origin
                          and q.direction == passenger.direction]
        if len(boarding_group) >= self.capacity:
            cost += CAPACITY_PENALTY
        return cost

    # Boarding order: keep car loads destination-coherent even when the
    # landing queue is deeper than one car.

    def _pick_boarder(self, car, eligible, boarded):
        # Anyone bound for a floor already on the car's plate adds no
        # stop; among those, the longest-waiting boards first.
        joining = [p for p in eligible
                   if p.destination in car.logic.selections]
        if joining:
            return joining[0]
        # A new stop must be opened. The car's first boarder is always
        # the longest-waiting passenger, so nobody can be starved by a
        # parade of more popular floors behind them.
        if not boarded:
            return eligible[0]
        # Otherwise spend the remaining space on the floor that clears
        # the most people off the landing.
        groups = {}
        for p in eligible:
            groups.setdefault(p.destination, []).append(p)
        best = max(groups.values(),
                   key=lambda g: (len(g), -g[0].arrived_at))
        return best[0]
