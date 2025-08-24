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
        
        # Initialize moles if not present
        for species in [ResourceType.CO2, ResourceType.H2, ResourceType.CH4, ResourceType.H2O]:
            if species not in resource_bus.resources:
                logger.warning(f"{species.value} not found in resources. Initializing to 0.0 moles.")
                resource_bus.add_resource(species, Q_(0.0, mol))

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
            "moles_CO2": self.resource_bus.get_resource(ResourceType.CO2),
            "moles_H2": self.resource_bus.get_resource(ResourceType.H2), 
            "moles_CH4": self.resource_bus.get_resource(ResourceType.CH4),
            "moles_H2O": self.resource_bus.get_resource(ResourceType.H2O),
            "total_consumed_CO2": self.total_consumed["CO2"],
            "total_consumed_H2": self.total_consumed["H2"],
            "total_produced_CH4": self.total_produced["CH4"],
            "total_produced_H2O": self.total_produced["H2O"]
        }

class PFRMethanation(Methanation):
    """
    Plug Flow Reactor model for methanation using Arrhenius kinetics
    Models reactor as volume-based ODEs rather than simple time-based rates
    """
    
    def __init__(self, resource_bus, 
                 reactor_volume=Q_(1.0, cubic_meter), 
                 temperature=Q_(573, kelvin), 
                 pre_exponential=Q_(1e5, pre_exponential_units), 
                 activation_energy=Q_(80000, joule_per_mol), 
                 volumetric_flow_rate=Q_(0.01, cubic_meter_per_second)):
        """
        Initialize PFR methanation reactor
        
        Args:
            reactor_volume: Total reactor volume (m³)
            temperature: Operating temperature (K)
            pre_exponential: Pre-exponential factor A in rate equation (1/s)
            activation_energy: Activation energy Ea (J/mol)
            volumetric_flow_rate: Volumetric flow rate v0 (m³/s)
        """
        # Initialize parent with dummy values since we override the rate function
        super().__init__(resource_bus, rate_constant=Q_(0.0, mol_per_second))
        
        # PFR-specific parameters with units
        self.reactor_volume = ensure_units(reactor_volume, cubic_meter)
        self.temperature = ensure_units(temperature, kelvin)
        self.pre_exponential = ensure_units(pre_exponential, pre_exponential_units)
        self.activation_energy = ensure_units(activation_energy, joule_per_mol)
        self.volumetric_flow_rate = ensure_units(volumetric_flow_rate, cubic_meter_per_second)
        self.last_rate = Q_(0.0, reaction_rate_unit)
        
        # Use the constant from units module
        self.R = R_GAS_CONSTANT
        
    def rate_constant_arrhenius(self):
        """Calculate rate constant using Arrhenius equation"""
        # Convert to base units for numpy exp operation
        Ea = self.activation_energy.to(joule_per_mol)
        R = self.R.to(joule_per_mol / kelvin)
        T = self.temperature.to(kelvin)
        
        exponent = -(Ea / (R * T)).magnitude
        return self.pre_exponential * np.exp(exponent)
    
    def pfr_odes(self, V, F):
        """
        ODEs for PFR: dF/dV = rate equations
        
        Args:
            V (float): Reactor volume coordinate (m³) - dimensionless for solver
            F (array): Molar flow rates [F_CO2, F_H2, F_CH4, F_H2O] (mol/s) - dimensionless for solver
            
        Returns:
            array: Derivatives dF/dV (mol/s/m³) - dimensionless for solver
        """
        F_CO2, F_H2, F_CH4, F_H2O = F
        
        # Convert flow rates to concentrations (mol/m³)
        # Note: Using ideal gas law PV = nRT => c = P/(RT) = F/(v0*RT) for flow
        denominator = (self.volumetric_flow_rate * self.R * self.temperature).to_base_units().magnitude
        c_CO2 = max(0, F_CO2 / denominator)
        c_H2 = max(0, F_H2 / denominator)
        
        # Rate equation: r = k * [CO2] * [H2]^4
        k_magnitude = strip_units(self.rate_constant_arrhenius())
        rate = k_magnitude * c_CO2 * c_H2**4
        
        # Stoichiometry: CO2 + 4H2 → CH4 + 2H2O
        return np.array([-rate, -4*rate, rate, 2*rate])
    
    def simulate_pfr(self, inlet_flows):
        """
        Simulate PFR for given inlet flows
        
        Args:
            inlet_flows (dict): Inlet molar flow rates {ResourceType: pint Quantity}
            
        Returns:
            dict: Outlet molar flow rates {ResourceType: pint Quantity}
        """
        # Convert to array format for ODE solver (extract magnitudes)
        F0 = np.array([
            strip_units(inlet_flows.get(ResourceType.CO2, Q_(0.0, mol_per_second))),
            strip_units(inlet_flows.get(ResourceType.H2, Q_(0.0, mol_per_second))), 
            strip_units(inlet_flows.get(ResourceType.CH4, Q_(0.0, mol_per_second))),
            strip_units(inlet_flows.get(ResourceType.H2O, Q_(0.0, mol_per_second)))
        ])
        
        # Check if we have reactants
        if F0[0] <= 0 or F0[1] <= 0:
            return {
                ResourceType.CO2: Q_(F0[0], mol_per_second),
                ResourceType.H2: Q_(F0[1], mol_per_second),
                ResourceType.CH4: Q_(F0[2], mol_per_second),
                ResourceType.H2O: Q_(F0[3], mol_per_second)
            }
        
        # Solve PFR ODEs from V=0 to V=reactor_volume
        V_span = (0, strip_units(self.reactor_volume))
        
        try:
            sol = solve_ivp(self.pfr_odes, V_span, F0, dense_output=True, rtol=1e-6)
            
            if sol.success:
                V_mid = self.reactor_volume.to(cubic_meter).magnitude / 2
                F_mid = sol.sol(V_mid)
                self.last_rate = Q_(self._calculate_rate(F_mid), reaction_rate_unit)
                F_outlet = sol.y[:, -1]
            else:
                logger.warning("PFR integration failed, using inlet conditions")
                F_outlet = F0
                self.last_rate = Q_(0.0, reaction_rate_unit)
                
        except Exception as e:
            logger.warning(f"PFR simulation error: {e}, using inlet conditions")
            F_outlet = F0
            self.last_rate = Q_(0.0, reaction_rate_unit)
        
        return {
            ResourceType.CO2: Q_(max(0, F_outlet[0]), mol_per_second),
            ResourceType.H2: Q_(max(0, F_outlet[1]), mol_per_second), 
            ResourceType.CH4: Q_(max(0, F_outlet[2]), mol_per_second),
            ResourceType.H2O: Q_(max(0, F_outlet[3]), mol_per_second)
        }
        
    def _calculate_rate(self, F):
        F_CO2, F_H2, F_CH4, F_H2O = F
        denominator = (self.volumetric_flow_rate * self.R * self.temperature).to_base_units().magnitude
        c_CO2 = max(0, F_CO2 / denominator)
        c_H2 = max(0, F_H2 / denominator)
        k = strip_units(self.rate_constant_arrhenius())
        return k * c_CO2 * c_H2**4
    
    def tick(self, time_seconds):
        """
        Update reactor for one time step using PFR model
        
        Args:
            time_seconds: Time step duration (s)
        """
        dt = ensure_units(time_seconds, second)
        
        # Get available reactants (mol)
        co2_available = self.resource_bus.get_resource(ResourceType.CO2)
        h2_available = self.resource_bus.get_resource(ResourceType.H2)
        ch4_current = self.resource_bus.get_resource(ResourceType.CH4)
        h2o_current = self.resource_bus.get_resource(ResourceType.H2O)
        
        if co2_available <= Q_(0, mol) or h2_available <= Q_(0, mol):
            self.time_elapsed += dt
            return
            
        # Convert available moles to flow rates (mol/s)
        # Assume we can process all available reactants in this timestep
        inlet_flows = {
            ResourceType.CO2: co2_available / dt,
            ResourceType.H2: h2_available / dt,
            ResourceType.CH4: Q_(0.0, mol_per_second),  # No CH4 inlet
            ResourceType.H2O: Q_(0.0, mol_per_second)   # No H2O inlet
        }
        
        # Simulate PFR
        outlet_flows = self.simulate_pfr(inlet_flows)
        
        # Convert back to moles processed in this timestep
        co2_outlet = outlet_flows[ResourceType.CO2] * dt
        h2_outlet = outlet_flows[ResourceType.H2] * dt
        ch4_produced = outlet_flows[ResourceType.CH4] * dt
        h2o_produced = outlet_flows[ResourceType.H2O] * dt
        
        # Calculate consumption
        co2_consumed = co2_available - co2_outlet
        h2_consumed = h2_available - h2_outlet
        
        # Update resource bus
        self.resource_bus.set_resource(ResourceType.CO2, co2_outlet)
        self.resource_bus.set_resource(ResourceType.H2, h2_outlet) 
        self.resource_bus.set_resource(ResourceType.CH4, ch4_current + ch4_produced)
        self.resource_bus.set_resource(ResourceType.H2O, h2o_current + h2o_produced)
        
        # Update totals
        self.total_consumed["CO2"] += co2_consumed
        self.total_consumed["H2"] += h2_consumed
        self.total_produced["CH4"] += ch4_produced
        self.total_produced["H2O"] += h2o_produced
        
        self.time_elapsed += dt
    
    def rate_function(self, t):
        """Override parent rate function - not used in PFR model"""
        return self.rate_constant_arrhenius()
    
    def status(self):
        """Get reactor status including PFR-specific parameters"""
        base_status = super().status()
        # Calculate inlet flows for status
        co2_inlet_flow = self.resource_bus.get_resource(ResourceType.CO2) / self.time_elapsed if self.time_elapsed > Q_(0, second) else Q_(0, mol_per_second)
        h2_inlet_flow = self.resource_bus.get_resource(ResourceType.H2) / self.time_elapsed if self.time_elapsed > Q_(0, second) else Q_(0, mol_per_second)
        
        base_status.update({
            "reactor_type": "PFR",
            "reactor_volume": self.reactor_volume,
            "temperature": self.temperature,
            "activation_energy": self.activation_energy,
            "pre_exponential": self.pre_exponential,
            "volumetric_flow_rate": self.volumetric_flow_rate,
            "arrhenius_rate_constant": self.rate_constant_arrhenius(),
            "current_reaction_rate": self.last_rate,
            "inlet_flow_CO2": co2_inlet_flow,
            "inlet_flow_H2": h2_inlet_flow
        })
        return base_status


class AdvancedPFRMethanation(PFRMethanation):
    """
    Advanced PFR model with energy balance, pressure drop, and reversible reaction
    
    Includes:
    - Energy balance with heat of reaction and heat loss
    - Pressure drop via Ergun equation  
    - Reversible Sabatier reaction kinetics
    - Temperature and pressure dependent concentrations
    """
    
    def __init__(self, resource_bus,
                 reactor_volume=Q_(1.0, cubic_meter),
                 inlet_temperature=Q_(573, kelvin),
                 inlet_pressure=Q_(101325, pascal),
                 pre_exponential_forward=Q_(1e5, pre_exponential_units),
                 pre_exponential_reverse=Q_(1e3, pre_exponential_units), 
                 activation_energy_forward=Q_(80000, joule_per_mol),
                 activation_energy_reverse=Q_(90000, joule_per_mol),
                 volumetric_flow_rate=Q_(0.01, cubic_meter_per_second),
                 heat_of_reaction=Q_(-165000, joule_per_mol),  # Exothermic
                 heat_capacity=Q_(35.0, joule_per_mol_kelvin),  # Average Cp
                 heat_loss_coefficient=Q_(100.0, joule / (cubic_meter * second * kelvin)),
                 ambient_temperature=Q_(298, kelvin),
                 porosity=0.4,  # Dimensionless
                 particle_diameter=Q_(0.003, meter),  # 3mm particles
                 gas_viscosity=Q_(2e-5, pascal * second),
                 gas_density=Q_(0.5, kilogram / cubic_meter)):
        """
        Initialize advanced PFR with energy balance and pressure drop
        
        Args:
            heat_of_reaction: Enthalpy of reaction (J/mol CO2) - negative for exothermic
            heat_capacity: Average molar heat capacity of gas mixture (J/mol·K)
            heat_loss_coefficient: Heat loss to surroundings (J/m³·s·K)
            ambient_temperature: Surrounding temperature for heat loss (K)
            porosity: Bed porosity (dimensionless)
            particle_diameter: Catalyst particle diameter (m)
            gas_viscosity: Gas dynamic viscosity (Pa·s)
            gas_density: Gas density (kg/m³)
        """
        # Initialize parent PFR
        super().__init__(resource_bus, reactor_volume, inlet_temperature, 
                        pre_exponential_forward, activation_energy_forward, volumetric_flow_rate)
        
        # Energy balance parameters
        self.inlet_temperature = ensure_units(inlet_temperature, kelvin)
        self.inlet_pressure = ensure_units(inlet_pressure, pascal)
        self.heat_of_reaction = ensure_units(heat_of_reaction, joule_per_mol)
        self.heat_capacity = ensure_units(heat_capacity, joule_per_mol_kelvin)
        self.heat_loss_coefficient = ensure_units(heat_loss_coefficient, joule / (cubic_meter * second * kelvin))
        self.ambient_temperature = ensure_units(ambient_temperature, kelvin)
        
        # Reversible kinetics
        self.pre_exponential_forward = ensure_units(pre_exponential_forward, pre_exponential_units)
        self.pre_exponential_reverse = ensure_units(pre_exponential_reverse, pre_exponential_units)
        self.activation_energy_forward = ensure_units(activation_energy_forward, joule_per_mol)
        self.activation_energy_reverse = ensure_units(activation_energy_reverse, joule_per_mol)
        
        # Pressure drop parameters
        self.porosity = porosity  # Dimensionless
        self.particle_diameter = ensure_units(particle_diameter, meter)
        self.gas_viscosity = ensure_units(gas_viscosity, pascal * second)
        self.gas_density = ensure_units(gas_density, kilogram / cubic_meter)
        
        # State tracking
        self.temperature_profile = []
        self.pressure_profile = []
        
    def equilibrium_constant(self, temperature):
        """
        Calculate equilibrium constant for Sabatier reaction at given temperature
        Using simplified correlation: K_eq = exp(A - B/T)
        """
        # Simplified correlation for CO2 + 4H2 ⇌ CH4 + 2H2O
        # These are approximate values for demonstration
        A = 15.0  # Dimensionless
        B = 15000  # K
        
        T_magnitude = strip_units(temperature.to(kelvin))
        return np.exp(A - B/T_magnitude)
        
    def rate_constants_arrhenius(self, temperature):
        """Calculate forward and reverse rate constants at given temperature"""
        T = temperature.to(kelvin)
        R = self.R.to(joule_per_mol_kelvin)
        
        # Forward rate constant
        exp_forward = -(self.activation_energy_forward / (R * T)).magnitude
        k_forward = self.pre_exponential_forward * np.exp(exp_forward)
        
        # Reverse rate constant  
        exp_reverse = -(self.activation_energy_reverse / (R * T)).magnitude
        k_reverse = self.pre_exponential_reverse * np.exp(exp_reverse)
        
        return k_forward, k_reverse
        
    def concentration_from_flow(self, flow_rate, temperature, pressure):
        """Calculate concentration from molar flow rate using ideal gas law"""
        # c = F*P/(v0*R*T) where v0 is volumetric flow rate
        denominator = (self.volumetric_flow_rate * self.R * temperature).to_base_units().magnitude
        P_magnitude = strip_units(pressure.to(pascal))
        F_magnitude = strip_units(flow_rate.to(mol_per_second))
        
        # Pressure correction factor
        P_correction = P_magnitude / strip_units(self.inlet_pressure.to(pascal))
        
        return max(0, F_magnitude * P_correction / denominator)
        
    def ergun_pressure_drop(self, velocity, position):
        """
        Calculate pressure drop using Ergun equation
        dP/dz = -(150*(1-ε)²*μ*v)/(ε³*dp²) - (1.75*(1-ε)*ρ*v²)/(ε³*dp)
        
        Args:
            velocity: Superficial velocity (m/s)
            position: Axial position (m) 
            
        Returns:
            dP/dz in Pa/m
        """
        eps = self.porosity
        dp = strip_units(self.particle_diameter.to(meter))
        mu = strip_units(self.gas_viscosity.to(pascal * second))
        rho = strip_units(self.gas_density.to(kilogram / cubic_meter))
        v = strip_units(velocity)
        
        # Ergun equation terms
        viscous_term = 150 * (1 - eps)**2 * mu * v / (eps**3 * dp**2)
        inertial_term = 1.75 * (1 - eps) * rho * v**2 / (eps**3 * dp)
        
        return -(viscous_term + inertial_term)  # Pa/m
        
    def advanced_pfr_odes(self, z, y):
        """
        Advanced ODE system including energy balance and pressure drop
        
        Args:
            z: Axial position (m) - dimensionless for solver
            y: State vector [F_CO2, F_H2, F_CH4, F_H2O, T, P] - dimensionless for solver
            
        Returns:
            dydt: Derivatives [dF/dz, dT/dz, dP/dz] - dimensionless for solver
        """
        F_CO2, F_H2, F_CH4, F_H2O, T, P = y
        
        # Convert to quantities with units (restore units for calculations)
        temperature = Q_(T, kelvin)
        pressure = Q_(P, pascal)
        F_total = F_CO2 + F_H2 + F_CH4 + F_H2O
        
        # Calculate concentrations using temperature and pressure
        c_CO2 = self.concentration_from_flow(Q_(F_CO2, mol_per_second), temperature, pressure)
        c_H2 = self.concentration_from_flow(Q_(F_H2, mol_per_second), temperature, pressure)
        c_CH4 = self.concentration_from_flow(Q_(F_CH4, mol_per_second), temperature, pressure)
        c_H2O = self.concentration_from_flow(Q_(F_H2O, mol_per_second), temperature, pressure)
        
        # Get rate constants
        k_forward, k_reverse = self.rate_constants_arrhenius(temperature)
        k_f = strip_units(k_forward)
        k_r = strip_units(k_reverse)
        
        # Forward and reverse reaction rates
        # Forward: CO2 + 4H2 → CH4 + 2H2O,  rate = k_f * [CO2] * [H2]^4
        # Reverse: CH4 + 2H2O → CO2 + 4H2,  rate = k_r * [CH4] * [H2O]^2
        r_forward = k_f * c_CO2 * c_H2**4
        r_reverse = k_r * c_CH4 * c_H2O**2
        
        # Net reaction rate (mol/m³/s)
        r_net = r_forward - r_reverse
        
        # Flow rate derivatives (mol/s/m)
        dF_CO2_dz = -r_net
        dF_H2_dz = -4 * r_net  
        dF_CH4_dz = r_net
        dF_H2O_dz = 2 * r_net
        
        # Energy balance: dT/dz = (-ΔHr * r + Q_loss) / (n_total * Cp)
        delta_Hr = strip_units(self.heat_of_reaction.to(joule_per_mol))  # J/mol
        Q_loss_coeff = strip_units(self.heat_loss_coefficient.to(joule / (cubic_meter * second * kelvin)))
        Q_loss = Q_loss_coeff * (T - strip_units(self.ambient_temperature.to(kelvin)))  # J/m³/s
        Cp = strip_units(self.heat_capacity.to(joule_per_mol_kelvin))  # J/mol/K
        
        if F_total > 1e-10:  # Avoid division by zero
            # Convert reactor volume to length for per-unit-length calculations
            reactor_length = strip_units(self.reactor_volume.to(cubic_meter)) ** (1/3)  # Approximate
            cross_sectional_area = strip_units(self.reactor_volume.to(cubic_meter)) / reactor_length
            
            dT_dz = (-delta_Hr * r_net * cross_sectional_area - Q_loss * cross_sectional_area) / (F_total * Cp)
        else:
            dT_dz = 0
        
        # Pressure drop: dP/dz using Ergun equation
        if F_total > 1e-10:
            # Calculate superficial velocity
            volumetric_flow = strip_units(self.volumetric_flow_rate.to(cubic_meter_per_second))
            # Approximate cross-sectional area
            cross_area = strip_units(self.reactor_volume.to(cubic_meter)) ** (2/3)  # Approximate
            velocity = volumetric_flow / cross_area  # m/s
            
            dP_dz = self.ergun_pressure_drop(Q_(velocity, meter/second), z)
        else:
            dP_dz = 0
        
        return np.array([dF_CO2_dz, dF_H2_dz, dF_CH4_dz, dF_H2O_dz, dT_dz, dP_dz])
        
    def simulate_advanced_pfr(self, inlet_flows):
        """
        Simulate advanced PFR with energy balance and pressure drop
        
        Args:
            inlet_flows (dict): Inlet molar flow rates {ResourceType: pint Quantity}
            
        Returns:
            dict: Outlet conditions {flows, temperature, pressure}
        """
        # Convert to array format (extract magnitudes)
        F0 = np.array([
            strip_units(inlet_flows.get(ResourceType.CO2, Q_(0.0, mol_per_second))),
            strip_units(inlet_flows.get(ResourceType.H2, Q_(0.0, mol_per_second))),
            strip_units(inlet_flows.get(ResourceType.CH4, Q_(0.0, mol_per_second))),
            strip_units(inlet_flows.get(ResourceType.H2O, Q_(0.0, mol_per_second)))
        ])
        
        # Initial conditions: [F_CO2, F_H2, F_CH4, F_H2O, T, P]
        T0 = strip_units(self.inlet_temperature.to(kelvin))
        P0 = strip_units(self.inlet_pressure.to(pascal))
        y0 = np.concatenate([F0, [T0, P0]])
        
        # Check if we have reactants
        if F0[0] <= 0 or F0[1] <= 0:
            return {
                'flows': {
                    ResourceType.CO2: Q_(F0[0], mol_per_second),
                    ResourceType.H2: Q_(F0[1], mol_per_second),
                    ResourceType.CH4: Q_(F0[2], mol_per_second),
                    ResourceType.H2O: Q_(F0[3], mol_per_second)
                },
                'temperature': self.inlet_temperature,
                'pressure': self.inlet_pressure
            }
        
        # Reactor length (approximate from volume)
        reactor_length = strip_units(self.reactor_volume.to(cubic_meter)) ** (1/3)
        z_span = (0, reactor_length)
        
        try:
            sol = solve_ivp(self.advanced_pfr_odes, z_span, y0, dense_output=True, rtol=1e-6)
            
            if sol.success:
                # Extract final conditions
                y_final = sol.y[:, -1]
                F_outlet = y_final[:4]
                T_outlet = y_final[4]
                P_outlet = y_final[5]
                
                # Store profiles for analysis
                z_points = np.linspace(0, reactor_length, 100)
                y_profile = sol.sol(z_points)
                self.temperature_profile = [Q_(T, kelvin) for T in y_profile[4, :]]
                self.pressure_profile = [Q_(P, pascal) for P in y_profile[5, :]]
                
                # Calculate reaction rate at outlet for tracking
                outlet_temp = Q_(T_outlet, kelvin)
                outlet_press = Q_(P_outlet, pascal)
                c_CO2_out = self.concentration_from_flow(Q_(F_outlet[0], mol_per_second), outlet_temp, outlet_press)
                c_H2_out = self.concentration_from_flow(Q_(F_outlet[1], mol_per_second), outlet_temp, outlet_press)
                k_f, k_r = self.rate_constants_arrhenius(outlet_temp)
                self.last_rate = Q_(strip_units(k_f) * c_CO2_out * c_H2_out**4, reaction_rate_unit)
                
                return {
                    'flows': {
                        ResourceType.CO2: Q_(max(0, F_outlet[0]), mol_per_second),
                        ResourceType.H2: Q_(max(0, F_outlet[1]), mol_per_second),
                        ResourceType.CH4: Q_(max(0, F_outlet[2]), mol_per_second),
                        ResourceType.H2O: Q_(max(0, F_outlet[3]), mol_per_second)
                    },
                    'temperature': Q_(T_outlet, kelvin),
                    'pressure': Q_(P_outlet, pascal)
                }
            else:
                logger.warning("Advanced PFR integration failed, using inlet conditions")
                return {
                    'flows': {
                        ResourceType.CO2: Q_(F0[0], mol_per_second),
                        ResourceType.H2: Q_(F0[1], mol_per_second),
                        ResourceType.CH4: Q_(F0[2], mol_per_second),
                        ResourceType.H2O: Q_(F0[3], mol_per_second)
                    },
                    'temperature': self.inlet_temperature,
                    'pressure': self.inlet_pressure
                }
                
        except Exception as e:
            logger.warning(f"Advanced PFR simulation error: {e}, using inlet conditions")
            return {
                'flows': {
                    ResourceType.CO2: Q_(F0[0], mol_per_second),
                    ResourceType.H2: Q_(F0[1], mol_per_second),
                    ResourceType.CH4: Q_(F0[2], mol_per_second),
                    ResourceType.H2O: Q_(F0[3], mol_per_second)
                },
                'temperature': self.inlet_temperature,
                'pressure': self.inlet_pressure
            }
    
    def tick(self, time_seconds):
        """
        Update reactor for one time step using advanced PFR model
        
        Args:
            time_seconds: Time step duration (s)
        """
        dt = ensure_units(time_seconds, second)
        
        # Get available reactants (mol)
        co2_available = self.resource_bus.get_resource(ResourceType.CO2)
        h2_available = self.resource_bus.get_resource(ResourceType.H2)
        ch4_current = self.resource_bus.get_resource(ResourceType.CH4)
        h2o_current = self.resource_bus.get_resource(ResourceType.H2O)
        
        if co2_available <= Q_(0, mol) or h2_available <= Q_(0, mol):
            self.time_elapsed += dt
            return
            
        # Convert available moles to flow rates (mol/s)
        inlet_flows = {
            ResourceType.CO2: co2_available / dt,
            ResourceType.H2: h2_available / dt,
            ResourceType.CH4: Q_(0.0, mol_per_second),
            ResourceType.H2O: Q_(0.0, mol_per_second)
        }
        
        # Simulate advanced PFR
        outlet_conditions = self.simulate_advanced_pfr(inlet_flows)
        outlet_flows = outlet_conditions['flows']
        self.outlet_temperature = outlet_conditions['temperature']
        self.outlet_pressure = outlet_conditions['pressure']
        
        # Convert back to moles processed in this timestep
        co2_outlet = outlet_flows[ResourceType.CO2] * dt
        h2_outlet = outlet_flows[ResourceType.H2] * dt
        ch4_produced = outlet_flows[ResourceType.CH4] * dt
        h2o_produced = outlet_flows[ResourceType.H2O] * dt
        
        # Calculate consumption
        co2_consumed = co2_available - co2_outlet
        h2_consumed = h2_available - h2_outlet
        
        # Update resource bus
        self.resource_bus.set_resource(ResourceType.CO2, co2_outlet)
        self.resource_bus.set_resource(ResourceType.H2, h2_outlet)
        self.resource_bus.set_resource(ResourceType.CH4, ch4_current + ch4_produced)
        self.resource_bus.set_resource(ResourceType.H2O, h2o_current + h2o_produced)
        
        # Update totals
        self.total_consumed["CO2"] += co2_consumed
        self.total_consumed["H2"] += h2_consumed
        self.total_produced["CH4"] += ch4_produced
        self.total_produced["H2O"] += h2o_produced
        
        self.time_elapsed += dt
    
    def status(self):
        """Get reactor status including advanced PFR parameters"""
        base_status = super().status()
        
        # Add advanced parameters
        base_status.update({
            "reactor_type": "Advanced PFR",
            "energy_balance": True,
            "pressure_drop": True,
            "reversible_kinetics": True,
            "inlet_temperature": self.inlet_temperature,
            "inlet_pressure": self.inlet_pressure,
            "outlet_temperature": getattr(self, 'outlet_temperature', self.inlet_temperature),
            "outlet_pressure": getattr(self, 'outlet_pressure', self.inlet_pressure),
            "heat_of_reaction": self.heat_of_reaction,
            "heat_capacity": self.heat_capacity,
            "porosity": self.porosity,
            "particle_diameter": self.particle_diameter,
            "gas_viscosity": self.gas_viscosity,
            "gas_density": self.gas_density,
            "equilibrium_constant": self.equilibrium_constant(getattr(self, 'outlet_temperature', self.inlet_temperature))
        })
        
        return base_status