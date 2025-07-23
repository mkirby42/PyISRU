from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Any
import math

# ---------------------------------------------------------------------------
# 1. Parameter & State dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SimParams:
    """Container for all *tunables* consumable by optimisers."""
    # Fleet sizes & production ------------------------------------------------
    crew_line_capacity: int = 1
    cargo_line_capacity: int = 1
    tanker_line_capacity: int = 3

    crew_build_time_months: float = 6.0
    cargo_build_time_months: float = 8.0
    tanker_build_time_months: float = 3.0

    crew_ship_lifespan: int = 12  # missions
    cargo_ship_lifespan: int = 12
    tanker_lifespan: int = 120    # flights

    # Mission architecture ----------------------------------------------------
    n_people_per_ship: int = 100
    cargo_mass_per_ship: float = 100.0  # tonnes
    fuel_per_mars_mission: float = 1200.0  # tonnes
    fuel_per_tanker: float = 1200.0       # tonnes per tanker flight

    launch_window_interval_days: int = 780
    transit_time_days: int = 250
    mars_wait_time_days: int = 540
    tanker_turnaround_days: int = 5

    # Simulation horizon ------------------------------------------------------
    total_simulation_days: int = 25 * 365

    # Objective target --------------------------------------------------------
    people_goal: int = 10_000
    cargo_goal: float = 50_000  # tonnes
    
    @property
    def mission_duration_days(self) -> int:
        """Total round trip time: transit + wait + transit back"""
        return self.transit_time_days * 2 + self.mars_wait_time_days


@dataclass
class SimState:
    """The mutable simulation state snapshot for a single day."""

    day: int = 0

    people_at_mars: int = 0
    cargo_at_mars: float = 0.0

    fuel_depot: float = 0.0

    crew_fleet: List[Dict[str, Any]] = field(default_factory=list)  # each: {id, missions}
    cargo_fleet: List[Dict[str, Any]] = field(default_factory=list)
    tanker_fleet: List[Dict[str, Any]] = field(default_factory=list)  # {id, last_flight_day, missions}

    crew_returning: List[tuple] = field(default_factory=list)   # (return_day, [ship dicts])
    cargo_returning: List[tuple] = field(default_factory=list)

    ships_arriving_mars: List[tuple] = field(default_factory=list)  # (arrival_day, crew_count, cargo_count)

    mars_fuel_demand_cum: float = 0.0

    # Manufacturing system (CRITICAL MISSING PIECE) --------------------------
    ships_under_construction: List[Dict[str, Any]] = field(default_factory=list)  # {type, id, completion_day}
    next_ship_id: int = 0

    # Historical record (append‑only) ----------------------------------------
    history: List[Dict[str, Any]] = field(default_factory=list)

# ---------------------------------------------------------------------------
# 2. Initialisers
# ---------------------------------------------------------------------------

def initialise_state(params: SimParams) -> SimState:
    """Create an empty state and optionally seed with initial fleet."""
    state = SimState()
    state.next_ship_id = 100  # Start IDs at 100 to avoid conflicts with seed ships
    
    # Example: seed a starter fleet (could move to params)
    # Initialize tankers ready to fly immediately by setting last_flight_day far in the past
    for i in range(3):
        state.tanker_fleet.append({
            "id": f"t{i}", 
            "last_flight_day": -params.tanker_turnaround_days, 
            "missions": 0
        })
    # Initialize some initial crew and cargo ships
    for i in range(1):
        state.crew_fleet.append({"id": f"c{i}", "missions": 0})
        state.cargo_fleet.append({"id": f"g{i}", "missions": 0})
    
    # Start initial ship construction to prime the manufacturing pipeline
    # This mimics having an ongoing production program
    for i in range(params.crew_line_capacity):
        completion_day = int(params.crew_build_time_months * 30 * (i + 1) / params.crew_line_capacity)
        state.ships_under_construction.append({
            'type': 'crew',
            'id': state.next_ship_id,
            'completion_day': completion_day
        })
        state.next_ship_id += 1
        
    for i in range(params.cargo_line_capacity):
        completion_day = int(params.cargo_build_time_months * 30 * (i + 1) / params.cargo_line_capacity)
        state.ships_under_construction.append({
            'type': 'cargo',
            'id': state.next_ship_id,
            'completion_day': completion_day
        })
        state.next_ship_id += 1
        
    for i in range(params.tanker_line_capacity):
        completion_day = int(params.tanker_build_time_months * 30 * (i + 1) / params.tanker_line_capacity)
        state.ships_under_construction.append({
            'type': 'tanker',
            'id': state.next_ship_id,
            'completion_day': completion_day
        })
        state.next_ship_id += 1
    
    return state

# ---------------------------------------------------------------------------
# 3. One‑day state transition
# ---------------------------------------------------------------------------

def step(state: SimState, params: SimParams) -> SimState:
    """Advance simulation by *one day*. Mutates and returns the same state.
    Now includes full ship lifecycle management from the original implementation.
    """
    d = state.day

    # 3.0 MANUFACTURING SYSTEM (CRITICAL MISSING PIECE) ---------------------
    # Check for ship completions
    completed_ships = [ship for ship in state.ships_under_construction if ship['completion_day'] == d]
    state.ships_under_construction = [ship for ship in state.ships_under_construction if ship['completion_day'] != d]
    
    # Add completed ships to active fleets
    for ship in completed_ships:
        if ship['type'] == 'crew':
            state.crew_fleet.append({'id': ship['id'], 'missions': 0})
        elif ship['type'] == 'cargo':
            state.cargo_fleet.append({'id': ship['id'], 'missions': 0})
        elif ship['type'] == 'tanker':
            state.tanker_fleet.append({'id': ship['id'], 'missions': 0, 'last_flight_day': -params.tanker_turnaround_days})
    
    # Start new ship construction (whenever production line has capacity)
    crew_under_construction = len([s for s in state.ships_under_construction if s['type'] == 'crew'])
    cargo_under_construction = len([s for s in state.ships_under_construction if s['type'] == 'cargo'])
    tanker_under_construction = len([s for s in state.ships_under_construction if s['type'] == 'tanker'])
    
    # Start crew ship if line has capacity
    if crew_under_construction < params.crew_line_capacity:
        completion_day = d + int(params.crew_build_time_months * 30)  # Convert months to days
        state.ships_under_construction.append({
            'type': 'crew',
            'id': state.next_ship_id,
            'completion_day': completion_day
        })
        state.next_ship_id += 1
    
    # Start cargo ship if line has capacity
    if cargo_under_construction < params.cargo_line_capacity:
        completion_day = d + int(params.cargo_build_time_months * 30)  # Convert months to days
        state.ships_under_construction.append({
            'type': 'cargo',
            'id': state.next_ship_id,
            'completion_day': completion_day
        })
        state.next_ship_id += 1
    
    # Start tanker if line has capacity
    if tanker_under_construction < params.tanker_line_capacity:
        completion_day = d + int(params.tanker_build_time_months * 30)  # Convert months to days
        state.ships_under_construction.append({
            'type': 'tanker',
            'id': state.next_ship_id,
            'completion_day': completion_day
        })
        state.next_ship_id += 1

    # 3.1 Ships returning from Mars ------------------------------------------
    returning_crew_missions = [item for item in state.crew_returning if item[0] == d]
    returning_cargo_missions = [item for item in state.cargo_returning if item[0] == d]
    
    # Process crew ship returns
    for return_day, ship_list in returning_crew_missions:
        for ship in ship_list:
            # Only add back ships that haven't exceeded their lifespan
            if ship['missions'] < params.crew_ship_lifespan:
                state.crew_fleet.append(ship)
    
    # Process cargo ship returns
    for return_day, ship_list in returning_cargo_missions:
        for ship in ship_list:
            # Only add back ships that haven't exceeded their lifespan
            if ship['missions'] < params.cargo_ship_lifespan:
                state.cargo_fleet.append(ship)
    
    # Remove processed returns from tracking
    state.crew_returning = [item for item in state.crew_returning if item[0] != d]
    state.cargo_returning = [item for item in state.cargo_returning if item[0] != d]

    # 3.2 Ship retirement based on mission counts ----------------------------
    state.crew_fleet = [ship for ship in state.crew_fleet if ship['missions'] < params.crew_ship_lifespan]
    state.cargo_fleet = [ship for ship in state.cargo_fleet if ship['missions'] < params.cargo_ship_lifespan]

    # 3.3 Daily tanker operations with proper turnaround --------------------
    if len(state.tanker_fleet) > 0:
        # Find tankers ready to fly (turnaround time has passed)
        ready_tankers = []
        for tanker in state.tanker_fleet:
            days_since_last_flight = d - tanker['last_flight_day']
            if days_since_last_flight >= params.tanker_turnaround_days:
                ready_tankers.append(tanker)
        
        # Fly all ready tankers
        if ready_tankers:
            daily_fuel_delivery = len(ready_tankers) * params.fuel_per_tanker
            state.fuel_depot += daily_fuel_delivery
            
            # Update flight records for tankers that flew
            for tanker in ready_tankers:
                tanker['missions'] += 1
                tanker['last_flight_day'] = d
    
    # Retire tankers that exceed their mission lifespan (after completing flights)
    state.tanker_fleet = [tk for tk in state.tanker_fleet if tk['missions'] < params.tanker_lifespan]

    # 3.4 Calculate Mars fuel demand from ships arriving today ---------------
    daily_mars_fuel_demand = 0
    arriving_ships_today = [item for item in state.ships_arriving_mars if item[0] == d]
    for arrival_day, crew_count, cargo_count in arriving_ships_today:
        # Each ship needs fuel for return journey (Mars -> Earth)
        total_ships = crew_count + cargo_count
        daily_mars_fuel_demand += total_ships * params.fuel_per_mars_mission
    
    # Remove processed arrivals and update cumulative demand
    state.ships_arriving_mars = [item for item in state.ships_arriving_mars if item[0] != d]
    state.mars_fuel_demand_cum += daily_mars_fuel_demand

    # 3.5 Launch window check ------------------------------------------------
    if d > 0 and d % params.launch_window_interval_days == 0:
        crew_avail = len(state.crew_fleet)
        cargo_avail = len(state.cargo_fleet)
        total_avail = crew_avail + cargo_avail
        
        if total_avail > 0:
            ships_possible = math.floor(state.fuel_depot / params.fuel_per_mars_mission)
            ships_to_launch = min(total_avail, ships_possible)
            
            # Simple proportional allocation
            if total_avail > 0:
                crew_to_launch = min(crew_avail, math.floor(ships_to_launch * crew_avail / total_avail))
                cargo_to_launch = ships_to_launch - crew_to_launch
            else:
                crew_to_launch = cargo_to_launch = 0

            if ships_to_launch > 0:
                # Update Mars counts
                state.people_at_mars += crew_to_launch * params.n_people_per_ship
                state.cargo_at_mars += cargo_to_launch * params.cargo_mass_per_ship
                state.fuel_depot -= ships_to_launch * params.fuel_per_mars_mission

                # Track launched ships for return scheduling
                launched_crew_ships = state.crew_fleet[:crew_to_launch]
                launched_cargo_ships = state.cargo_fleet[:cargo_to_launch]
                
                # Remove launched ships from available fleet
                state.crew_fleet = state.crew_fleet[crew_to_launch:]
                state.cargo_fleet = state.cargo_fleet[cargo_to_launch:]
                
                # Increment mission count for launched ships
                for ship in launched_crew_ships:
                    ship['missions'] += 1
                for ship in launched_cargo_ships:
                    ship['missions'] += 1
                
                # Schedule ship returns (after full round trip)
                return_day = d + params.mission_duration_days
                if crew_to_launch > 0:
                    state.crew_returning.append((return_day, launched_crew_ships))
                if cargo_to_launch > 0:
                    state.cargo_returning.append((return_day, launched_cargo_ships))
                
                # Schedule Mars arrival for fuel demand tracking
                mars_arrival_day = d + params.transit_time_days
                if crew_to_launch > 0 or cargo_to_launch > 0:
                    state.ships_arriving_mars.append((mars_arrival_day, crew_to_launch, cargo_to_launch))

    # 3.6 Record daily state -------------------------------------------------
    state.history.append({
        "day": d,
        "people": state.people_at_mars,
        "cargo": state.cargo_at_mars,
        "fuel_depot": state.fuel_depot,
        "crew": len(state.crew_fleet),
        "cargo_fleet": len(state.cargo_fleet),
        "tankers": len(state.tanker_fleet),
        "mars_fuel_demand": state.mars_fuel_demand_cum,
    })

    # Advance clock
    state.day += 1
    return state

# ---------------------------------------------------------------------------
# 4. Full simulation run
# ---------------------------------------------------------------------------

def simulate(params: SimParams) -> SimState:
    state = initialise_state(params)
    for _ in range(params.total_simulation_days):
        step(state, params)
    return state

# ---------------------------------------------------------------------------
# 5. Objective for optimisers
# ---------------------------------------------------------------------------

def objective(param_vector: List[float]) -> float:
    """Example objective: minimise years to reach params.people_goal on Mars.
    decode_params() converts the flat numeric vector into a SimParams instance.
    """
    params = decode_params(param_vector)
    result_state = simulate(params)
    # find first day goal achieved
    for rec in result_state.history:
        if rec["people"] >= params.people_goal:
            return rec["day"] / 365.0
    # goal not reached -> penalise heavily
    return 1e6

# ---------------------------------------------------------------------------
# 6. Parameter decoding helper
# ---------------------------------------------------------------------------

def decode_params(v: List[float]) -> SimParams:
    """Map raw optimiser vector -> SimParams. Adjust indices/bounds as needed."""
    return SimParams(
        crew_line_capacity=int(v[0]),
        cargo_line_capacity=int(v[1]),
        tanker_line_capacity=int(v[2]),
        crew_build_time_months=v[3],
        cargo_build_time_months=v[4],
        tanker_build_time_months=v[5],
        n_people_per_ship=int(v[6]),
        cargo_mass_per_ship=v[7],
        fuel_per_tanker=v[8],
        fuel_per_mars_mission=v[9],
        # Extend ship lifespans for optimization - bottleneck was ship retirement
        crew_ship_lifespan=50,  # Much longer lifespan
        cargo_ship_lifespan=50,  # Much longer lifespan
        tanker_lifespan=500,     # Much longer lifespan
        total_simulation_days=int(25 * 365),  # 25 years for dual constraints
        people_goal=5000,  # Set our target to 5000 people
        cargo_goal=110000,  # Set our target to 110,000 tons cargo
    )

# ---------------------------------------------------------------------------
# 7. Optimization setup for 5000 people
# ---------------------------------------------------------------------------

def optimize_for_dual_goals():
    """Use scipy.optimize to find optimal parameters for 5000 people + 110,000 tons cargo on Mars."""
    from scipy.optimize import differential_evolution
    import time
    
    print("🚀 Optimizing Mars transport parameters for 5000 people + 110,000 tons cargo...")
    print("This may take a few minutes...\n")
    
    # Parameter bounds: [min, max] for each parameter  
    # Realistic ranges for achieving 5000 people efficiently
    bounds = [
        (1, 1),      # crew_line_capacity - realistic industrial scale
        (1, 1),      # cargo_line_capacity - realistic industrial scale
        (1, 2),     # tanker_line_capacity - enough fuel production
        (1, 6),       # crew_build_time_months - achievable build times
        (1, 6),       # cargo_build_time_months - achievable build times
        (1, 6),       # tanker_build_time_months - simpler tankers build faster
        (100, 150),   # n_people_per_ship - reasonable ship sizes
        (80, 150),    # cargo_mass_per_ship - reasonable cargo capacity
        (80, 150),    # fuel_per_tanker - reasonable tanker capacity
        (1400, 1600), # fuel_per_mars_mission - realistic fuel needs
    ]
    
    def objective_wrapper(param_vector):
        """Wrapper that adds some logging and error handling."""
        try:
            params = decode_params(param_vector)
            result_state = simulate(params)
            
            # Find first day BOTH goals are achieved
            people_achieved_day = None
            cargo_achieved_day = None
            
            for rec in result_state.history:
                if people_achieved_day is None and rec["people"] >= params.people_goal:
                    people_achieved_day = rec["day"]
                if cargo_achieved_day is None and rec["cargo"] >= params.cargo_goal:
                    cargo_achieved_day = rec["day"]
                
                # If both goals achieved, we can stop
                if people_achieved_day is not None and cargo_achieved_day is not None:
                    break
            
            if hasattr(objective_wrapper, 'call_count'):
                objective_wrapper.call_count += 1
            else:
                objective_wrapper.call_count = 1
            
            # If both goals achieved, return the later of the two dates
            if people_achieved_day is not None and cargo_achieved_day is not None:
                final_day = max(people_achieved_day, cargo_achieved_day)
                years = final_day / 365.0
                
                if objective_wrapper.call_count % 10 == 0:
                    people_years = people_achieved_day / 365.0
                    cargo_years = cargo_achieved_day / 365.0
                    print(f"Evaluation {objective_wrapper.call_count}: {years:.2f} years (people: {people_years:.2f}y, cargo: {cargo_years:.2f}y)")
                    
                return years
            
            # Goals not reached - return penalty but show what we achieved
            final_people = result_state.history[-1]["people"] if result_state.history else 0
            final_cargo = result_state.history[-1]["cargo"] if result_state.history else 0
            
            if objective_wrapper.call_count % 10 == 0:
                print(f"Evaluation {objective_wrapper.call_count}: Only reached {final_people} people, {final_cargo:.0f} cargo in {params.total_simulation_days/365:.1f} years")
                
            return 1e6
            
        except Exception as e:
            print(f"Error in simulation: {e}")
            return 1e6  # Return penalty for failed simulations
    
    start_time = time.time()
    
    # Run optimization
    result = differential_evolution(
        objective_wrapper,
        bounds,
        seed=42,
        maxiter=50,     # Fewer iterations since we expect faster convergence
        popsize=10,     # Smaller population for faster execution
        atol=0.1,
        tol=0.01
    )
    
    elapsed_time = time.time() - start_time
    
    print(f"\n🎯 Optimization completed in {elapsed_time:.1f} seconds!")
    print(f"📊 Function evaluations: {result.nfev}")
    print(f"⏱️  Optimal time to reach both goals: {result.fun:.2f} years")
    print(f"✅ Optimization {'converged' if result.success else 'did not converge'}")
    
    # Decode optimal parameters
    optimal_params = decode_params(result.x)
    
    print(f"\n🏭 Optimal Parameters:")
    print(f"   Crew Line Capacity: {optimal_params.crew_line_capacity}")
    print(f"   Cargo Line Capacity: {optimal_params.cargo_line_capacity}")
    print(f"   Tanker Line Capacity: {optimal_params.tanker_line_capacity}")
    print(f"   Crew Build Time: {optimal_params.crew_build_time_months:.1f} months")
    print(f"   Cargo Build Time: {optimal_params.cargo_build_time_months:.1f} months")
    print(f"   Tanker Build Time: {optimal_params.tanker_build_time_months:.1f} months")
    print(f"   People per Ship: {optimal_params.n_people_per_ship}")
    print(f"   Cargo per Ship: {optimal_params.cargo_mass_per_ship:.0f} tons")
    print(f"   Fuel per Tanker: {optimal_params.fuel_per_tanker:.0f} tons")
    print(f"   Fuel per Mission: {optimal_params.fuel_per_mars_mission:.0f} tons")
    
    # Run final simulation with optimal parameters
    print(f"\n📈 Running final simulation...")
    final_state = simulate(optimal_params)
    
    # Find when we hit both goals
    people_day = cargo_day = None
    for rec in final_state.history:
        if people_day is None and rec["people"] >= optimal_params.people_goal:
            people_day = rec['day']
        if cargo_day is None and rec["cargo"] >= optimal_params.cargo_goal:
            cargo_day = rec['day']
        if people_day and cargo_day:
            break
    
    if people_day and cargo_day:
        final_day = max(people_day, cargo_day)
        print(f"🎉 Reached both goals on day {final_day} ({final_day/365:.2f} years)")
        print(f"   People goal reached: day {people_day} ({people_day/365:.2f} years)")
        print(f"   Cargo goal reached: day {cargo_day} ({cargo_day/365:.2f} years)")
        final_rec = next(rec for rec in final_state.history if rec['day'] == final_day)
        print(f"   Final people: {final_rec['people']}")
        print(f"   Final cargo: {final_rec['cargo']:.0f} tons")
        print(f"   Final fuel depot: {final_rec['fuel_depot']:.0f} tons")
    
    return optimal_params, result

# ---------------------------------------------------------------------------
# 9. Scaling test to understand bottlenecks
# ---------------------------------------------------------------------------

def test_extreme_scaling():
    """Test with extreme parameters to understand scaling bottlenecks."""
    print("🔬 Testing extreme scaling parameters...")
    
    # Very aggressive parameters
    extreme_params = SimParams(
        crew_line_capacity=100,       # Massive production
        cargo_line_capacity=100,      # Massive production
        tanker_line_capacity=200,     # Massive fuel production
        crew_build_time_months=1,     # Very fast builds
        cargo_build_time_months=1,    # Very fast builds
        tanker_build_time_months=1,   # Very fast builds
        n_people_per_ship=200,        # Huge ships
        cargo_mass_per_ship=200,      # Huge cargo
        fuel_per_tanker=200,          # Huge tankers
        fuel_per_mars_mission=1000,   # Efficient missions
        crew_ship_lifespan=50,        # Much longer lifespan
        cargo_ship_lifespan=50,       # Much longer lifespan  
        tanker_lifespan=500,          # Much longer lifespan
        total_simulation_days=30 * 365,  # 30 years
        people_goal=5000,
        cargo_goal=110000
    )
    
    print("Parameters:")
    print(f"  Production lines: {extreme_params.crew_line_capacity} crew, {extreme_params.cargo_line_capacity} cargo, {extreme_params.tanker_line_capacity} tanker")
    print(f"  Build times: {extreme_params.crew_build_time_months}mo crew, {extreme_params.cargo_build_time_months}mo cargo, {extreme_params.tanker_build_time_months}mo tanker")
    print(f"  Ship capacity: {extreme_params.n_people_per_ship} people, {extreme_params.cargo_mass_per_ship} tons cargo")
    print(f"  Fuel: {extreme_params.fuel_per_tanker} tons/tanker, {extreme_params.fuel_per_mars_mission} tons/mission")
    
    result_state = simulate(extreme_params)
    
    # Analyze results
    max_people = max(rec["people"] for rec in result_state.history)
    final_people = result_state.history[-1]["people"]
    max_crew_ships = max(rec["crew"] for rec in result_state.history)
    max_fuel = max(rec["fuel_depot"] for rec in result_state.history)
    
    print(f"\n📊 Results after 30 years:")
    print(f"  Max people reached: {max_people}")
    print(f"  Final people: {final_people}")
    print(f"  Max crew ships available: {max_crew_ships}")
    print(f"  Max fuel depot: {max_fuel:.0f} tons")
    
    # Check if we hit 5000
    for rec in result_state.history:
        if rec["people"] >= 5000:
            print(f"🎉 Reached 5000 people on day {rec['day']} ({rec['day']/365:.2f} years)")
            break
    else:
        print(f"❌ Did not reach 5000 people in 30 years")
    
    # Show a few data points to understand the trajectory
    print(f"\n📈 Growth trajectory (every 5 years):")
    for rec in result_state.history:
        if rec["day"] % (5 * 365) == 0:
            year = rec["day"] / 365
            print(f"  Year {year:.0f}: {rec['people']} people, {rec['crew']} crew ships, {rec['fuel_depot']:.0f} fuel")
    
    return result_state

def debug_ship_lifecycle():
    """Debug version to understand what happens to ships."""
    print("🔍 Debugging ship lifecycle with simple parameters...")
    
    debug_params = SimParams(
        crew_line_capacity=5,
        cargo_line_capacity=5,
        tanker_line_capacity=10,
        crew_build_time_months=2,
        cargo_build_time_months=2,
        tanker_build_time_months=1,
        n_people_per_ship=100,
        cargo_mass_per_ship=100,
        fuel_per_tanker=100,
        fuel_per_mars_mission=1000,
        crew_ship_lifespan=50,
        cargo_ship_lifespan=50,
        tanker_lifespan=500,
        total_simulation_days=10 * 365,  # 10 years for detailed tracking
        people_goal=1000,
        cargo_goal=5000
    )
    
    state = initialise_state(debug_params)
    
    print(f"Initial state: {len(state.crew_fleet)} crew ships, {len(state.cargo_fleet)} cargo ships")
    print(f"Launch windows every {debug_params.launch_window_interval_days} days")
    print(f"Mission duration: {debug_params.mission_duration_days} days")
    print()
    
    for day in range(0, 2000):  # First ~5.5 years in detail
        old_crew_count = len(state.crew_fleet)
        old_cargo_count = len(state.cargo_fleet)
        
        step(state, debug_params)
        
        new_crew_count = len(state.crew_fleet)
        new_cargo_count = len(state.cargo_fleet)
        
        # Log important events
        if day % debug_params.launch_window_interval_days == 0 and day > 0:
            print(f"Day {day} (Year {day/365:.1f}) - LAUNCH WINDOW:")
            print(f"  Crew ships: {old_crew_count} → {new_crew_count}")
            print(f"  Cargo ships: {old_cargo_count} → {new_cargo_count}")
            print(f"  People at Mars: {state.people_at_mars}")
            print(f"  Fuel depot: {state.fuel_depot:.0f}")
            print(f"  Ships returning tracked: {len(state.crew_returning)} crew missions, {len(state.cargo_returning)} cargo missions")
            print()
        
        # Log when ships return
        if len(state.crew_returning) > 0:
            returning_today = [item for item in state.crew_returning if item[0] == day+1]
            if returning_today:
                for return_day, ship_list in returning_today:
                    print(f"Day {day+1}: {len(ship_list)} crew ships returning from Mars")
        
        if len(state.cargo_returning) > 0:
            returning_today = [item for item in state.cargo_returning if item[0] == day+1]
            if returning_today:
                for return_day, ship_list in returning_today:
                    print(f"Day {day+1}: {len(ship_list)} cargo ships returning from Mars")
    
    return state

def diagnose_launch_sequence():
    """Detailed diagnosis of launch windows to find the bottleneck."""
    print("🔬 Diagnosing launch sequence with high-production parameters...")
    
    # Use promising parameters from optimization
    diag_params = SimParams(
        crew_line_capacity=50,        # High production
        cargo_line_capacity=50,       # High production
        tanker_line_capacity=200,     # Very high fuel production
        crew_build_time_months=2,     # Fast builds
        cargo_build_time_months=2,    # Fast builds
        tanker_build_time_months=1,   # Very fast builds
        n_people_per_ship=200,        # Large ships
        cargo_mass_per_ship=150,      
        fuel_per_tanker=200,          # Large tankers
        fuel_per_mars_mission=1200,   # Efficient missions
        crew_ship_lifespan=50,        
        cargo_ship_lifespan=50,       
        tanker_lifespan=500,          
        total_simulation_days=20 * 365,  # 20 years for detailed tracking
        people_goal=5000,
        cargo_goal=110000
    )
    
    print(f"Parameters:")
    print(f"  Production: {diag_params.crew_line_capacity} crew lines, {diag_params.tanker_line_capacity} tanker lines")
    print(f"  Build times: {diag_params.crew_build_time_months}mo crew, {diag_params.tanker_build_time_months}mo tanker")
    print(f"  Ship capacity: {diag_params.n_people_per_ship} people/ship")
    print(f"  Mission fuel: {diag_params.fuel_per_mars_mission} tons")
    print()
    
    state = simulate(diag_params)
    
    # Analyze launch windows specifically
    launch_windows = []
    for day in range(0, diag_params.total_simulation_days, diag_params.launch_window_interval_days):
        if day == 0:
            continue  # Skip day 0
            
        # Find the corresponding history record
        window_record = None
        for rec in state.history:
            if rec["day"] == day:
                window_record = rec
                break
        
        if window_record:
            launch_windows.append({
                "window": len(launch_windows) + 1,
                "day": day,
                "year": day / 365,
                "crew_ships": window_record["crew"],
                "fuel_depot": window_record["fuel_depot"],
                "people_at_mars": window_record["people"],
                "mars_fuel_demand": window_record.get("mars_fuel_demand", 0)
            })
    
    print("📊 Launch Window Analysis:")
    print("Window | Year | Crew Ships | Fuel Depot | People@Mars | People Δ")
    print("-------|------|------------|------------|-------------|----------")
    
    prev_people = 0
    for i, window in enumerate(launch_windows[:15]):  # First 15 windows
        people_delta = window["people_at_mars"] - prev_people
        print(f"{window['window']:6} | {window['year']:4.1f} | {window['crew_ships']:10} | {window['fuel_depot']:10.0f} | {window['people_at_mars']:11} | {people_delta:8}")
        prev_people = window["people_at_mars"]
    
    # Calculate theoretical vs actual
    print(f"\n🧮 Theoretical Analysis:")
    
    # How many crew ships should we have after 10 years?
    years_10 = 10
    months_10 = years_10 * 12
    ships_per_month = diag_params.crew_line_capacity / diag_params.crew_build_time_months
    theoretical_ships_10yr = ships_per_month * months_10
    
    print(f"  Production rate: {ships_per_month:.1f} crew ships/month")
    print(f"  Theoretical ships after 10 years: {theoretical_ships_10yr:.0f}")
    
    # What about fuel production?
    tankers_per_month = diag_params.tanker_line_capacity / diag_params.tanker_build_time_months
    fuel_per_month = tankers_per_month * diag_params.fuel_per_tanker * 30 / diag_params.tanker_turnaround_days
    
    print(f"  Tanker production: {tankers_per_month:.1f} tankers/month")
    print(f"  Fuel production: {fuel_per_month:.0f} tons/month")
    
    # How many ships can we fuel per launch window?
    fuel_per_window = fuel_per_month * (diag_params.launch_window_interval_days / 30)
    ships_per_window_fuel_limit = fuel_per_window / diag_params.fuel_per_mars_mission
    
    print(f"  Fuel per launch window: {fuel_per_window:.0f} tons")
    print(f"  Ships we can fuel per window: {ships_per_window_fuel_limit:.1f}")
    
    return state

# ---------------------------------------------------------------------------
# 8. Quick demonstration
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--optimize":
        # Run optimization
        optimal_params, result = optimize_for_dual_goals()
    elif len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Run scaling test
        test_extreme_scaling()
    elif len(sys.argv) > 1 and sys.argv[1] == "--debug":
        # Run debug simulation
        debug_ship_lifecycle()
    elif len(sys.argv) > 1 and sys.argv[1] == "--diagnose":
        # Run launch sequence diagnosis
        diagnose_launch_sequence()
    else:
        # Run default simulation
        default_params = SimParams()
        final_state = simulate(default_params)
        years = final_state.day / 365.0
        last_record = final_state.history[-1]
        print(f"Simulated {years:.1f} years → {last_record['people']} people, {last_record['cargo']:.0f} t cargo on Mars, depot fuel {last_record['fuel_depot']:.0f} t")
        print(f"\nTo optimize for 5000 people + 110,000 tons cargo, run: python mars_transport_sim.py --optimize")
        print(f"To test extreme scaling, run: python mars_transport_sim.py --test")
        print(f"To debug ship lifecycle, run: python mars_transport_sim.py --debug")
        print(f"To diagnose launch sequence, run: python mars_transport_sim.py --diagnose")

    # TODO: plug into scipy / optuna optimiser of choice
