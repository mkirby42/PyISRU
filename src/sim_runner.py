from typing import Iterable, Optional, Dict, Any, List, Callable
from .resource_bus import ResourceBus, ResourceType
from .units import Q_, second, to_json_serializable


class SimulationEvent:
    def apply_if_due(self, *, t_prev: float, t_now: float, bus: ResourceBus, process, environment=None) -> None:
        raise NotImplementedError


class AddResourcesEvent(SimulationEvent):
    def __init__(self, at_seconds: float, additions: Dict[ResourceType, Q_]):
        self.at_seconds = float(at_seconds)
        self.additions = additions
        self._fired = False

    def apply_if_due(self, *, t_prev, t_now, bus: ResourceBus, process, environment=None):
        if not self._fired and t_prev < self.at_seconds <= t_now:
            for rt, qty in self.additions.items():
                bus.set_resource(rt, bus.get_resource(rt) + qty)
            self._fired = True


class RemoveResourcesEvent(SimulationEvent):
    def __init__(self, at_seconds: float, removals: Dict[ResourceType, Q_]):
        self.at_seconds = float(at_seconds)
        self.removals = removals
        self._fired = False

    def apply_if_due(self, *, t_prev, t_now, bus: ResourceBus, process, environment=None):
        if not self._fired and t_prev < self.at_seconds <= t_now:
            for rt, qty in self.removals.items():
                bus.consume_resource(rt, qty)
            self._fired = True


class RecurringAddResourcesEvent(SimulationEvent):
    def __init__(self, every_seconds: float, additions: Dict[ResourceType, Q_], start_seconds: float = 0.0, until_seconds: Optional[float] = None):
        self.every = float(every_seconds)
        self.additions = additions
        self.start = float(start_seconds)
        self.until = float(until_seconds) if until_seconds is not None else None
        self._next = self.start

    def apply_if_due(self, *, t_prev, t_now, bus: ResourceBus, process, environment=None):
        while t_prev < self._next <= t_now and (self.until is None or self._next <= self.until):
            for rt, qty in self.additions.items():
                bus.set_resource(rt, bus.get_resource(rt) + qty)
            self._next += self.every


class RecurringRemoveResourcesEvent(SimulationEvent):
    def __init__(self, every_seconds: float, removals: Dict[ResourceType, Q_], start_seconds: float = 0.0, until_seconds: Optional[float] = None):
        self.every = float(every_seconds)
        self.removals = removals
        self.start = float(start_seconds)
        self.until = float(until_seconds) if until_seconds is not None else None
        self._next = self.start

    def apply_if_due(self, *, t_prev, t_now, bus: ResourceBus, process, environment=None):
        while t_prev < self._next <= t_now and (self.until is None or self._next <= self.until):
            for rt, qty in self.removals.items():
                bus.consume_resource(rt, qty)
            self._next += self.every


class SimulationRunner:
    def __init__(self, *, bus: ResourceBus, process, dt: Q_, duration_seconds: float, log_interval_seconds: float = 5.0, save_interval_seconds: Optional[float] = None, events: Optional[Iterable[SimulationEvent]] = None, environment=None, on_log: Optional[Callable[[int, ResourceBus, Any], Dict[str, Any]]] = None, on_save: Optional[Callable[[int, ResourceBus, Any], Dict[str, Any]]] = None):
        self.bus = bus
        self.process = process
        self.dt = dt
        self.duration = float(duration_seconds)
        self.log_interval = float(log_interval_seconds)
        self.save_interval = float(save_interval_seconds) if save_interval_seconds is not None else None
        self.events: List[SimulationEvent] = list(events or [])
        self.environment = environment
        self.on_log = on_log
        self.on_save = on_save

    def run(self) -> Dict[int, Any]:
        history: Dict[int, Any] = {}
        t_prev = 0.0
        t_now = 0.0
        dt_s = float(self.dt.to(second).magnitude)
        next_log = 0.0
        next_save = 0.0 if self.save_interval is not None else None

        while t_now <= self.duration + 1e-12:
            # Apply events in (t_prev, t_now]
            for ev in self.events:
                ev.apply_if_due(t_prev=t_prev, t_now=t_now, bus=self.bus, process=self.process, environment=self.environment)

            # Build a single status snapshot when needed
            status_built = False
            status_snapshot: Optional[Dict[str, Any]] = None

            # Log
            if t_now + 1e-12 >= next_log:
                if not status_built:
                    status_snapshot = to_json_serializable(self.process.status())
                    status_built = True
                if self.on_log is not None:
                    extras = self.on_log(int(round(t_now)), self.bus, self.process) or {}
                    status_snapshot.update(extras)
                history[int(round(t_now))] = status_snapshot
                next_log += self.log_interval

            # Save (can be independent of log cadence)
            if next_save is not None and t_now + 1e-12 >= next_save:
                if not status_built:
                    status_snapshot = to_json_serializable(self.process.status())
                    status_built = True
                if self.on_save is not None:
                    extras = self.on_save(int(round(t_now)), self.bus, self.process) or {}
                    status_snapshot.update(extras)
                # Ensure snapshot is present in history for this time
                history.setdefault(int(round(t_now)), status_snapshot)
                next_save += self.save_interval

            # Advance
            if t_now > 0.0:
                self.process.tick(self.dt)

            t_prev, t_now = t_now, t_now + dt_s

        return history


def parse_events(raw_events: Optional[List[Dict[str, Any]]]) -> List[SimulationEvent]:
    events: List[SimulationEvent] = []
    if not raw_events:
        return events

    for ev in raw_events:
        ev_type = ev.get("type")
        resources = {
            ResourceType[key]: Q_(float(value), 'mol') for key, value in ev.get("resources", {}).items()
        }

        if ev_type == "add_resources":
            events.append(AddResourcesEvent(at_seconds=float(ev["at_seconds"]), additions=resources))
        elif ev_type == "remove_resources":
            events.append(RemoveResourcesEvent(at_seconds=float(ev["at_seconds"]), removals=resources))
        elif ev_type == "add_resources_recurring":
            events.append(RecurringAddResourcesEvent(
                every_seconds=float(ev["every_seconds"]),
                additions=resources,
                start_seconds=float(ev.get("start_seconds", 0.0)),
                until_seconds=ev.get("until_seconds")
            ))
        elif ev_type == "remove_resources_recurring":
            events.append(RecurringRemoveResourcesEvent(
                every_seconds=float(ev["every_seconds"]),
                removals=resources,
                start_seconds=float(ev.get("start_seconds", 0.0)),
                until_seconds=ev.get("until_seconds")
            ))
        else:
            raise ValueError(f"Unknown event type: {ev_type}")

    return events


