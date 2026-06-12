"""
An elevator simulation lab, grown from the classic elevator challenge.

The public API, layer by layer:

- `ElevatorLogic` -- the sweep ("LOOK") business logic the challenge in
  tests/CHALLENGE.md asks for, plus the `UP`/`DOWN` direction constants
  and the challenge's default `FLOOR_COUNT`.
- `EfficientElevatorLogic` -- LOOK plus anticipatory parking: an idle car
  relocates toward the median floor of recent demand.
- `Passenger` and `Building` -- the single-car passenger simulation
  (tests/SCENARIOS.md): arrivals over time, recorded waits, per-tick
  safety invariants.
- `ElevatorBank` -- six cars behind one set of hall buttons, with a group
  dispatcher assigning calls by estimated time of arrival
  (tests/CLUSTER.md).
- `DestinationBank` -- destination dispatch: lobby kiosks collect each
  passenger's destination before boarding, and the controller groups
  same-floor passengers into the same car (tests/DESTINATION.md).

`python -m elevators.benchmark` compares the two single-car dispatchers
over randomized traffic.
"""
from .elevator import ElevatorLogic, UP, DOWN, FLOOR_COUNT
from .efficient_elevator import EfficientElevatorLogic
from .simulation import Passenger, Building
from .cluster import ElevatorBank
from .destination import DestinationBank

__all__ = ['ElevatorLogic', 'EfficientElevatorLogic', 'Passenger',
           'Building', 'ElevatorBank', 'DestinationBank',
           'UP', 'DOWN', 'FLOOR_COUNT']
