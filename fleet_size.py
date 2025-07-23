import pandas as pd
from dash import Dash, dcc, html, Input, Output, dash_table
import plotly.graph_objs as go

# Constants
launch_window_interval_days = 780  # 26 months between Mars windows
total_simulation_days = 25 * 365  # simulate 25 years
transit_time_days = 250  # 6-9 months travel time (each way)
mars_wait_time_days = 540  # ~18 months wait on Mars
mission_duration_days = transit_time_days * 2 + mars_wait_time_days  # total round trip

# Simulation logic
def simulate_mars_transport(params):
    # Result tracking
    time = []
    people_at_mars = []
    cargo_at_mars = []
    crew_ships_available = []
    cargo_ships_available = []
    tankers_available = []
    leo_fuel_depot = []
    fuel_needed_for_fleet = []
    mars_fuel_demand = []
    
    # Data for three separate tables
    production_data = []  # Quarterly production/fuel/fleet data
    operations_data = []  # Launch window operations data
    mars_data = []        # Quarterly Mars deliveries and status
    
    # Quarterly tracking variables
    quarter_start_day = 0
    quarter_crew_completed = 0
    quarter_cargo_completed = 0
    quarter_tanker_completed = 0
    quarter_fuel_delivered = 0
    quarter_people_delivered = 0
    quarter_cargo_delivered = 0
    
    # State tracking
    people_cumulative = 0
    cargo_cumulative = 0
    depot_fuel = 0
    mars_fuel_cumulative = 0
    
    # Ship lifecycle tracking with mission counts
    crew_ships_fleet = []  # list of {'id': ship_id, 'missions': count}
    cargo_ships_fleet = []  # list of {'id': ship_id, 'missions': count}
    tankers_fleet = []  # list of {'id': ship_id, 'missions': count, 'last_flight_day': day}
    crew_ships_returning = []  # list of (return_day, ship_list)
    cargo_ships_returning = []  # list of (return_day, ship_list)
    ships_arriving_mars = []  # list of (arrival_day, crew_count, cargo_count)
    next_ship_id = 0
    
    # Manufacturing tracking
    ships_under_construction = []  # list of {'type': 'crew'/'cargo'/'tanker', 'id': ship_id, 'completion_day': day}
    
    for day in range(0, total_simulation_days + 1):
        # Continuous manufacturing system
        
        # Check for ship completions
        completed_ships = [ship for ship in ships_under_construction if ship['completion_day'] == day]
        ships_under_construction = [ship for ship in ships_under_construction if ship['completion_day'] != day]
        
        # Add completed ships to active fleets and track quarterly completions
        for ship in completed_ships:
            if ship['type'] == 'crew':
                crew_ships_fleet.append({'id': ship['id'], 'missions': 0})
                quarter_crew_completed += 1
            elif ship['type'] == 'cargo':
                cargo_ships_fleet.append({'id': ship['id'], 'missions': 0})
                quarter_cargo_completed += 1
            elif ship['type'] == 'tanker':
                tankers_fleet.append({'id': ship['id'], 'missions': 0, 'last_flight_day': -999})
                quarter_tanker_completed += 1
        
        # Start new ship construction (whenever production line has capacity)
        crew_under_construction = len([s for s in ships_under_construction if s['type'] == 'crew'])
        cargo_under_construction = len([s for s in ships_under_construction if s['type'] == 'cargo'])
        tanker_under_construction = len([s for s in ships_under_construction if s['type'] == 'tanker'])
        
        # Start crew ship if line has capacity
        if crew_under_construction < params["crew_line_capacity"]:
            completion_day = day + (params["crew_build_time_months"] * 30)  # Convert months to days
            ships_under_construction.append({
                'type': 'crew',
                'id': next_ship_id,
                'completion_day': completion_day
            })
            next_ship_id += 1
        
        # Start cargo ship if line has capacity
        if cargo_under_construction < params["cargo_line_capacity"]:
            completion_day = day + (params["cargo_build_time_months"] * 30)  # Convert months to days
            ships_under_construction.append({
                'type': 'cargo',
                'id': next_ship_id,
                'completion_day': completion_day
            })
            next_ship_id += 1
        
        # Start tanker if line has capacity
        if tanker_under_construction < params["tanker_line_capacity"]:
            completion_day = day + (params["tanker_build_time_months"] * 30)  # Convert months to days
            ships_under_construction.append({
                'type': 'tanker',
                'id': next_ship_id,
                'completion_day': completion_day
            })
            next_ship_id += 1
        
        # Remove ships that exceed their mission lifespan (except tankers - handled after flights)
        crew_ships_fleet = [ship for ship in crew_ships_fleet if ship['missions'] < params["crew_ship_lifespan"]]
        cargo_ships_fleet = [ship for ship in cargo_ships_fleet if ship['missions'] < params["cargo_ship_lifespan"]]
        
        # Daily tanker operations - fly all ready tankers
        if len(tankers_fleet) > 0:
            # Find tankers ready to fly (turnaround time has passed)
            ready_tankers = []
            for tanker in tankers_fleet:
                days_since_last_flight = day - tanker['last_flight_day']
                if days_since_last_flight >= params["tanker_turnaround_days"]:
                    ready_tankers.append(tanker)
            
            # Fly all ready tankers
            active_tankers = len(ready_tankers)
            daily_fuel_delivery = active_tankers * params["fuel_per_tanker"]
            depot_fuel += daily_fuel_delivery
            quarter_fuel_delivered += daily_fuel_delivery
            
            # Update flight records for tankers that flew
            for tanker in ready_tankers:
                tanker['missions'] += 1
                tanker['last_flight_day'] = day
            
        # Remove tankers that exceed their mission lifespan (after completing flights)
        tankers_fleet = [ship for ship in tankers_fleet if ship['missions'] < params["tanker_lifespan"]]
            
        # Ships returning from Mars
        returning_crew_missions = [item for item in crew_ships_returning if item[0] == day]
        returning_cargo_missions = [item for item in cargo_ships_returning if item[0] == day]
        
        for return_day, ship_list in returning_crew_missions:
            # Add back ships that haven't exceeded lifespan (missions already counted at launch)
            for ship in ship_list:
                if ship['missions'] < params["crew_ship_lifespan"]:
                    crew_ships_fleet.append(ship)
            
        for return_day, ship_list in returning_cargo_missions:
            # Add back ships that haven't exceeded lifespan (missions already counted at launch)
            for ship in ship_list:
                if ship['missions'] < params["cargo_ship_lifespan"]:
                    cargo_ships_fleet.append(ship)
            
        # Remove returned ships from tracking
        crew_ships_returning = [item for item in crew_ships_returning if item[0] != day]
        cargo_ships_returning = [item for item in cargo_ships_returning if item[0] != day]
        
        # Calculate Mars fuel demand from ships arriving today
        daily_mars_fuel_demand = 0
        arriving_ships_today = [item for item in ships_arriving_mars if item[0] == day]
        for arrival_day, crew_count, cargo_count in arriving_ships_today:
            # Each ship needs fuel for return journey (Mars -> Earth)
            total_ships = crew_count + cargo_count
            daily_mars_fuel_demand += total_ships * params["fuel_per_mars_mission"]
        
        # Remove processed arrivals
        ships_arriving_mars = [item for item in ships_arriving_mars if item[0] != day]

        # Mars launch windows
        if day % launch_window_interval_days == 0 and day > 0:
            # Calculate fuel needed per ship for Mars mission
            fuel_per_crew_ship = params["fuel_per_mars_mission"]
            fuel_per_cargo_ship = params["fuel_per_mars_mission"]
            
            # Calculate balanced launch strategy
            total_ships_wanted = len(crew_ships_fleet) + len(cargo_ships_fleet)
            total_ships_can_fuel = depot_fuel // fuel_per_crew_ship  # Same fuel per ship
            
            if total_ships_can_fuel >= total_ships_wanted:
                # Can fuel everything - launch all available ships
                max_crew_ships = len(crew_ships_fleet)
                max_cargo_ships = len(cargo_ships_fleet)
            else:
                # Limited fuel - launch balanced mix
                crew_fraction = len(crew_ships_fleet) / total_ships_wanted if total_ships_wanted > 0 else 0
                cargo_fraction = len(cargo_ships_fleet) / total_ships_wanted if total_ships_wanted > 0 else 0
                
                max_crew_ships = min(len(crew_ships_fleet), int(total_ships_can_fuel * crew_fraction))
                max_cargo_ships = min(len(cargo_ships_fleet), int(total_ships_can_fuel * cargo_fraction))
                
                # Use any remaining fuel capacity for either type
                remaining_capacity = total_ships_can_fuel - max_crew_ships - max_cargo_ships
                if remaining_capacity > 0:
                    if len(crew_ships_fleet) > max_crew_ships:
                        additional_crew = min(remaining_capacity, len(crew_ships_fleet) - max_crew_ships)
                        max_crew_ships += additional_crew
                        remaining_capacity -= additional_crew
                    if remaining_capacity > 0 and len(cargo_ships_fleet) > max_cargo_ships:
                        additional_cargo = min(remaining_capacity, len(cargo_ships_fleet) - max_cargo_ships)
                        max_cargo_ships += additional_cargo
            
            # Calculate metrics before launching (using available ships)
            crew_ships_available_window = len(crew_ships_fleet)
            cargo_ships_available_window = len(cargo_ships_fleet)
            crew_util_pct = (max_crew_ships / crew_ships_available_window * 100) if crew_ships_available_window > 0 else 0
            cargo_util_pct = (max_cargo_ships / cargo_ships_available_window * 100) if cargo_ships_available_window > 0 else 0
            
            # Calculate fuel needed for all available ships
            total_fleet_fuel_needed = (crew_ships_available_window + cargo_ships_available_window) * params["fuel_per_mars_mission"]
            
            # Determine limiting factor
            total_ships_available = crew_ships_available_window + cargo_ships_available_window
            ships_we_could_fuel = depot_fuel // fuel_per_crew_ship if fuel_per_crew_ship > 0 else 0
            limiting_factor = "Fuel" if ships_we_could_fuel < total_ships_available else "Ships"
            
            # Ships returning this window
            crew_ships_returning_today = sum([len(ship_list) for return_day, ship_list in crew_ships_returning if return_day == day])
            cargo_ships_returning_today = sum([len(ship_list) for return_day, ship_list in cargo_ships_returning if return_day == day])
            ships_returning_today = crew_ships_returning_today + cargo_ships_returning_today
            
            # Total fleet size (including ships in transit)
            ships_in_transit = sum([len(ship_list) for return_day, ship_list in crew_ships_returning]) + \
                              sum([len(ship_list) for return_day, ship_list in cargo_ships_returning])
            total_fleet_size = crew_ships_available_window + cargo_ships_available_window + len(tankers_fleet) + ships_in_transit

            if max_crew_ships > 0 or max_cargo_ships > 0:
                # Ships launched this window
                fuel_used = (max_crew_ships * fuel_per_crew_ship) + (max_cargo_ships * fuel_per_cargo_ship)
                depot_fuel -= fuel_used
                
                # Remove ships from available fleet and track them for return
                launched_crew_ships = crew_ships_fleet[:max_crew_ships]
                launched_cargo_ships = cargo_ships_fleet[:max_cargo_ships]
                crew_ships_fleet = crew_ships_fleet[max_crew_ships:]
                cargo_ships_fleet = cargo_ships_fleet[max_cargo_ships:]
                
                # Increment mission count for launched ships
                for ship in launched_crew_ships:
                    ship['missions'] += 1
                for ship in launched_cargo_ships:
                    ship['missions'] += 1
                
                # Add people and cargo to Mars
                people_delivered_this_window = max_crew_ships * params["n_people_per_ship"]
                cargo_delivered_this_window = max_cargo_ships * params["cargo_mass_per_ship"]
                people_cumulative += people_delivered_this_window
                cargo_cumulative += cargo_delivered_this_window
                quarter_people_delivered += people_delivered_this_window
                quarter_cargo_delivered += cargo_delivered_this_window
                
                # Schedule ship returns (after full round trip)
                return_day = day + mission_duration_days
                if max_crew_ships > 0:
                    crew_ships_returning.append((return_day, launched_crew_ships))
                if max_cargo_ships > 0:
                    cargo_ships_returning.append((return_day, launched_cargo_ships))
                
                # Schedule Mars arrival for fuel demand tracking
                mars_arrival_day = day + transit_time_days
                if max_crew_ships > 0 or max_cargo_ships > 0:
                    ships_arriving_mars.append((mars_arrival_day, max_crew_ships, max_cargo_ships))
            else:
                fuel_used = 0

            # Calculate fuel surplus/deficit (after any fuel use)
            fuel_surplus = depot_fuel - total_fleet_fuel_needed

            # Log operations data for launch windows
            if day <= 780 * 10:  # First 10 launch windows (~26 years)
                operations_data.append({
                    "Window": len(operations_data) + 1,
                    "Year": f"{day/365:.1f}",
                    "Crew Avail": crew_ships_available_window,
                    "Cargo Avail": cargo_ships_available_window,
                    "Crew Launch": max_crew_ships,
                    "Cargo Launch": max_cargo_ships,
                    "Crew Util %": f"{crew_util_pct:.0f}%",
                    "Cargo Util %": f"{cargo_util_pct:.0f}%",
                    "Limiting Factor": limiting_factor,
                    "Fuel Used": f"{fuel_used:.0f}",
                    "Ships Returning": ships_returning_today
                })

        # Calculate fuel needed to launch all available ships
        total_fleet_fuel_needed = (len(crew_ships_fleet) + len(cargo_ships_fleet)) * params["fuel_per_mars_mission"]
        
        # Update cumulative Mars fuel demand
        mars_fuel_cumulative += daily_mars_fuel_demand
        
        # Record daily state
        time.append(day / 365)
        people_at_mars.append(people_cumulative)
        cargo_at_mars.append(cargo_cumulative)
        crew_ships_available.append(len(crew_ships_fleet))
        cargo_ships_available.append(len(cargo_ships_fleet))
        tankers_available.append(len(tankers_fleet))
        leo_fuel_depot.append(depot_fuel)
        fuel_needed_for_fleet.append(total_fleet_fuel_needed)
        mars_fuel_demand.append(mars_fuel_cumulative)
        
        # Quarterly reporting (every ~91 days)
        if day > 0 and day % 91 == 0 and day <= total_simulation_days:
            quarter_num = day // 91
            year = day / 365
            
            # Production data
            crew_under_construction = len([s for s in ships_under_construction if s['type'] == 'crew'])
            cargo_under_construction = len([s for s in ships_under_construction if s['type'] == 'cargo'])
            tanker_under_construction = len([s for s in ships_under_construction if s['type'] == 'tanker'])
            
            production_data.append({
                "Quarter": f"Q{((quarter_num-1) % 4) + 1}",
                "Year": f"{year:.1f}",
                "Crew Built": quarter_crew_completed,
                "Cargo Built": quarter_cargo_completed,
                "Tanker Built": quarter_tanker_completed,
                "Fuel Delivered": f"{quarter_fuel_delivered:.0f}",
                "Crew Fleet": len(crew_ships_fleet),
                "Cargo Fleet": len(cargo_ships_fleet),
                "Tanker Fleet": len(tankers_fleet),
                "Building": crew_under_construction + cargo_under_construction + tanker_under_construction,
                "Depot Fuel": f"{depot_fuel:.0f}"
            })
            
            # Mars data
            # Calculate ships idle on Mars (simplified estimate)
            ships_in_transit = sum([len(ship_list) for return_day, ship_list in crew_ships_returning]) + \
                              sum([len(ship_list) for return_day, ship_list in cargo_ships_returning])
            # Rough estimate of ships on Mars surface waiting for return window
            estimated_ships_on_mars = max(0, (people_cumulative // params["n_people_per_ship"]) + 
                                           (cargo_cumulative // params["cargo_mass_per_ship"]) - ships_in_transit)
            
            mars_data.append({
                "Quarter": f"Q{((quarter_num-1) % 4) + 1}",
                "Year": f"{year:.1f}",
                "People Delivered": quarter_people_delivered,
                "Cargo Delivered": f"{quarter_cargo_delivered:.0f}",
                "Ships on Mars": f"{estimated_ships_on_mars:.0f}",
                "Total People": f"{people_cumulative:.0f}",
                "Total Cargo": f"{cargo_cumulative:.0f}",
                "Cumulative Fuel Demand": f"{mars_fuel_cumulative:.0f}"
            })
            
            # Reset quarterly counters
            quarter_crew_completed = 0
            quarter_cargo_completed = 0
            quarter_tanker_completed = 0
            quarter_fuel_delivered = 0
            quarter_people_delivered = 0
            quarter_cargo_delivered = 0

    df = pd.DataFrame({
        "Year": time,
        "People at Mars": people_at_mars,
        "Cargo at Mars (tons)": cargo_at_mars,
        "Crew Ships Available": crew_ships_available,
        "Cargo Ships Available": cargo_ships_available,
        "Tankers Available": tankers_available,
        "LEO Fuel Depot": leo_fuel_depot,
        "Fuel Needed for Fleet": fuel_needed_for_fleet,
        "Mars Fuel Demand": mars_fuel_demand
    })
    
    return df, production_data, operations_data, mars_data

# Dash App
app = Dash(__name__)
app.title = "Mars Transport Simulator"

app.layout = html.Div([
    # Header
    html.Div([
        html.H1("Mars Settlement Transport Simulator", 
                style={
                    "textAlign": "center", 
                    "color": "#2c3e50", 
                    "marginBottom": "30px",
                    "fontFamily": "system-ui, -apple-system, sans-serif",
                    "fontWeight": "300",
                    "fontSize": "2.5rem"
                })
    ], style={
        "backgroundColor": "#ffffff",
        "padding": "20px 0",
        "borderBottom": "1px solid #e9ecef",
        "marginBottom": "0"
    }),
    
    # Main content
    html.Div([
        # Controls Panel
        html.Div([
            html.H3("Mission Parameters", 
                   style={
                       "color": "#34495e", 
                       "marginBottom": "25px",
                       "fontFamily": "system-ui, -apple-system, sans-serif",
                       "fontWeight": "400",
                       "fontSize": "1.3rem"
                   }),
            
            # Ship Capacity Section
            html.Div([
                html.H4("Ship Capacity", style={"color": "#7f8c8d", "fontSize": "1rem", "marginBottom": "15px"}),
                
                html.Div([
                    html.Label("People per Ship", style={"fontWeight": "500", "color": "#2c3e50"}),
                    html.P("Crew capacity for each crew-class Starship", 
                           style={"fontSize": "12px", "color": "#95a5a6", "margin": "5px 0 10px 0"}),
                    dcc.Slider(10, 200, 10, value=100, id="n_people_per_ship",
                              marks={i: str(i) for i in range(10, 201, 50)},
                              tooltip={"placement": "bottom", "always_visible": False})
                ], style={"marginBottom": "20px"}),
                
                html.Div([
                    html.Label("Cargo Mass per Ship (tons)", style={"fontWeight": "500", "color": "#2c3e50"}),
                    html.P("Cargo capacity for each cargo-class Starship", 
                           style={"fontSize": "12px", "color": "#95a5a6", "margin": "5px 0 10px 0"}),
                    dcc.Slider(10, 200, 10, value=100, id="cargo_mass_per_ship",
                              marks={i: str(i) for i in range(10, 201, 50)},
                              tooltip={"placement": "bottom", "always_visible": False})
                ], style={"marginBottom": "25px"}),
            ]),
            
            # Manufacturing Section
            html.Div([
                html.H4("Manufacturing", style={"color": "#7f8c8d", "fontSize": "1rem", "marginBottom": "15px"}),
                
                html.Div([
                    html.Label("Crew Ship Build Time (months)", style={"fontWeight": "500", "color": "#2c3e50"}),
                    html.P("Time to build each crew ship from start to finish", 
                           style={"fontSize": "12px", "color": "#95a5a6", "margin": "5px 0 10px 0"}),
                    dcc.Slider(1, 12, 1, value=6, id="crew_build_time_months",
                              marks={i: str(i) for i in range(1, 13, 3)},
                              tooltip={"placement": "bottom", "always_visible": False})
                ], style={"marginBottom": "20px"}),
                
                html.Div([
                    html.Label("Cargo Ship Build Time (months)", style={"fontWeight": "500", "color": "#2c3e50"}),
                    html.P("Time to build each cargo ship from start to finish", 
                           style={"fontSize": "12px", "color": "#95a5a6", "margin": "5px 0 10px 0"}),
                    dcc.Slider(1, 12, 1, value=4, id="cargo_build_time_months",
                              marks={i: str(i) for i in range(1, 13, 3)},
                              tooltip={"placement": "bottom", "always_visible": False})
                ], style={"marginBottom": "20px"}),
                
                html.Div([
                    html.Label("Tanker Build Time (months)", style={"fontWeight": "500", "color": "#2c3e50"}),
                    html.P("Time to build each tanker ship from start to finish", 
                           style={"fontSize": "12px", "color": "#95a5a6", "margin": "5px 0 10px 0"}),
                    dcc.Slider(1, 12, 1, value=3, id="tanker_build_time_months",
                              marks={i: str(i) for i in range(1, 13, 3)},
                              tooltip={"placement": "bottom", "always_visible": False})
                ], style={"marginBottom": "20px"}),
                
                html.Div([
                    html.Label("Crew Line Capacity", style={"fontWeight": "500", "color": "#2c3e50"}),
                    html.P("Max crew ships building simultaneously. Production rate emerges from capacity × build time.", 
                           style={"fontSize": "12px", "color": "#95a5a6", "margin": "5px 0 10px 0"}),
                    dcc.Slider(1, 30, 1, value=8, id="crew_line_capacity",
                              marks={i: str(i) for i in range(1, 31, 10)},
                              tooltip={"placement": "bottom", "always_visible": False})
                ], style={"marginBottom": "20px"}),
                
                html.Div([
                    html.Label("Cargo Line Capacity", style={"fontWeight": "500", "color": "#2c3e50"}),
                    html.P("Max cargo ships building simultaneously", 
                           style={"fontSize": "12px", "color": "#95a5a6", "margin": "5px 0 10px 0"}),
                    dcc.Slider(1, 50, 1, value=15, id="cargo_line_capacity",
                              marks={i: str(i) for i in range(1, 51, 15)},
                              tooltip={"placement": "bottom", "always_visible": False})
                ], style={"marginBottom": "20px"}),
                
                html.Div([
                    html.Label("Tanker Line Capacity", style={"fontWeight": "500", "color": "#2c3e50"}),
                    html.P("Max tanker ships building simultaneously", 
                           style={"fontSize": "12px", "color": "#95a5a6", "margin": "5px 0 10px 0"}),
                    dcc.Slider(1, 50, 1, value=20, id="tanker_line_capacity",
                              marks={i: str(i) for i in range(1, 51, 15)},
                              tooltip={"placement": "bottom", "always_visible": False})
                ], style={"marginBottom": "25px"}),
            ]),
            
            # Operations Section
            html.Div([
                html.H4("Operations", style={"color": "#7f8c8d", "fontSize": "1rem", "marginBottom": "15px"}),
                
                html.Div([
                    html.Label("Tanker Turnaround (days)", style={"fontWeight": "500", "color": "#2c3e50"}),
                    html.P("Days between flights for each tanker", 
                           style={"fontSize": "12px", "color": "#95a5a6", "margin": "5px 0 10px 0"}),
                    dcc.Slider(1, 30, 1, value=7, id="tanker_turnaround_days",
                              marks={i: str(i) for i in range(1, 31, 7)},
                              tooltip={"placement": "bottom", "always_visible": False})
                ], style={"marginBottom": "20px"}),
                
                html.Div([
                    html.Label("Fuel per Tanker (tons)", style={"fontWeight": "500", "color": "#2c3e50"}),
                    html.P("Fuel load carried by each tanker to LEO depot", 
                           style={"fontSize": "12px", "color": "#95a5a6", "margin": "5px 0 10px 0"}),
                    dcc.Slider(10, 200, 10, value=100, id="fuel_per_tanker",
                              marks={i: str(i) for i in range(10, 201, 50)},
                              tooltip={"placement": "bottom", "always_visible": False})
                ], style={"marginBottom": "20px"}),
                
                html.Div([
                    html.Label("Fuel per Mars Mission (tons)", style={"fontWeight": "500", "color": "#2c3e50"}),
                    html.P("Fuel needed for complete round trip", 
                           style={"fontSize": "12px", "color": "#95a5a6", "margin": "5px 0 10px 0"}),
                    dcc.Slider(100, 2000, 100, value=1600, id="fuel_per_mars_mission",
                              marks={i: str(i) for i in range(100, 2001, 500)},
                              tooltip={"placement": "bottom", "always_visible": False})
                ], style={"marginBottom": "25px"}),
            ]),
            
            # Lifespan Section
            html.Div([
                html.H4("Ship Lifespan", style={"color": "#7f8c8d", "fontSize": "1rem", "marginBottom": "15px"}),
                
                html.Div([
                    html.Label("Crew Ship Lifespan (missions)", style={"fontWeight": "500", "color": "#2c3e50"}),
                    html.P("Mars round trips before retirement", 
                           style={"fontSize": "12px", "color": "#95a5a6", "margin": "5px 0 10px 0"}),
                    dcc.Slider(1, 20, 1, value=10, id="crew_ship_lifespan",
                              marks={i: str(i) for i in range(1, 21, 5)},
                              tooltip={"placement": "bottom", "always_visible": False})
                ], style={"marginBottom": "20px"}),
                
                html.Div([
                    html.Label("Cargo Ship Lifespan (missions)", style={"fontWeight": "500", "color": "#2c3e50"}),
                    html.P("Mars round trips before retirement", 
                           style={"fontSize": "12px", "color": "#95a5a6", "margin": "5px 0 10px 0"}),
                    dcc.Slider(1, 20, 1, value=10, id="cargo_ship_lifespan",
                              marks={i: str(i) for i in range(1, 21, 5)},
                              tooltip={"placement": "bottom", "always_visible": False})
                ], style={"marginBottom": "20px"}),
                
                html.Div([
                    html.Label("Tanker Lifespan (missions)", style={"fontWeight": "500", "color": "#2c3e50"}),
                    html.P("LEO fuel runs before retirement", 
                           style={"fontSize": "12px", "color": "#95a5a6", "margin": "5px 0 10px 0"}),
                    dcc.Slider(2, 50, 2, value=20, id="tanker_lifespan",
                              marks={i: str(i) for i in range(2, 51, 12)},
                              tooltip={"placement": "bottom", "always_visible": False})
                ], style={"marginBottom": "20px"}),
            ])
            
        ], style={
            "flex": "0 0 300px",  # Fixed width for params
            "padding": "25px",
            "backgroundColor": "#f8f9fa",
            "borderRadius": "8px",
            "margin": "10px",
            "boxShadow": "0 2px 4px rgba(0,0,0,0.1)",
            "fontFamily": "system-ui, -apple-system, sans-serif"
        }),

        # Right Column: Charts + Table
        html.Div([
            # Charts Panel
            html.Div([
                dcc.Graph(id="people_graph", style={"marginBottom": "15px"}),
                dcc.Graph(id="cargo_graph", style={"marginBottom": "15px"}),
                dcc.Graph(id="fleet_graph", style={"marginBottom": "15px"}),
                dcc.Graph(id="fuel_depot_graph", style={"marginBottom": "15px"}),
                dcc.Graph(id="mars_fuel_graph")
            ], style={
                "padding": "25px",
                "backgroundColor": "#ffffff",
                "borderRadius": "8px",
                "margin": "10px 10px 20px 10px",
                "boxShadow": "0 2px 4px rgba(0,0,0,0.1)",
                "height": "600px",
                "overflowY": "auto"
            }),
            
            # Three Data Tables Panel
            html.Div([
                # Production Table
                html.Div([
                    html.H3("Production & Fleet Status (Quarterly)", 
                           style={
                               "color": "#34495e", 
                               "marginBottom": "15px",
                               "fontFamily": "system-ui, -apple-system, sans-serif",
                               "fontWeight": "400",
                               "fontSize": "1.1rem"
                           }),
                    dash_table.DataTable(
                        id="production_table",
                        columns=[
                            {"name": "Quarter", "id": "Quarter", "type": "text"},
                            {"name": "Year", "id": "Year", "type": "text"},
                            {"name": "Crew Built", "id": "Crew Built", "type": "numeric"},
                            {"name": "Cargo Built", "id": "Cargo Built", "type": "numeric"},
                            {"name": "Tanker Built", "id": "Tanker Built", "type": "numeric"},
                            {"name": "Fuel Delivered", "id": "Fuel Delivered", "type": "text"},
                            {"name": "Crew Fleet", "id": "Crew Fleet", "type": "numeric"},
                            {"name": "Cargo Fleet", "id": "Cargo Fleet", "type": "numeric"},
                            {"name": "Tanker Fleet", "id": "Tanker Fleet", "type": "numeric"},
                            {"name": "Building", "id": "Building", "type": "numeric"},
                            {"name": "Depot Fuel", "id": "Depot Fuel", "type": "text"}
                        ],
                        data=[],
                        style_table={"height": "300px", "overflowY": "auto", "borderRadius": "6px"},
                        style_cell={"textAlign": "center", "fontSize": "10px", "padding": "4px"},
                        style_header={"backgroundColor": "#3498db", "color": "white", "fontWeight": "600"},
                        style_data_conditional=[
                            {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"},
                            {"if": {"row_index": "even"}, "backgroundColor": "#ffffff"}
                        ]
                    )
                ], style={"marginBottom": "20px"}),
                
                # Operations Table
                html.Div([
                    html.H3("Launch Operations (Launch Windows)", 
                           style={
                               "color": "#34495e", 
                               "marginBottom": "15px",
                               "fontFamily": "system-ui, -apple-system, sans-serif",
                               "fontWeight": "400",
                               "fontSize": "1.1rem"
                           }),
                    dash_table.DataTable(
                        id="operations_table",
                        columns=[
                            {"name": "Window", "id": "Window", "type": "numeric"},
                            {"name": "Year", "id": "Year", "type": "text"},
                            {"name": "Crew Avail", "id": "Crew Avail", "type": "numeric"},
                            {"name": "Cargo Avail", "id": "Cargo Avail", "type": "numeric"},
                            {"name": "Crew Launch", "id": "Crew Launch", "type": "numeric"},
                            {"name": "Cargo Launch", "id": "Cargo Launch", "type": "numeric"},
                            {"name": "Crew Util %", "id": "Crew Util %", "type": "text"},
                            {"name": "Cargo Util %", "id": "Cargo Util %", "type": "text"},
                            {"name": "Limiting Factor", "id": "Limiting Factor", "type": "text"},
                            {"name": "Fuel Used", "id": "Fuel Used", "type": "text"},
                            {"name": "Ships Returning", "id": "Ships Returning", "type": "numeric"}
                        ],
                        data=[],
                        style_table={"height": "300px", "overflowY": "auto", "borderRadius": "6px"},
                        style_cell={"textAlign": "center", "fontSize": "10px", "padding": "4px"},
                        style_header={"backgroundColor": "#e74c3c", "color": "white", "fontWeight": "600"},
                        style_data_conditional=[
                            {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"},
                            {"if": {"row_index": "even"}, "backgroundColor": "#ffffff"}
                        ]
                    )
                ], style={"marginBottom": "20px"}),
                
                # Mars Table
                html.Div([
                    html.H3("Mars Settlement Status (Quarterly)", 
                           style={
                               "color": "#34495e", 
                               "marginBottom": "15px",
                               "fontFamily": "system-ui, -apple-system, sans-serif",
                               "fontWeight": "400",
                               "fontSize": "1.1rem"
                           }),
                    dash_table.DataTable(
                        id="mars_table",
                        columns=[
                            {"name": "Quarter", "id": "Quarter", "type": "text"},
                            {"name": "Year", "id": "Year", "type": "text"},
                            {"name": "People Delivered", "id": "People Delivered", "type": "numeric"},
                            {"name": "Cargo Delivered", "id": "Cargo Delivered", "type": "text"},
                            {"name": "Ships on Mars", "id": "Ships on Mars", "type": "text"},
                            {"name": "Total People", "id": "Total People", "type": "text"},
                            {"name": "Total Cargo", "id": "Total Cargo", "type": "text"},
                            {"name": "Cumulative Fuel Demand", "id": "Cumulative Fuel Demand", "type": "text"}
                        ],
                        data=[],
                        style_table={"height": "300px", "overflowY": "auto", "borderRadius": "6px"},
                        style_cell={"textAlign": "center", "fontSize": "10px", "padding": "4px"},
                        style_header={"backgroundColor": "#f39c12", "color": "white", "fontWeight": "600"},
                        style_data_conditional=[
                            {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"},
                            {"if": {"row_index": "even"}, "backgroundColor": "#ffffff"}
                        ]
                    )
                ])
            ], style={
                "padding": "25px",
                "backgroundColor": "#ffffff",
                "borderRadius": "8px",
                "margin": "10px",
                "boxShadow": "0 2px 4px rgba(0,0,0,0.1)"
            })
        ], style={
            "flex": "1"  # Right column takes remaining space
        })
    ], style={
        "padding": "0 20px 20px 20px",
        "backgroundColor": "#f1f3f4",
        "fontFamily": "system-ui, -apple-system, sans-serif",
        "display": "flex",
        "gap": "10px"
    })
], style={
    "backgroundColor": "#f1f3f4",
    "minHeight": "100vh",
    "margin": "0",
    "fontFamily": "system-ui, -apple-system, sans-serif"
})

@app.callback(
    [Output("people_graph", "figure"), Output("cargo_graph", "figure"), Output("fleet_graph", "figure"), Output("fuel_depot_graph", "figure"), Output("mars_fuel_graph", "figure"), Output("production_table", "data"), Output("operations_table", "data"), Output("mars_table", "data")],
    Input("n_people_per_ship", "value"),
    Input("cargo_mass_per_ship", "value"),
    Input("crew_build_time_months", "value"),
    Input("cargo_build_time_months", "value"),
    Input("tanker_build_time_months", "value"),
    Input("crew_line_capacity", "value"),
    Input("cargo_line_capacity", "value"),
    Input("tanker_line_capacity", "value"),
    Input("tanker_turnaround_days", "value"),
    Input("fuel_per_tanker", "value"),
    Input("fuel_per_mars_mission", "value"),
    Input("crew_ship_lifespan", "value"),
    Input("cargo_ship_lifespan", "value"),
    Input("tanker_lifespan", "value"),
)
def update_graphs(n_people, cargo_mass, crew_build_months, cargo_build_months, tanker_build_months, crew_capacity, cargo_capacity, tanker_capacity, tanker_turnaround_days, fuel_per_tanker, fuel_per_mission, crew_lifespan, cargo_lifespan, tanker_lifespan):
    params = {
        "n_people_per_ship": n_people,
        "cargo_mass_per_ship": cargo_mass,
        "crew_build_time_months": crew_build_months,
        "cargo_build_time_months": cargo_build_months,
        "tanker_build_time_months": tanker_build_months,
        "crew_line_capacity": crew_capacity,
        "cargo_line_capacity": cargo_capacity,
        "tanker_line_capacity": tanker_capacity,
        "tanker_turnaround_days": tanker_turnaround_days,
        "fuel_per_tanker": fuel_per_tanker,
        "fuel_per_mars_mission": fuel_per_mission,
        "crew_ship_lifespan": crew_lifespan,
        "cargo_ship_lifespan": cargo_lifespan,
        "tanker_lifespan": tanker_lifespan,
    }
    df, production_data, operations_data, mars_data = simulate_mars_transport(params)

    # People chart
    people_fig = go.Figure()
    people_fig.add_trace(go.Scatter(
        x=df["Year"], 
        y=df["People at Mars"],
        name="People at Mars", 
        line=dict(color="#3498db", width=3),
        fill='tozeroy',
        fillcolor='rgba(52, 152, 219, 0.1)'
    ))
    people_fig.update_layout(
        title={
            'text': "People at Mars",
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 18, 'color': '#2c3e50', 'family': 'system-ui, -apple-system, sans-serif'}
        },
        xaxis_title="Year",
        yaxis_title="Cumulative People",
        margin=dict(l=60, r=30, t=60, b=50),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family='system-ui, -apple-system, sans-serif', color='#2c3e50'),
        xaxis=dict(gridcolor='rgba(0,0,0,0.1)', showgrid=True),
        yaxis=dict(gridcolor='rgba(0,0,0,0.1)', showgrid=True),
        showlegend=False
    )

    # Cargo chart
    cargo_fig = go.Figure()
    cargo_fig.add_trace(go.Scatter(
        x=df["Year"], 
        y=df["Cargo at Mars (tons)"],
        name="Cargo at Mars", 
        line=dict(color="#e74c3c", width=3),
        fill='tozeroy',
        fillcolor='rgba(231, 76, 60, 0.1)'
    ))
    cargo_fig.update_layout(
        title={
            'text': "Cargo at Mars",
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 18, 'color': '#2c3e50', 'family': 'system-ui, -apple-system, sans-serif'}
        },
        xaxis_title="Year",
        yaxis_title="Cumulative Cargo (tons)",
        margin=dict(l=60, r=30, t=60, b=50),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family='system-ui, -apple-system, sans-serif', color='#2c3e50'),
        xaxis=dict(gridcolor='rgba(0,0,0,0.1)', showgrid=True),
        yaxis=dict(gridcolor='rgba(0,0,0,0.1)', showgrid=True),
        showlegend=False
    )

    # Fleet chart
    fleet_fig = go.Figure()
    fleet_fig.add_trace(go.Scatter(
        x=df["Year"], 
        y=df["Crew Ships Available"],
        name="Crew Ships", 
        line=dict(color="#3498db", width=3)
    ))
    fleet_fig.add_trace(go.Scatter(
        x=df["Year"], 
        y=df["Cargo Ships Available"],
        name="Cargo Ships", 
        line=dict(color="#2ecc71", width=3)
    ))
    fleet_fig.add_trace(go.Scatter(
        x=df["Year"], 
        y=df["Tankers Available"],
        name="Tankers", 
        line=dict(color="#f39c12", width=3)
    ))
    fleet_fig.update_layout(
        title={
            'text': "Available Fleet Size",
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 18, 'color': '#2c3e50', 'family': 'system-ui, -apple-system, sans-serif'}
        },
        xaxis_title="Year",
        yaxis_title="Ships Available on Earth",
        margin=dict(l=60, r=30, t=60, b=50),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family='system-ui, -apple-system, sans-serif', color='#2c3e50'),
        xaxis=dict(gridcolor='rgba(0,0,0,0.1)', showgrid=True),
        yaxis=dict(gridcolor='rgba(0,0,0,0.1)', showgrid=True),
        legend=dict(
            x=0.02, 
            y=0.98,
            bgcolor='rgba(255,255,255,0.8)',
            bordercolor='rgba(0,0,0,0.1)',
            borderwidth=1,
            font=dict(size=12)
        )
    )

    # LEO Fuel Depot chart
    fuel_fig = go.Figure()
    fuel_fig.add_trace(go.Scatter(
        x=df["Year"], 
        y=df["LEO Fuel Depot"],
        name="LEO Fuel Storage", 
        line=dict(color="#9b59b6", width=3),
        fill='tozeroy',
        fillcolor='rgba(155, 89, 182, 0.1)'
    ))
    fuel_fig.add_trace(go.Scatter(
        x=df["Year"], 
        y=df["Fuel Needed for Fleet"],
        name="Fuel Needed for Fleet", 
        line=dict(color="#e74c3c", width=2, dash='dash')
    ))
    fuel_fig.update_layout(
        title={
            'text': "LEO Fuel Depot vs Fleet Needs",
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 18, 'color': '#2c3e50', 'family': 'system-ui, -apple-system, sans-serif'}
        },
        xaxis_title="Year",
        yaxis_title="Fuel (tons LOX & CH4)",
        margin=dict(l=60, r=30, t=60, b=50),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family='system-ui, -apple-system, sans-serif', color='#2c3e50'),
        xaxis=dict(gridcolor='rgba(0,0,0,0.1)', showgrid=True),
        yaxis=dict(gridcolor='rgba(0,0,0,0.1)', showgrid=True),
        legend=dict(
            x=0.02, 
            y=0.98,
            bgcolor='rgba(255,255,255,0.8)',
            bordercolor='rgba(0,0,0,0.1)',
            borderwidth=1,
            font=dict(size=12)
        )
    )

    # Mars Fuel Demand chart
    mars_fuel_fig = go.Figure()
    mars_fuel_fig.add_trace(go.Scatter(
        x=df["Year"], 
        y=df["Mars Fuel Demand"],
        name="Cumulative Mars Fuel Demand", 
        line=dict(color="#f39c12", width=3),
        fill='tozeroy',
        fillcolor='rgba(243, 156, 18, 0.1)'
    ))
    mars_fuel_fig.update_layout(
        title={
            'text': "Mars ISRU Fuel Demand",
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 18, 'color': '#2c3e50', 'family': 'system-ui, -apple-system, sans-serif'}
        },
        xaxis_title="Year",
        yaxis_title="Cumulative Fuel Demand (tons)",
        margin=dict(l=60, r=30, t=60, b=50),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family='system-ui, -apple-system, sans-serif', color='#2c3e50'),
        xaxis=dict(gridcolor='rgba(0,0,0,0.1)', showgrid=True),
        yaxis=dict(gridcolor='rgba(0,0,0,0.1)', showgrid=True),
        showlegend=False
    )
    
    # Return table data for display
    return people_fig, cargo_fig, fleet_fig, fuel_fig, mars_fuel_fig, production_data, operations_data, mars_data

if __name__ == "__main__":
    app.run(debug=True)