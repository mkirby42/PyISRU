import math
import logging
from scipy.integrate import solve_ivp
import numpy as np
from .chemical_process import ChemicalProcess
from .resource_bus import ResourceType
from .units import (Q_, mol, second, kelvin, joule, cubic_meter, 
                   mol_per_second, joule_per_mol, joule_per_mol_kelvin,
                   cubic_meter_per_second, R_GAS_CONSTANT, pre_exponential_units,
                   ensure_units, strip_units, reaction_rate_unit, pascal, 
                   kilogram, meter, gram)

logger = logging.getLogger(__name__)

class Methanation(ChemicalProcess):
    def __init__(self, resource_bus, rate_constant=Q_(0.1, mol_per_second)):
        super().__init__(resource_bus)
        self.rate_constant = ensure_units(rate_constant, mol_per_second)
        self.time_elapsed = Q_(0, second)
        self.total_consumed = {"CO2": Q_(0, mol), "H2": Q_(0, mol)}
        self.total_produced = {"CH4": Q_(0, mol), "H2O": Q_(0, mol)}
        # Track initial inventory for conversion and visualization
        self.initial_moles = {}
        # Track instantaneous, reactant-limited actual rate (mol/s)
        self.last_actual_rate = Q_(0.0, mol_per_second)
        # Batch model: no inlet/outlet flow; expose zeros for consistency
        self.last_inlet_flows = {
            ResourceType.CO2: Q_(0.0, mol_per_second),
            ResourceType.H2: Q_(0.0, mol_per_second),
            ResourceType.CH4: Q_(0.0, mol_per_second),
            ResourceType.H2O: Q_(0.0, mol_per_second),
        }
        self.last_outlet_flows = {
            ResourceType.CO2: Q_(0.0, mol_per_second),
            ResourceType.H2: Q_(0.0, mol_per_second),
            ResourceType.CH4: Q_(0.0, mol_per_second),
            ResourceType.H2O: Q_(0.0, mol_per_second),
        }
        
        # Initialize moles if not present
        for species in [ResourceType.CO2, ResourceType.H2, ResourceType.CH4, ResourceType.H2O]:
            if species not in resource_bus.resources:
                logger.warning(f"{species.value} not found in resources. Initializing to 0.0 moles.")
                resource_bus.add_resource(species, Q_(0.0, mol))
        # Capture initial moles after ensuring presence
        for species in [ResourceType.CO2, ResourceType.H2, ResourceType.CH4, ResourceType.H2O]:
            self.initial_moles[species.value] = self.resource_bus.get_resource(species)

    def rate_function(self, t):
        """
        Rate function r(t) for the reaction
        Returns pint quantity in mol/s
        """
        return self.rate_constant

    def tick(self, time_seconds):
        """
        Update moles based on Sabatier reaction stoichiometry:
        CO₂ + 4H₂ → CH₄ + 2H₂O
        
        Rate equations:
        d[CO₂]/dt = -r(t)
        d[H₂]/dt = -4r(t)  
        d[CH₄]/dt = +r(t)
        d[H₂O]/dt = +2r(t)
        """
        dt = ensure_units(time_seconds, second)
        r_t = self.rate_function(self.time_elapsed)
        
        # Check if we have enough reactants
        co2_available = self.resource_bus.get_resource(ResourceType.CO2)
        h2_available = self.resource_bus.get_resource(ResourceType.H2)
        
        # Limit reaction rate by available reactants
        if dt > Q_(0, second):
            max_rate_co2 = co2_available / dt
            max_rate_h2 = h2_available / (4 * dt)
            actual_rate = min(r_t, max_rate_co2, max_rate_h2)
        else:
            actual_rate = Q_(0, mol_per_second)
        
        if actual_rate > Q_(0, mol_per_second):
            # Update moles based on stoichiometry
            delta_co2 = -actual_rate * dt
            delta_h2 = -4 * actual_rate * dt
            delta_ch4 = actual_rate * dt
            delta_h2o = 2 * actual_rate * dt
            
            # Apply changes (consume_resource expects positive amounts)
            self.resource_bus.consume_resource(ResourceType.CO2, -delta_co2)  
            self.resource_bus.consume_resource(ResourceType.H2, -delta_h2)    
            
            current_ch4 = self.resource_bus.get_resource(ResourceType.CH4)
            current_h2o = self.resource_bus.get_resource(ResourceType.H2O)
            self.resource_bus.set_resource(ResourceType.CH4, current_ch4 + delta_ch4)
            self.resource_bus.set_resource(ResourceType.H2O, current_h2o + delta_h2o)
            
            # Update total consumed and produced
            self.total_consumed["CO2"] += -delta_co2
            self.total_consumed["H2"] += -delta_h2
            self.total_produced["CH4"] += delta_ch4
            self.total_produced["H2O"] += delta_h2o
        
        # Store actual instantaneous rate used this tick
        self.last_actual_rate = actual_rate
        
        self.time_elapsed += dt
    
    def inputs(self):
        return [ResourceType.CO2, ResourceType.H2]
    
    def outputs(self):
        return [ResourceType.CH4, ResourceType.H2O]
    
    def status(self):
        return {
            "time_elapsed": self.time_elapsed,
            "rate_constant": self.rate_constant,
            "current_rate": self.rate_function(self.time_elapsed),
            "actual_rate": self.last_actual_rate,
            "moles_CO2": self.resource_bus.get_resource(ResourceType.CO2),
            "moles_H2": self.resource_bus.get_resource(ResourceType.H2), 
            "moles_CH4": self.resource_bus.get_resource(ResourceType.CH4),
            "moles_H2O": self.resource_bus.get_resource(ResourceType.H2O),
            # Expose inlet/outlet flows (batch: zeros)
            "inlet_flow_CO2": self.last_inlet_flows[ResourceType.CO2],
            "inlet_flow_H2": self.last_inlet_flows[ResourceType.H2],
            "inlet_flow_CH4": self.last_inlet_flows[ResourceType.CH4],
            "inlet_flow_H2O": self.last_inlet_flows[ResourceType.H2O],
            "outlet_flow_CO2": self.last_outlet_flows[ResourceType.CO2],
            "outlet_flow_H2": self.last_outlet_flows[ResourceType.H2],
            "outlet_flow_CH4": self.last_outlet_flows[ResourceType.CH4],
            "outlet_flow_H2O": self.last_outlet_flows[ResourceType.H2O],
            "total_consumed_CO2": self.total_consumed["CO2"],
            "total_consumed_H2": self.total_consumed["H2"],
            "total_produced_CH4": self.total_produced["CH4"],
            "total_produced_H2O": self.total_produced["H2O"],
            "initial_moles": self.initial_moles
        }

class MethanationWithArrheniusKinetics(Methanation):
    """
    CO2 + 4 H2 -> CH4 + 2 H2O
    Simple power-law kinetics: r_vol = k(T) * c_CO2^a * c_H2^b  [mol m^-3 s^-1]
    """

    def __init__(
        self,
        resource_bus,
        *,
        pre_exponential,          # e.g. Q_(1.0e-3,  m**9 / mol**4 / second) for a=1,b=4 (overall 5th order)
        activation_energy,        # Q_(Ea, joule_per_mol)
        temperature,              # Q_(T, kelvin)   (or provide a setter / energy balance later)
        reactor_volume,           # Q_(V, cubic_meter)
        orders=(1.0, 4.0)         # (a, b): orders in CO2 and H2
    ):
        super().__init__(resource_bus, rate_constant=Q_(0.0, mol/second))
        self.pre_exponential = ensure_units(pre_exponential, pre_exponential.units)
        self.activation_energy = ensure_units(activation_energy, joule_per_mol)
        self.temperature = ensure_units(temperature, kelvin)
        self.reactor_volume = ensure_units(reactor_volume, cubic_meter)
        self.orders = orders  # (a, b)
        self.R = R_GAS_CONSTANT  # J/mol/K

    def rate_constant_arrhenius(self, T=None):
        T = self.temperature if T is None else ensure_units(T, kelvin)
        Ea = self.activation_energy
        R = self.R
        # dimensionless exponent
        exponent = -(Ea / (R * T)).to_base_units().magnitude
        return self.pre_exponential * np.exp(exponent)
    
    def _y_from_bus(self) -> np.ndarray:
        # State vector in moles (floats, SI)
        n_CO2 = strip_units(self.resource_bus.get_resource(ResourceType.CO2).to(mol))
        n_H2  = strip_units(self.resource_bus.get_resource(ResourceType.H2 ).to(mol))
        n_CH4 = strip_units(self.resource_bus.get_resource(ResourceType.CH4).to(mol))
        n_H2O = strip_units(self.resource_bus.get_resource(ResourceType.H2O).to(mol))
        return np.array([n_CO2, n_H2, n_CH4, n_H2O], dtype=float)

    def _bus_from_y(self, y: np.ndarray) -> None:
        # Push moles back into the resource bus
        self.resource_bus.set_resource(ResourceType.CO2, Q_(max(y[0], 0.0), mol))
        self.resource_bus.set_resource(ResourceType.H2,  Q_(max(y[1], 0.0), mol))
        self.resource_bus.set_resource(ResourceType.CH4, Q_(max(y[2], 0.0), mol))
        self.resource_bus.set_resource(ResourceType.H2O, Q_(max(y[3], 0.0), mol))

    def _ode_rhs(self, t: float, y: np.ndarray) -> np.ndarray:
        # y = [n_CO2, n_H2, n_CH4, n_H2O] in mol
        n_CO2, n_H2, n_CH4, n_H2O = y
        V = strip_units(self.reactor_volume.to(cubic_meter))  # m^3
        if V <= 0.0:
            return np.zeros_like(y)

        # concentrations [mol/m^3]
        c_CO2 = max(n_CO2, 0.0) / V
        c_H2  = max(n_H2,  0.0) / V

        a, b = self.orders
        kT = strip_units(self.rate_constant_arrhenius(self.temperature))  # in your chosen units for k
        # volumetric rate [mol/m^3/s]
        r_vol = kT * (c_CO2 ** a) * (c_H2 ** b)
        # reactor-wide rate [mol/s]
        r = r_vol * V

        # Stoichiometry: CO2 + 4H2 -> CH4 + 2H2O
        dn_CO2 = -r
        dn_H2  = -4.0 * r
        dn_CH4 = +r
        dn_H2O = +2.0 * r
        return np.array([dn_CO2, dn_H2, dn_CH4, dn_H2O], dtype=float)

    def _compute_last_rate(self, y: np.ndarray):
        # Store last_actual_rate in mol/s at the final state
        n_CO2, n_H2, *_ = y
        V = strip_units(self.reactor_volume.to(cubic_meter))
        if V <= 0.0:
            self.last_actual_rate = Q_(0.0, mol_per_second)
            return
        c_CO2 = max(n_CO2, 0.0) / V
        c_H2  = max(n_H2,  0.0) / V
        a, b = self.orders
        kT = strip_units(self.rate_constant_arrhenius(self.temperature))
        r_vol = kT * (c_CO2 ** a) * (c_H2 ** b)
        self.last_actual_rate = Q_(r_vol * V, mol_per_second)

    def tick(self, time_seconds):
        dt_q = ensure_units(time_seconds, second)
        if dt_q <= Q_(0, second):
            return

        # Time window in seconds (float)
        t_span = (0.0, strip_units(dt_q.to(second)))
        y0 = self._y_from_bus()

        # Stop if reactants will go negative; define an event:
        def depletion_event(t, y):
            # Stop when either CO2 hits 0 or H2/4 hits 0 (stoich-limited)
            n_CO2, n_H2, *_ = y
            return min(n_CO2, n_H2 / 4.0)
        depletion_event.terminal = True
        depletion_event.direction = -1

        sol = solve_ivp(
            fun=self._ode_rhs,
            t_span=t_span,
            y0=y0,
            method="BDF",             # robust for stiff/high-order kinetics
            rtol=1e-6,
            atol=1e-9,
            events=depletion_event,
            max_step=t_span[1] / 50 if t_span[1] > 0 else None
        )

        y_final = sol.y[:, -1]

        # Update bus and tallies
        self._bus_from_y(y_final)

        dn = y_final - y0  # mol deltas over this tick
        # Totals (use sign to separate consumed/produced)
        self.total_consumed["CO2"] += Q_(max(-dn[0], 0.0), mol)
        self.total_consumed["H2"]  += Q_(max(-dn[1], 0.0), mol)
        self.total_produced["CH4"] += Q_(max( dn[2], 0.0), mol)
        self.total_produced["H2O"] += Q_(max( dn[3], 0.0), mol)

        # Bookkeeping
        self._compute_last_rate(y_final)
        self.time_elapsed += dt_q

    def status(self):
        s = super().status()
        s.update({
            "A_pre_exponential": self.pre_exponential,
            "Ea": self.activation_energy,
            "temperature": self.temperature,
            "reactor_volume": self.reactor_volume,
            "k_T": self.rate_constant_arrhenius(self.temperature),
        })
        return s

class AdvancedPFRMethanation(Methanation):
    """
    Plug Flow Reactor (PFR) model for methanation (CO2 + 4 H2 -> CH4 + 2 H2O)
    with Arrhenius kinetics, nonisothermal energy balance, and pressure drop.
    State vector y(z) = [F_CO2, F_H2, F_CH4, F_H2O, T, P]
      - F_i: molar flow of species i (mol/s)
      - T  : temperature (K)
      - P  : pressure (Pa)
    Independent variable: axial coordinate z (m)
    """

    # ---- Species names for property lookups
    _S_CO2 = ResourceType.CO2
    _S_H2  = ResourceType.H2
    _S_CH4 = ResourceType.CH4
    _S_H2O = ResourceType.H2O

    def __init__(
        self,
        resource_bus,
        *,
        # Kinetics: r_vol = k(T) * c_CO2^a * c_H2^b  (mol m^-3 s^-1)
        pre_exponential,          # e.g., Q_(1e-3, m**12 / mol**4 / second) for a=1, b=4
        activation_energy,        # Q_(Ea, joule_per_mol)
        orders=(1.0, 4.0),        # (a, b) reactant orders in CO2 and H2
        product_orders=(1.0, 2.0),# (g, d) product orders in CH4 and H2O (default stoich)
        # Optional equilibrium model (dimensionless K_eq). If equilibrium_constant_ref is None,
        # reverse term is disabled (keeps prior behavior). If provided, K_eq follows van't Hoff
        # with self.delta_Hr as reaction enthalpy and T_ref at which K_eq_ref is specified.
        equilibrium_constant_ref=None,           # float or quantity, dimensionless
        equilibrium_T_ref=Q_(298.15, kelvin),
        # Operating conditions (inlet)
        temperature=Q_(573, kelvin),
        inlet_pressure=Q_(101325, pascal),
        volumetric_flow_rate=Q_(0.01, cubic_meter_per_second),  # at inlet
        # Geometry / packed bed / heat transfer
        reactor_volume=Q_(1.0, cubic_meter),  # bed volume (catalyst + void)
        tube_diameter=Q_(0.10, meter),        # 10 cm ID tube
        void_fraction=0.40,                   # bed voids, epsilon
        particle_diameter=Q_(3e-3, meter),    # 3 mm pellets
        overall_U=Q_(50.0, joule/(second*meter**2*kelvin)),  # W/m^2/K
        ambient_temperature=Q_(300.0, kelvin),
        # Transport props (simple models)
        gas_viscosity=Q_(2.0e-5, kilogram/(meter*second)),    # Pa·s
        # Reaction heat (assumed constant; negative for exothermic)
        heat_of_reaction=Q_(-165e3, joule_per_mol),           # ~ -165 kJ/mol
        # Cp (molar, assumed constant; tweak as needed)
        cp_molar_CO2=Q_(44.0, joule_per_mol_kelvin),
        cp_molar_H2 =Q_(29.0, joule_per_mol_kelvin),
        cp_molar_CH4=Q_(35.0, joule_per_mol_kelvin),
        cp_molar_H2O=Q_(36.0, joule_per_mol_kelvin),
        # Molecular weights (kg/mol)
        mw_CO2=Q_(44.0095e-3, kilogram/mol),
        mw_H2 =Q_(2.01588e-3, kilogram/mol),
        mw_CH4=Q_(16.043e-3, kilogram/mol),
        mw_H2O=Q_(18.01528e-3, kilogram/mol),
    ):
        # Base class (we do not use its zero-order rate)
        super().__init__(resource_bus, rate_constant=Q_(0.0, mol/second))

        # --- Store kinetic parameters
        self.pre_exponential = ensure_units(pre_exponential, pre_exponential.units)
        self.activation_energy = ensure_units(activation_energy, joule_per_mol)
        self.orders = orders  # (a, b)
        self.product_orders = product_orders  # (g, d)
        self.R = R_GAS_CONSTANT

        # --- Operating (inlet) state
        self.temperature = ensure_units(temperature, kelvin)           # inlet T
        self.inlet_pressure = ensure_units(inlet_pressure, pascal)     # inlet P
        self.volumetric_flow_rate_in = ensure_units(volumetric_flow_rate, cubic_meter_per_second)

        # --- Geometry / bed / HT
        self.reactor_volume = ensure_units(reactor_volume, cubic_meter)  # bed volume
        self.tube_diameter = ensure_units(tube_diameter, meter)
        self.void_fraction = float(void_fraction)
        self.particle_diameter = ensure_units(particle_diameter, meter)
        self.U_overall = ensure_units(overall_U, joule/(second*meter**2*kelvin))
        self.T_amb = ensure_units(ambient_temperature, kelvin)

        # --- Transport props
        self.mu_gas = ensure_units(gas_viscosity, kilogram/(meter*second))

        # --- Thermo / properties
        self.delta_Hr = ensure_units(heat_of_reaction, joule_per_mol)
        self.cp_molar = {
            self._S_CO2: ensure_units(cp_molar_CO2, joule_per_mol_kelvin),
            self._S_H2:  ensure_units(cp_molar_H2,  joule_per_mol_kelvin),
            self._S_CH4: ensure_units(cp_molar_CH4, joule_per_mol_kelvin),
            self._S_H2O: ensure_units(cp_molar_H2O, joule_per_mol_kelvin),
        }
        self.MW = {
            self._S_CO2: ensure_units(mw_CO2, kilogram/mol),
            self._S_H2:  ensure_units(mw_H2,  kilogram/mol),
            self._S_CH4: ensure_units(mw_CH4, kilogram/mol),
            self._S_H2O: ensure_units(mw_H2O, kilogram/mol),
        }

        # --- Equilibrium model (dimensionless K_eq based on activities)
        if equilibrium_constant_ref is None:
            self.K_eq_ref = None
        else:
            try:
                # Accept raw float/int or pint quantity; store as plain float (dimensionless)
                self.K_eq_ref = float(getattr(equilibrium_constant_ref, 'magnitude', equilibrium_constant_ref))
            except Exception:
                self.K_eq_ref = None
        self.T_ref_for_K = ensure_units(equilibrium_T_ref, kelvin)
        # standard concentration for activities (a_i = c_i / c_std), choose 1 mol/m^3
        self.c_std = Q_(1.0, mol/cubic_meter)

        # --- Derived geometry
        self.A = Q_(math.pi * (self.tube_diameter.magnitude ** 2) / 4.0, meter**2)  # cross-section
        # Use bed volume to set length
        self.length = (self.reactor_volume / self.A).to(meter)
        self.perimeter = Q_(math.pi * self.tube_diameter.magnitude, meter)          # inner perimeter
        self.UPw = (self.U_overall * self.perimeter)  # J/(s·m·K) == W/m/K

        # --- Caches / diagnostics
        self.last_profile = None
        self.last_rate = Q_(0.0, reaction_rate_unit)
        self.last_inlet_flows = {s: Q_(0.0, mol_per_second) for s in [self._S_CO2, self._S_H2, self._S_CH4, self._S_H2O]}
        self.last_outlet_flows = {s: Q_(0.0, mol_per_second) for s in [self._S_CO2, self._S_H2, self._S_CH4, self._S_H2O]}
        self._last_solver_info = {}

    # ------------ Kinetics & properties

    def rate_constant_arrhenius(self, T):
        T = ensure_units(T, kelvin)
        Ea = self.activation_energy
        R  = self.R
        exponent = -(Ea / (R * T)).to_base_units().magnitude
        return self.pre_exponential * np.exp(exponent)  # retains units of A

    def equilibrium_constant(self, T):
        """Return dimensionless K_eq(T) using van't Hoff if reference provided; else very large."""
        if self.K_eq_ref is None:
            # effectively irreversible (reverse term -> 0)
            return float('inf')
        T = ensure_units(T, kelvin)
        T_ref = self.T_ref_for_K
        dHr = strip_units(self.delta_Hr)  # J/mol
        R = strip_units(self.R)           # J/mol/K
        invT = 1.0 / T.to(kelvin).magnitude
        invTref = 1.0 / T_ref.to(kelvin).magnitude
        lnK = math.log(max(1e-300, self.K_eq_ref)) - (dHr / R) * (invT - invTref)
        # guard for extremes
        lnK = max(-700.0, min(700.0, lnK))
        return math.exp(lnK)

    def _mixture_cp(self, T, F):
        """Return mixture molar Cp (J/mol/K) from mole-fraction average."""
        F_CO2, F_H2, F_CH4, F_H2O = F
        ntot = max(1e-30, F_CO2 + F_H2 + F_CH4 + F_H2O)
        y = {
            self._S_CO2: F_CO2/ntot,
            self._S_H2:  F_H2/ntot,
            self._S_CH4: F_CH4/ntot,
            self._S_H2O: F_H2O/ntot
        }
        Cp = sum(y[s] * self.cp_molar[s].magnitude for s in y)  # J/mol/K
        return Q_(Cp, joule_per_mol_kelvin)

    def _mixture_MW(self, F):
        """Return mixture mean molecular weight (kg/mol)."""
        F_CO2, F_H2, F_CH4, F_H2O = F
        ntot = max(1e-30, F_CO2 + F_H2 + F_CH4 + F_H2O)
        y_CO2 = F_CO2/ntot; y_H2 = F_H2/ntot; y_CH4 = F_CH4/ntot; y_H2O = F_H2O/ntot
        MW = (y_CO2*self.MW[self._S_CO2] + y_H2*self.MW[self._S_H2] +
              y_CH4*self.MW[self._S_CH4] + y_H2O*self.MW[self._S_H2O])
        return MW

    def _volumetric_flow(self, F, T, P):
        """Ideal-gas volumetric flow (m^3/s): Vdot = n_dot R T / P."""
        n_dot = sum(F)
        Vdot = (self.R * T / P).to(cubic_meter_per_second / (mol/second)).magnitude * n_dot
        return Q_(Vdot, cubic_meter_per_second)

    def _concentrations(self, F, T, P):
        """Concentrations (mol/m^3) from flows using ideal gas."""
        Vdot = self._volumetric_flow(F, T, P)
        Vdot_mag = max(1e-30, Vdot.to(cubic_meter_per_second).magnitude)
        return np.array([F_i / Vdot_mag for F_i in F])  # mol/m^3

    def _ergun_dPdz(self, F, T, P):
        """Ergun pressure gradient dP/dz (Pa/m)."""
        Vdot = self._volumetric_flow(F, T, P).to(cubic_meter_per_second).magnitude
        A = self.A.to(meter**2).magnitude
        u = Vdot / max(1e-30, A)  # superficial velocity, m/s

        MW = self._mixture_MW(F).to(kilogram/mol)
        rho = (P * MW / (self.R * T)).to(kilogram/(meter**3)).magnitude  # kg/m^3

        mu = self.mu_gas.to(kilogram/(meter*second)).magnitude
        eps = self.void_fraction
        dp  = self.particle_diameter.to(meter).magnitude

        term1 = 150.0 * ((1 - eps)**2 / eps**3) * (mu * u / (dp**2))
        term2 = 1.75  * ((1 - eps)   / eps**3) * (rho * u**2 / dp)
        dPdz = -(term1 + term2)  # Pa/m
        return dPdz

    # ------------ PFR ODEs: dy/dz
    def _rhs(self, z, y):
        """
        y = [F_CO2, F_H2, F_CH4, F_H2O, T, P]
        returns dy/dz in [mol/s/m, ..., K/m, Pa/m]
        """
        F_CO2, F_H2, F_CH4, F_H2O, T, P = y
        # guard
        T = max(T, 1.0)           # K
        P = max(P, 100.0)         # Pa
        F = np.array([max(F_CO2,0.0), max(F_H2,0.0), max(F_CH4,0.0), max(F_H2O,0.0)], dtype=float)

        # Concentrations and reversible rate using activities
        c = self._concentrations(F, Q_(T, kelvin), Q_(P, pascal))  # mol/m^3
        a, b = self.orders
        g, d = self.product_orders
        kT = strip_units(self.rate_constant_arrhenius(Q_(T, kelvin)))  # units of A
        cstd = self.c_std.to(cubic_meter**-1 * mol).magnitude
        # activities (dimensionless)
        a_CO2 = max(c[0], 0.0) / max(1e-30, cstd)
        a_H2  = max(c[1], 0.0) / max(1e-30, cstd)
        a_CH4 = max(c[2], 0.0) / max(1e-30, cstd)
        a_H2O = max(c[3], 0.0) / max(1e-30, cstd)
        forward_term = (a_CO2**a) * (a_H2**b)
        reverse_term = (a_CH4**g) * (a_H2O**d)
        K_eq = self.equilibrium_constant(Q_(T, kelvin))
        # if K_eq is inf, reverse contribution is zero
        net_activity = forward_term - (0.0 if not math.isfinite(K_eq) else (reverse_term / max(1e-300, K_eq)))
        r_vol = kT * net_activity  # mol/m^3/s

        # Species ODEs
        A_cs = self.A.to(meter**2).magnitude
        dF_CO2 = - r_vol * A_cs
        dF_H2  = - 4.0 * r_vol * A_cs
        dF_CH4 = + r_vol * A_cs
        dF_H2O = + 2.0 * r_vol * A_cs

        # Energy ODE
        Cp_mix = strip_units(self._mixture_cp(Q_(T, kelvin), F))  # J/mol/K
        n_dot  = max(1e-30, sum(F))                               # mol/s
        dTdz_reaction = (- strip_units(self.delta_Hr) * r_vol * A_cs) / max(1e-30, (n_dot * Cp_mix))
        dTdz_loss     = (- (self.UPw.to(joule/(second*meter*kelvin)).magnitude) * (T - self.T_amb.to(kelvin).magnitude)) / max(1e-30, (n_dot * Cp_mix))
        dTdz = dTdz_reaction + dTdz_loss

        # Pressure-drop ODE
        dPdz = self._ergun_dPdz(F, Q_(T, kelvin), Q_(P, pascal))

        return np.array([dF_CO2, dF_H2, dF_CH4, dF_H2O, dTdz, dPdz], dtype=float)

    # ------------ Public API

    def simulate_pfr(self, inlet_flows):
        """
        Integrate along z from 0 -> L. Inlet state:
          F_i(0) from 'inlet_flows' (mol/s),
          T(0)   from self.temperature,
          P(0)   from self.inlet_pressure.
        Returns outlet molar flows as pint quantities.
        """
        F0 = np.array([
            strip_units(inlet_flows.get(self._S_CO2, Q_(0.0, mol_per_second))),
            strip_units(inlet_flows.get(self._S_H2,  Q_(0.0, mol_per_second))),
            strip_units(inlet_flows.get(self._S_CH4, Q_(0.0, mol_per_second))),
            strip_units(inlet_flows.get(self._S_H2O, Q_(0.0, mol_per_second))),
        ], dtype=float)

        T0 = self.temperature.to(kelvin).magnitude
        P0 = self.inlet_pressure.to(pascal).magnitude
        y0 = np.array([F0[0], F0[1], F0[2], F0[3], T0, P0], dtype=float)

        z_span = (0.0, self.length.to(meter).magnitude)

        # Early exit if no reactants
        if y0[0] <= 0.0 or y0[1] <= 0.0:
            self.last_rate = Q_(0.0, reaction_rate_unit)
            self.last_profile = None
            self.last_inlet_flows = {
                self._S_CO2: Q_(F0[0], mol_per_second),
                self._S_H2:  Q_(F0[1], mol_per_second),
                self._S_CH4: Q_(F0[2], mol_per_second),
                self._S_H2O: Q_(F0[3], mol_per_second),
            }
            self.last_outlet_flows = self.last_inlet_flows.copy()
            return self.last_outlet_flows

        # Integration (stiff-friendly)
        def depletion_event(z, y):
            # stop if any reactant exhausted or pressure collapses
            F_CO2, F_H2, _, _, _, P = y
            return min(F_CO2, F_H2/4.0, P - 1.0)  # Pa threshold
        depletion_event.terminal = True
        depletion_event.direction = -1

        sol = solve_ivp(
            fun=self._rhs,
            t_span=z_span,
            y0=y0,
            method="BDF",
            rtol=1e-6,
            atol=1e-9,
            events=depletion_event,
            max_step=(z_span[1] / 200.0 if z_span[1] > 0 else None)
        )

        self._last_solver_info = {
            "success": sol.success,
            "status": sol.status,
            "message": sol.message,
            "nfev": sol.nfev,
            "njev": getattr(sol, "njev", None),
            "nlu": getattr(sol, "nlu", None),
        }

        if not sol.success:
            logger.warning(f"PFR integration: {sol.message}")
        y_end = sol.y[:, -1]  # outlet

        # cache axial profile for visualization
        try:
            z_pts = np.linspace(z_span[0], sol.t[-1], 150)
            Y = sol.sol(z_pts) if sol.sol is not None else np.vstack([
                np.interp(z_pts, sol.t, sol.y[i, :]) for i in range(sol.y.shape[0])
            ])
            # compute rate profile (mol/m^3/s)
            rate_prof = []
            for i in range(Y.shape[1]):
                F = Y[0:4, i]
                T = Y[4, i]; P = Y[5, i]
                c = self._concentrations(F, Q_(T, kelvin), Q_(P, pascal))
                a, b = self.orders; g, d = self.product_orders
                kT = strip_units(self.rate_constant_arrhenius(Q_(T, kelvin)))
                cstd = self.c_std.to(cubic_meter**-1 * mol).magnitude
                a_CO2 = max(c[0], 0.0) / max(1e-30, cstd)
                a_H2  = max(c[1], 0.0) / max(1e-30, cstd)
                a_CH4 = max(c[2], 0.0) / max(1e-30, cstd)
                a_H2O = max(c[3], 0.0) / max(1e-30, cstd)
                forward_term = (a_CO2**a) * (a_H2**b)
                reverse_term = (a_CH4**g) * (a_H2O**d)
                K_eq = self.equilibrium_constant(Q_(T, kelvin))
                net_activity = forward_term - (0.0 if not math.isfinite(K_eq) else (reverse_term / max(1e-300, K_eq)))
                rate_prof.append(kT * net_activity)
            rate_prof = np.asarray(rate_prof)

            self.last_profile = {
                "z": z_pts,
                "F_profile": Y[0:4, :],
                "T_profile": Y[4, :],
                "P_profile": Y[5, :],
                "rate_profile": rate_prof,
            }
            # store a representative mid-bed volumetric rate
            mid_idx = len(z_pts)//2
            self.last_rate = Q_(rate_prof[mid_idx], reaction_rate_unit)
        except Exception:
            self.last_profile = None
            self.last_rate = Q_(0.0, reaction_rate_unit)

        F_out = y_end[0:4]
        self.last_inlet_flows = {
            self._S_CO2: Q_(F0[0], mol_per_second),
            self._S_H2:  Q_(F0[1], mol_per_second),
            self._S_CH4: Q_(F0[2], mol_per_second),
            self._S_H2O: Q_(F0[3], mol_per_second),
        }
        self.last_outlet_flows = {
            self._S_CO2: Q_(max(0.0, F_out[0]), mol_per_second),
            self._S_H2:  Q_(max(0.0, F_out[1]), mol_per_second),
            self._S_CH4: Q_(max(0.0, F_out[2]), mol_per_second),
            self._S_H2O: Q_(max(0.0, F_out[3]), mol_per_second),
        }
        return self.last_outlet_flows

    def get_axial_profiles(self, num_points=150):
        if not self.last_profile:
            return None
        # resample if needed
        z = self.last_profile["z"]
        def _resample(x):
            return np.interp(np.linspace(z[0], z[-1], num_points), z, x)
        prof = {
            "z_fraction": np.linspace(0.0, 1.0, num_points),
            "F_CO2": _resample(self.last_profile["F_profile"][0]),
            "F_H2":  _resample(self.last_profile["F_profile"][1]),
            "F_CH4": _resample(self.last_profile["F_profile"][2]),
            "F_H2O": _resample(self.last_profile["F_profile"][3]),
            "T":     _resample(self.last_profile["T_profile"]),
            "P":     _resample(self.last_profile["P_profile"]),
            "rate":  _resample(self.last_profile["rate_profile"]),
        }
        # conversion based on inlet CO2
        F0_CO2 = max(1e-30, self.last_inlet_flows[self._S_CO2].to(mol_per_second).magnitude)
        prof["conversion_CO2"] = np.clip((F0_CO2 - prof["F_CO2"]) / F0_CO2, 0.0, 1.0)
        return prof

    def tick(self, time_seconds):
        """
        "Operate" the steady-state PFR over a finite dt by:
          1) building an inlet feed (CO2:H2 ~ 1:4, limited by inventory & inlet Vdot),
          2) solving the steady PFR for those inlet flows,
          3) consuming inventory by (Fin - Fout)*dt and accumulating products Fout*dt.
        """
        dt = ensure_units(time_seconds, second)
        if dt <= Q_(0, second):
            return

        # Available inventory
        n_CO2 = self.resource_bus.get_resource(self._S_CO2)
        n_H2  = self.resource_bus.get_resource(self._S_H2)
        n_CH4 = self.resource_bus.get_resource(self._S_CH4)
        n_H2O = self.resource_bus.get_resource(self._S_H2O)

        if n_CO2 <= Q_(0, mol) or n_H2 <= Q_(0, mol):
            self.time_elapsed += dt
            return

        # Build inlet flows: assume stoich split and cap by inlet volumetric capacity and inventory
        T_in = self.temperature
        P_in = self.inlet_pressure
        c_tot_in = (P_in / (self.R * T_in)).to(mol/cubic_meter)               # mol/m^3
        n_dot_max = (c_tot_in * self.volumetric_flow_rate_in).to(mol/second) # mol/s
        F_CO2_in = min(n_dot_max / 5.0, n_CO2 / dt, n_H2 / (4.0*dt))
        F_H2_in  = 4.0 * F_CO2_in

        inlet = {
            self._S_CO2: F_CO2_in,
            self._S_H2:  F_H2_in,
            self._S_CH4: Q_(0.0, mol_per_second),
            self._S_H2O: Q_(0.0, mol_per_second),
        }

        outlet = self.simulate_pfr(inlet)

        # Convert molar flow differences into inventory changes over dt
        d_CO2 = (inlet[self._S_CO2] - outlet[self._S_CO2]) * dt
        d_H2  = (inlet[self._S_H2]  - outlet[self._S_H2])  * dt
        d_CH4 = outlet[self._S_CH4] * dt
        d_H2O = outlet[self._S_H2O] * dt

        # Clamp tiny negatives
        d_CO2 = max(d_CO2, Q_(0.0, mol))
        d_H2  = max(d_H2,  Q_(0.0, mol))

        # Apply to resource bus
        self.resource_bus.consume_resource(self._S_CO2, d_CO2)
        self.resource_bus.consume_resource(self._S_H2,  d_H2)
        self.resource_bus.set_resource(self._S_CH4, n_CH4 + d_CH4)
        self.resource_bus.set_resource(self._S_H2O, n_H2O + d_H2O)

        # Totals
        self.total_consumed["CO2"] += d_CO2
        self.total_consumed["H2"]  += d_H2
        self.total_produced["CH4"] += d_CH4
        self.total_produced["H2O"] += d_H2O

        self.time_elapsed += dt

    def rate_function(self, t):
        """Not used (PFR is solved via spatial ODEs)."""
        return self.rate_constant_arrhenius(self.temperature)

    def status(self):
        base = super().status()
        base.update({
            "reactor_type": "PFR-Advanced",
            "reactor_volume": self.reactor_volume,
            "length": self.length,
            "area": self.A,
            "tube_diameter": self.tube_diameter,
            "void_fraction": self.void_fraction,
            "porosity": self.void_fraction,
            "particle_diameter": self.particle_diameter,
            "overall_heat_transfer_coefficient": self.UPw,
            "inlet_temperature": self.temperature,
            "inlet_pressure": self.inlet_pressure,
            "inlet_volumetric_flow": self.volumetric_flow_rate_in,
            "arrhenius_pre_exponential": self.pre_exponential,
            "arrhenius_activation_energy": self.activation_energy,
            "orders": self.orders,
            "product_orders": self.product_orders,
            "heat_of_reaction": self.delta_Hr,
            "equilibrium_constant": self.equilibrium_constant(self.temperature),
            "current_reaction_rate_midbed": self.last_rate,
            # Derived/latest outlet estimates if a profile exists
            "outlet_temperature": (Q_(self.last_profile["T_profile"][-1], kelvin)
                                     if (self.last_profile and len(self.last_profile.get("T_profile", []))>0)
                                     else self.temperature),
            "outlet_pressure": (Q_(self.last_profile["P_profile"][-1], pascal)
                                   if (self.last_profile and len(self.last_profile.get("P_profile", []))>0)
                                   else self.inlet_pressure),
            # Flatten inlet/outlet flows by species
            "inlet_flow_CO2": self.last_inlet_flows[self._S_CO2],
            "inlet_flow_H2":  self.last_inlet_flows[self._S_H2],
            "inlet_flow_CH4": self.last_inlet_flows[self._S_CH4],
            "inlet_flow_H2O": self.last_inlet_flows[self._S_H2O],
            "outlet_flow_CO2": self.last_outlet_flows[self._S_CO2],
            "outlet_flow_H2":  self.last_outlet_flows[self._S_H2],
            "outlet_flow_CH4": self.last_outlet_flows[self._S_CH4],
            "outlet_flow_H2O": self.last_outlet_flows[self._S_H2O],
            "solver_info": self._last_solver_info,
        })
        return base


class PFRMethanation(Methanation):
    """
    Plug Flow Reactor (PFR) model for methanation with Arrhenius kinetics,
    isothermal and isobaric (no dT/dz, no dP/dz). 4-ODE system over z for
    species molar flows.
    """

    _S_CO2 = ResourceType.CO2
    _S_H2  = ResourceType.H2
    _S_CH4 = ResourceType.CH4
    _S_H2O = ResourceType.H2O

    def __init__(
        self,
        resource_bus,
        *,
        pre_exponential,
        activation_energy,
        orders=(1.0, 4.0),
        temperature=Q_(573, kelvin),
        inlet_pressure=Q_(101325, pascal),
        volumetric_flow_rate=Q_(0.01, cubic_meter_per_second),
        reactor_volume=Q_(1.0, cubic_meter),
        tube_diameter=Q_(0.10, meter),
        void_fraction=0.40,
        particle_diameter=Q_(3e-3, meter),
        overall_U=Q_(50.0, joule/(second*meter**2*kelvin)),
        ambient_temperature=Q_(300.0, kelvin),
        gas_viscosity=Q_(2.0e-5, kilogram/(meter*second)),
        heat_of_reaction=Q_(-165e3, joule_per_mol),
        cp_molar_CO2=Q_(44.0, joule_per_mol_kelvin),
        cp_molar_H2 =Q_(29.0, joule_per_mol_kelvin),
        cp_molar_CH4=Q_(35.0, joule_per_mol_kelvin),
        cp_molar_H2O=Q_(36.0, joule_per_mol_kelvin),
        mw_CO2=Q_(44.0095e-3, kilogram/mol),
        mw_H2 =Q_(2.01588e-3, kilogram/mol),
        mw_CH4=Q_(16.043e-3, kilogram/mol),
        mw_H2O=Q_(18.01528e-3, kilogram/mol),
    ):
        super().__init__(resource_bus, rate_constant=Q_(0.0, mol/second))

        self.pre_exponential = ensure_units(pre_exponential, pre_exponential.units)
        self.activation_energy = ensure_units(activation_energy, joule_per_mol)
        self.orders = orders
        self.R = R_GAS_CONSTANT

        self.temperature = ensure_units(temperature, kelvin)
        self.inlet_pressure = ensure_units(inlet_pressure, pascal)
        self.volumetric_flow_rate_in = ensure_units(volumetric_flow_rate, cubic_meter_per_second)

        self.reactor_volume = ensure_units(reactor_volume, cubic_meter)
        self.tube_diameter = ensure_units(tube_diameter, meter)
        self.void_fraction = float(void_fraction)
        self.particle_diameter = ensure_units(particle_diameter, meter)
        self.U_overall = ensure_units(overall_U, joule/(second*meter**2*kelvin))
        self.T_amb = ensure_units(ambient_temperature, kelvin)

        self.mu_gas = ensure_units(gas_viscosity, kilogram/(meter*second))
        self.delta_Hr = ensure_units(heat_of_reaction, joule_per_mol)
        self.cp_molar = {
            self._S_CO2: ensure_units(cp_molar_CO2, joule_per_mol_kelvin),
            self._S_H2:  ensure_units(cp_molar_H2,  joule_per_mol_kelvin),
            self._S_CH4: ensure_units(cp_molar_CH4, joule_per_mol_kelvin),
            self._S_H2O: ensure_units(cp_molar_H2O, joule_per_mol_kelvin),
        }
        self.MW = {
            self._S_CO2: ensure_units(mw_CO2, kilogram/mol),
            self._S_H2:  ensure_units(mw_H2,  kilogram/mol),
            self._S_CH4: ensure_units(mw_CH4, kilogram/mol),
            self._S_H2O: ensure_units(mw_H2O, kilogram/mol),
        }

        self.A = Q_(math.pi * (self.tube_diameter.magnitude ** 2) / 4.0, meter**2)
        self.length = (self.reactor_volume / self.A).to(meter)
        self.perimeter = Q_(math.pi * self.tube_diameter.magnitude, meter)
        self.UPw = (self.U_overall * self.perimeter)

        self.last_profile = None
        self.last_rate = Q_(0.0, reaction_rate_unit)
        self.last_inlet_flows = {s: Q_(0.0, mol_per_second) for s in [self._S_CO2, self._S_H2, self._S_CH4, self._S_H2O]}
        self.last_outlet_flows = {s: Q_(0.0, mol_per_second) for s in [self._S_CO2, self._S_H2, self._S_CH4, self._S_H2O]}
        self._last_solver_info = {}

    def rate_constant_arrhenius(self, T):
        T = ensure_units(T, kelvin)
        Ea = self.activation_energy
        R  = self.R
        exponent = -(Ea / (R * T)).to_base_units().magnitude
        return self.pre_exponential * np.exp(exponent)

    def _volumetric_flow(self, F, T, P):
        n_dot = sum(F)
        Vdot = (self.R * T / P).to(cubic_meter_per_second / (mol/second)).magnitude * n_dot
        return Q_(Vdot, cubic_meter_per_second)

    def _concentrations(self, F, T, P):
        Vdot = self._volumetric_flow(F, T, P)
        Vdot_mag = max(1e-30, Vdot.to(cubic_meter_per_second).magnitude)
        return np.array([F_i / Vdot_mag for F_i in F])

    def _rhs(self, z, y):
        F_CO2, F_H2, F_CH4, F_H2O = y
        F_CO2 = max(F_CO2, 0.0); F_H2 = max(F_H2, 0.0); F_CH4 = max(F_CH4, 0.0); F_H2O = max(F_H2O, 0.0)
        F = np.array([F_CO2, F_H2, F_CH4, F_H2O], dtype=float)

        T0 = self.temperature.to(kelvin).magnitude
        P0 = self.inlet_pressure.to(pascal).magnitude

        c = self._concentrations(F, Q_(T0, kelvin), Q_(P0, pascal))
        a, b = self.orders
        kT = strip_units(self.rate_constant_arrhenius(Q_(T0, kelvin)))
        r_vol = kT * (c[0]**a) * (c[1]**b)

        A_cs = self.A.to(meter**2).magnitude
        dF_CO2 = - r_vol * A_cs
        dF_H2  = - 4.0 * r_vol * A_cs
        dF_CH4 = + r_vol * A_cs
        dF_H2O = + 2.0 * r_vol * A_cs
        return np.array([dF_CO2, dF_H2, dF_CH4, dF_H2O], dtype=float)

    def simulate_pfr(self, inlet_flows):
        F0 = np.array([
            strip_units(inlet_flows.get(self._S_CO2, Q_(0.0, mol_per_second))),
            strip_units(inlet_flows.get(self._S_H2,  Q_(0.0, mol_per_second))),
            strip_units(inlet_flows.get(self._S_CH4, Q_(0.0, mol_per_second))),
            strip_units(inlet_flows.get(self._S_H2O, Q_(0.0, mol_per_second))),
        ], dtype=float)

        T0 = self.temperature.to(kelvin).magnitude
        P0 = self.inlet_pressure.to(pascal).magnitude
        y0 = np.array([F0[0], F0[1], F0[2], F0[3]], dtype=float)

        z_span = (0.0, self.length.to(meter).magnitude)

        if y0[0] <= 0.0 or y0[1] <= 0.0:
            self.last_rate = Q_(0.0, reaction_rate_unit)
            self.last_profile = None
            self.last_inlet_flows = {
                self._S_CO2: Q_(F0[0], mol_per_second),
                self._S_H2:  Q_(F0[1], mol_per_second),
                self._S_CH4: Q_(F0[2], mol_per_second),
                self._S_H2O: Q_(F0[3], mol_per_second),
            }
            self.last_outlet_flows = self.last_inlet_flows.copy()
            return self.last_outlet_flows

        def depletion_event(z, y):
            F_CO2, F_H2, _, _ = y
            return min(F_CO2, F_H2/4.0)
        depletion_event.terminal = True
        depletion_event.direction = -1

        sol = solve_ivp(
            fun=self._rhs,
            t_span=z_span,
            y0=y0,
            method="BDF",
            rtol=1e-6,
            atol=1e-9,
            events=depletion_event,
            max_step=(z_span[1] / 200.0 if z_span[1] > 0 else None)
        )

        self._last_solver_info = {
            "success": sol.success,
            "status": sol.status,
            "message": sol.message,
            "nfev": sol.nfev,
            "njev": getattr(sol, "njev", None),
            "nlu": getattr(sol, "nlu", None),
        }

        if not sol.success:
            logger.warning(f"PFR (isothermal) integration: {sol.message}")
        y_end = sol.y[:, -1]

        try:
            z_pts = np.linspace(z_span[0], sol.t[-1], 150)
            Y = sol.sol(z_pts) if sol.sol is not None else np.vstack([
                np.interp(z_pts, sol.t, sol.y[i, :]) for i in range(sol.y.shape[0])
            ])
            rate_prof = []
            for i in range(Y.shape[1]):
                F = Y[0:4, i]
                c = self._concentrations(F, Q_(T0, kelvin), Q_(P0, pascal))
                a, b = self.orders
                kT = strip_units(self.rate_constant_arrhenius(Q_(T0, kelvin)))
                rate_prof.append(kT * (c[0]**a) * (c[1]**b))
            rate_prof = np.asarray(rate_prof)

            self.last_profile = {
                "z": z_pts,
                "F_profile": Y[0:4, :],
                "T_profile": np.full_like(z_pts, T0),
                "P_profile": np.full_like(z_pts, P0),
                "rate_profile": rate_prof,
            }
            mid_idx = len(z_pts)//2
            self.last_rate = Q_(rate_prof[mid_idx], reaction_rate_unit)
        except Exception:
            self.last_profile = None
            self.last_rate = Q_(0.0, reaction_rate_unit)

        F_out = y_end[0:4]
        self.last_inlet_flows = {
            self._S_CO2: Q_(F0[0], mol_per_second),
            self._S_H2:  Q_(F0[1], mol_per_second),
            self._S_CH4: Q_(F0[2], mol_per_second),
            self._S_H2O: Q_(F0[3], mol_per_second),
        }
        self.last_outlet_flows = {
            self._S_CO2: Q_(max(0.0, F_out[0]), mol_per_second),
            self._S_H2:  Q_(max(0.0, F_out[1]), mol_per_second),
            self._S_CH4: Q_(max(0.0, F_out[2]), mol_per_second),
            self._S_H2O: Q_(max(0.0, F_out[3]), mol_per_second),
        }
        return self.last_outlet_flows

    def get_axial_profiles(self, num_points=150):
        if not self.last_profile:
            return None
        z = self.last_profile["z"]
        def _resample(x):
            return np.interp(np.linspace(z[0], z[-1], num_points), z, x)
        prof = {
            "z_fraction": np.linspace(0.0, 1.0, num_points),
            "F_CO2": _resample(self.last_profile["F_profile"][0]),
            "F_H2":  _resample(self.last_profile["F_profile"][1]),
            "F_CH4": _resample(self.last_profile["F_profile"][2]),
            "F_H2O": _resample(self.last_profile["F_profile"][3]),
            "T":     _resample(self.last_profile["T_profile"]),
            "P":     _resample(self.last_profile["P_profile"]),
            "rate":  _resample(self.last_profile["rate_profile"]),
        }
        F0_CO2 = max(1e-30, self.last_inlet_flows[self._S_CO2].to(mol_per_second).magnitude)
        prof["conversion_CO2"] = np.clip((F0_CO2 - prof["F_CO2"]) / F0_CO2, 0.0, 1.0)
        # Ensure JSON-serializable (lists of floats)
        for key in ["z_fraction", "F_CO2", "F_H2", "F_CH4", "F_H2O", "T", "P", "rate", "conversion_CO2"]:
            arr = np.asarray(prof[key], dtype=float)
            prof[key] = arr.tolist()
        return prof

    def tick(self, time_seconds):
        dt = ensure_units(time_seconds, second)
        if dt <= Q_(0, second):
            return

        n_CO2 = self.resource_bus.get_resource(self._S_CO2)
        n_H2  = self.resource_bus.get_resource(self._S_H2)
        n_CH4 = self.resource_bus.get_resource(self._S_CH4)
        n_H2O = self.resource_bus.get_resource(self._S_H2O)

        if n_CO2 <= Q_(0, mol) or n_H2 <= Q_(0, mol):
            self.time_elapsed += dt
            return

        T_in = self.temperature
        P_in = self.inlet_pressure
        c_tot_in = (P_in / (self.R * T_in)).to(mol/cubic_meter)
        n_dot_max = (c_tot_in * self.volumetric_flow_rate_in).to(mol/second)
        F_CO2_in = min(n_dot_max / 5.0, n_CO2 / dt, n_H2 / (4.0*dt))
        F_H2_in  = 4.0 * F_CO2_in

        inlet = {
            self._S_CO2: F_CO2_in,
            self._S_H2:  F_H2_in,
            self._S_CH4: Q_(0.0, mol_per_second),
            self._S_H2O: Q_(0.0, mol_per_second),
        }

        outlet = self.simulate_pfr(inlet)

        d_CO2 = (inlet[self._S_CO2] - outlet[self._S_CO2]) * dt
        d_H2  = (inlet[self._S_H2]  - outlet[self._S_H2])  * dt
        d_CH4 = outlet[self._S_CH4] * dt
        d_H2O = outlet[self._S_H2O] * dt

        d_CO2 = max(d_CO2, Q_(0.0, mol))
        d_H2  = max(d_H2,  Q_(0.0, mol))

        self.resource_bus.consume_resource(self._S_CO2, d_CO2)
        self.resource_bus.consume_resource(self._S_H2,  d_H2)
        self.resource_bus.set_resource(self._S_CH4, n_CH4 + d_CH4)
        self.resource_bus.set_resource(self._S_H2O, n_H2O + d_H2O)

        self.total_consumed["CO2"] += d_CO2
        self.total_consumed["H2"]  += d_H2
        self.total_produced["CH4"] += d_CH4
        self.total_produced["H2O"] += d_H2O

        self.time_elapsed += dt

    def rate_function(self, t):
        return self.rate_constant_arrhenius(self.temperature)

    def status(self):
        base = super().status()
        base.update({
            "reactor_type": "PFR-Isothermal",
            "length": self.length,
            "area": self.A,
            "tube_diameter": self.tube_diameter,
            "void_fraction": self.void_fraction,
            "particle_diameter": self.particle_diameter,
            "overall_heat_transfer_coefficient": self.UPw,
            "inlet_temperature": self.temperature,
            "inlet_pressure": self.inlet_pressure,
            "inlet_volumetric_flow": self.volumetric_flow_rate_in,
            "arrhenius_pre_exponential": self.pre_exponential,
            "arrhenius_activation_energy": self.activation_energy,
            "orders": self.orders,
            "heat_of_reaction": self.delta_Hr,
            "current_reaction_rate_midbed": self.last_rate,
            "inlet_flow_CO2": self.last_inlet_flows[self._S_CO2],
            "inlet_flow_H2":  self.last_inlet_flows[self._S_H2],
            "inlet_flow_CH4": self.last_inlet_flows[self._S_CH4],
            "inlet_flow_H2O": self.last_inlet_flows[self._S_H2O],
            "outlet_flow_CO2": self.last_outlet_flows[self._S_CO2],
            "outlet_flow_H2":  self.last_outlet_flows[self._S_H2],
            "outlet_flow_CH4": self.last_outlet_flows[self._S_CH4],
            "outlet_flow_H2O": self.last_outlet_flows[self._S_H2O],
            "solver_info": self._last_solver_info,
        })
        return base