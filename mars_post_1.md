Focus:
	•	End-to-end mission architecture: LEO depot → Mars surface → ISRU return
	•	Fleet size vs base buildup timeline
	•	Material throughput modeling
Include:
	•	Estimated tonnage needed for a large research base
	•	Starship cargo capacity and turnaround window
	•	Graphs showing fleet size vs years to operational base

## Introductory Narrative
Jim was excited for today, he'd been looking forward to the next series resupply landings since the station had run out of ketchup 4 months ago. The food was never great at Musk Manor, what the inhabitants of the officially titled International Martian Advanced Research Station or IMARS called their home, but ketchup was at least able to make the food feel more like food and less like rations. Soon enough the first of the fleet of over 300 resupply ships would begin landing and Jim would be able to get his hands on some sweet non-newtonian processed tomato product. 

Settling a sizeable scientific and engineering outpost on the Martian surface will require large amounts of equipment to be transferred from Earth. I think using an aircraft carrier as a mass per person analog is a good way to think about the problem. Aircraft carriers are large vessels that can carry a large number of people and equipment. They are also relatively self-sufficient for limited periods of time, with a large amount of fuel and food on board. The USS Gerald R. Ford (CVN-78) is a nuclear powered aircraft carrier that can carry a crew of 4,600 and has a displacement of 101,000 tons. This gives us a mass per crew member of 22 tons. Assuming we can replace the aircraft and ordnance with life support, ISRU, and scientific equipment we can use this as a baseline for the mass of the outpost. Using the collection of Antarctic research bases as a reference, we can estimate the crew of a large outpost capable of producing a meaningful amount of science to be 5,000 people. This gives us a total mass of 110,000 tons. 

With the payload in mind let's look at the fuel requirements. Though fuel may not be the primary cost driver it is of primary concern as a system mass driver and therefore exploring ways to reduce the fuel requirements could drive the costs down significantly. 

The architecture of our missions is that multiple tanker class starships will ferry fuel to an orbital depot in LEO these tanker launches can take place more or less around the clock since they just go to LEO and back (take accout for turnaround time as a parameter). (sim should track fleet size as a function of production rates (lead time and number of lines) for tankers and have param for fuel load to LEO for tankers)

Crew class ships will launch and refuel at the depot. sim should track fleet size as a function of production rates (lead time and number of lines) for crew ships and have params for people per ship. We can assume all available crew ships will be launched for each launch window.

Cargo class ships will launch and refuel at the depot. sim should track fleet size as a function of production rates (lead time and number of lines) for cargo ships and have params for mass of cargo per ship. We can assume all available cargo ships will be launched for each launch window.

The flotilla of crew and cargo ships will depart for Mars. The journey will take 250 days. The ships will land on the Martian surface and be refueled using fuel produced by ISRU plants. The ships will then have to wait for the next launch window to return to Earth. Sim should account for the time spent on Mars and the time spent in transit. 6-9 months there, wait for ~18 months, then 6-9 months back. Once the ships return they can be added to the fleet along with the newly produced ships. 

Each class of ship will have a mission life that should be accounted for in the sim.

Elon Musk has stated that the goal is to produce 1000 starships per year. Seeing as the speculated new build lead time for a Falcon 9 is 12-18 months, this seems a bit fantastical. However, Space X has been able to work miracles in the past and while the initial production rate is likely to be lower, it is possible that the production rate could be increased to 1000 starships per year over time. For my purposes I will assume an order of magnitude increase in production rate for starships over Falcon 9 ~1 a month. This is a very rough estimate and the actual production rate will likely be lower.

Sim visualizes
- fuel storage of LEO depot
- fleet size per class of ship
- people at mars
- cargo at mars

## Starship and Super Heavy

Super Heavy
Fuel tank capacity 
2700 t of LOX
700 t of CH4

Starship
52.1 m tall
9 m diameter
Dry mass: 100 t
1170 t of LOX11
330 t of CH4

System capacity
100-150 t to LEO
27 t to Geostationary Transfer Orbit (GTO)
Claim 100+ t to Moon or Mars

Space X Goal fleet size: 1,000–2,000 Starships

Mars Synodic Period: 780 days

## Fleet Size and Base Buildup Timeline
Assuming 100 people per crew ship, 100 tons per cargo ship, yearly production rate of 15, 35, and 50 crew, cargo, and tanker ships respectively, a tanker turnaround time of 7 days, a tanker fuel load of 100 tons, and a crew and cargo ship fuel need of 1500 tons and mission lifespans of 10, 10, and 20 missions respectively, the we can see that we will accrew a a fleet size of  

# Mars Transport Simulation Model

This model simulates a Mars transport architecture using periodic launch windows, tanker-fueled depots in LEO, and continuous production of ships. The system evolves in discrete daily timesteps.

---

## State Variables

Let \( t \in \mathbb{Z}_{\geq 0} \) represent time in days. The system state at day \( t \) includes:

- \( P(t) \): cumulative number of people delivered to Mars  
- \( C(t) \): cumulative cargo mass (tons) delivered to Mars  
- \( F(t) \): fuel in the LEO depot (tons)  
- \( S_{\text{crew}}(t) \): available crew ships at LEO  
- \( S_{\text{cargo}}(t) \): available cargo ships at LEO  
- \( S_{\text{tanker}}(t) \): available tankers at LEO  
- \( D_{\text{mars}}(t) \): cumulative Mars-side fuel demand (for return flights)

---

## Parameters

The simulation is driven by fixed parameters:

- \( n_p \): people per crew ship  
- \( m_c \): cargo mass (tons) per cargo ship  
- \( f_s \): fuel required per Mars mission (tons)  
- \( r_t \): fuel delivered per tanker flight (tons)  
- \( \tau_{\text{transit}} \): time from Earth to Mars (days)  
- \( \tau_{\text{wait}} \): Mars surface wait time (days)  
- \( \tau_{\text{mission}} = 2 \cdot \tau_{\text{transit}} + \tau_{\text{wait}} \): full round-trip time  
- \( \Delta \): interval between Mars launch windows (days)  
- \( \tau_{\text{turn}} \): minimum days between tanker flights  
- \( \tau_{\text{build}, i} \): build time for ship type \( i \in \{ \text{crew, cargo, tanker} \} \)  
- \( \lambda_i \): max ships of type \( i \) that can be under construction at once  
- \( L_i \): lifespan (missions) of ship type \( i \)

---

## Tanker Fuel Delivery

Each day, fuel delivered to the depot is:

$$
Q_f(t) = r_t \cdot N_t(t)
$$

where \( N_t(t) \) is the number of tankers ready to fly (idle for at least \( \tau_{\text{turn}} \) days).

The depot is updated as:

$$
F(t+1) = F(t) + Q_f(t) - F_{\text{used}}(t)
$$

---

## Launch Window Dynamics

Every \( \Delta \) days (i.e., when \( t \bmod \Delta = 0 \)), ships may be launched to Mars:

Define:

$$
S_{\text{total}}(t) = S_{\text{crew}}(t) + S_{\text{cargo}}(t)
$$

Max number of ships that can be fueled:

$$
L(t) = \left\lfloor \frac{F(t)}{f_s} \right\rfloor
$$

Let:

$$
\alpha = \frac{S_{\text{crew}}(t)}{S_{\text{total}}(t)} \quad \text{(crew fraction)}
$$

Then:

$$
A_{\text{crew}}(t) = \min \left( S_{\text{crew}}(t), \left\lfloor \alpha \cdot L(t) \right\rfloor \right)
$$

$$
A_{\text{cargo}}(t) = \min \left( S_{\text{cargo}}(t), L(t) - A_{\text{crew}}(t) \right)
$$

People and cargo delivered:

$$
P(t+1) = P(t) + A_{\text{crew}}(t) \cdot n_p
$$

$$
C(t+1) = C(t) + A_{\text{cargo}}(t) \cdot m_c
$$

Depot fuel usage:

$$
F_{\text{used}}(t) = f_s \cdot \left( A_{\text{crew}}(t) + A_{\text{cargo}}(t) \right)
$$

Return flights are scheduled at \( t + \tau_{\text{mission}} \). Each ship consumes additional return fuel, accounted for on Mars.

---

## Ship Construction

Shipyards produce new ships continuously if within capacity:

$$
S_i^{\text{build}}(t) = 
\begin{cases}
1 & \text{if current under construction for } i < \lambda_i \\
0 & \text{otherwise}
\end{cases}
$$

Completed ships enter the fleet at:

$$
t_{\text{complete}} = t + \tau_{\text{build}, i}
$$

---

## Mars-Side Fuel Demand

Fuel required for return journeys accumulates as ships arrive at Mars:

$$
D_{\text{mars}}(t+1) = D_{\text{mars}}(t) + f_s \cdot \left( A_{\text{crew}}^{\text{arrive}}(t) + A_{\text{cargo}}^{\text{arrive}}(t) \right)
$$

Arrival is scheduled at \( t + \tau_{\text{transit}} \) after launch.

---

## Full System Dynamics

The system is governed by:

$$
\bm{x}(t+1) = f(\bm{x}(t), \bm{u}(t), \bm{\theta})
$$

Where:

- \( \bm{x}(t) = [P(t), C(t), F(t), S_{\text{crew}}(t), S_{\text{cargo}}(t), S_{\text{tanker}}(t), D_{\text{mars}}(t)] \)
- \( \bm{u}(t) \): control inputs (e.g., build decisions, tanker readiness)
- \( \bm{\theta} \): parameters

---

## Notes

- Ships exceeding lifespan are retired after reaching mission count \( L_i \)  
- Launch windows occur every \( \Delta = 780 \) days  
- Daily operations track construction, fuel delivery, and return scheduling  
- This model assumes instant refueling at Mars for return trips with sufficient ISRU fuel production.