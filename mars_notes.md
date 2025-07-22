# Mars Notes

Settling a sizeable scientific and engineering outpost on the Martian surface will require large amounts of equipment to be transferred from Earth. I think using an aircraft carrier as a mass per person analog is a good way to think about the problem. Aircraft carriers are large vessels that can carry a large number of people and equipment. They are also relatively self-sufficient, with a large amount of fuel and food on board. The USS Gerald R. Ford (CVN-78) is a nuclear powered aircraft carrier that can carry a crew of 4,600 and has a displacement of 101,000 tons. This gives us a mass per crew member of 22 tons. Assuming we can replace the aircraft and ordnance with life support, ISRU, and scientific equipment we can use this as a baseline for the mass of the outpost. Using the Antarctic research bases as a reference, we can estimate the crew of a large outpost capable of producing a meaningful amount of science to be 5,000 people. This gives us a total mass of 110,000 tons. 

With the payload in mind let's look at the fuel requirements. Though fuel may not be the primary cost driver it is of primary concern as a system mass driver and therefore exploring ways to reduce the fuel requirements could drive the costs down significantly. 

We can break each mission into 5 stages:
Earth to LEO delta v required 9300 m/s
LEO to Mars Orbit delta v required 3600 m/s
Mars Orbit to Mars Surface delta v required 1400 m/s
Mars Surface to Mars Orbit delta v required 4100 m/s 
Mars Orbit to Earth LEO delta v required 3600 m/s
How is delta V calculated?

We are ignoring the delta v required to transfer from Earth LEO to Earth surface as atmospheric drag makes landing on Earth negligible from a fuel efficiency standpoint (Need to verify).

I'll be using ISPs of 330 s at sea level and 380 s in vacuum. I'll use a fuel ratio of 3.5:1 LOX:CH4 (Why?). I'll use a dry mass fraction of 0.10. 

Utilizing the resources available on Mars can significantly reduce the amounts of fuel, life support gases, water, structural materials, and other consumables required to transfer the equipment to Mars. This field of study is called in-situ resource utilization (ISRU). It explores the use of local resources such as the martian atmosphere, regolith, and subsurface water to produce useful materials. The Martian atmosphere is 95% CO2, and Martian regolith is 10% water by weight. Using a combination of atmospheric processing and regolith processing we can produce the necessary fuels and life support gases.


All phases from Earth surface to Mars surface will use fuel produced on Earth.
We will examine two cases for the other phases:
1. Bringing fuel from Earth to Mars
2. Martian ISRU propellant production


Earth orbit fuel depot scheme





TODO: Calculate the fuel requirements per ton of equipment transferred to Mars using starship and super heavy with the Earth orbit fuel depot scheme. With and without Martian ISRU propellant production.

Tsiolkovsky Rocket Equation

m_i = m_f * e^(delta_v / Isp * g_0)

m_i = initial mass
m_f = final mass
delta_v = change in velocity
Isp = specific impulse
g_0 = standard gravity


TODO: Describe the fuel production process and plant requirements. 
Water extraction from regolith.
Martian regolith contains 10% water by weight. This water can be extraced by heating the regolith to 1000 C. This will produce a mixture of water vapor and carbon dioxide. The water vapor can be condensed and stored. The carbon dioxide can be stored in a pressurized tank.

Hydrogen production process.
The stored water can be electrolyzed to produce hydrogen and oxygen. The hydrogen can be stored in a pressurized tank. The oxygen can be stored in a pressurized tank.

Atmospheric processing.
The Martian atmosphere is 95% CO2. This can be processed to produce methane and oxygen. The methane can be stored in a pressurized tank. The oxygen can be stored in a pressurized tank. the Martian atmosphere has an ambient pressure of 610 Pa. This is 0.0061 atm. So it is likely that the atmospheric processing will require a pressurization step.

Methane production process.
The Sabatier reaction is a process by which carbon dioxide and hydrogen are converted to methane and water. This reaction is exothermic and requires a catalyst. A Sabatier reactor can be used to produce methane from carbon dioxide and hydrogen.

Propellant liquefaction.
With the methane from the Sabatier reactor and the oxygen from the electrolyses unit propellant can be produced. The propellant can be stored in a pressurized cryogenic tank.

Power system requirements.
All these systems will require power. Nuclear power is an attractive option though I will be focusing on solar power for now. I'd like to conduct a trade study between nuclear and solar power in the future.


TODO: Given different fleet sizes and the available launch windows, how long would it take to transfer the equipment to Mars?

In an effort to further the discussion around these ideas and encourage future work, I've created a simulation engine that can be used to model the system. The simulation engine is a simple python package that can be used to model an ISRU system. I envision this as a tool to help design and optimize the system. This will begin as a simple exploration of what I see as the most straightforward way to produce propellant on Mars. I'd like the simulation to be modular enough to allow for components to be added and removed as needed. This modularity will allow for the simulation to be used to explore different system configurations and to compare the performance of different systems. I will first be exploring adding increased fidelity and realism to the Sabatier reactor by testing the addition of a microkinetics model reactor. 


End with why do any of this at all?




## An ISRU Propellant Production System to Fully Fuel a Mars Ascent Vehicle
Authors: Julie E. Kleinhenz & Aaron Paz
Published: 2017


Establishes mass and power estimates for a end to end ISRU system including - Excavating and extracting water from Martian regolith
- Atmospheric processing 
- Propellant liquefaction


System mass = 1.7 mT (saving 70 mT of ascent propellant)


Mass penalties and questionable water yields were previously thought to make water extraction from regolith prohibitive.


For every 1 kg of Martian produced propellant the mass savings in LEO is on the order of 10 kg.


### Questions
What is the water content of regolith?
What are the different classifications of regolith (location, depth, type), and what is the water content of each?
Whats the mass of the power source? (Solar)

 --- 

## Methane and Oxygen from Energy-efficient, Low Temperature in-situ Resource Utilization
(ISRU) Enables Missions to Mars

Authors: Mohamed Shahid, Bradley Chambers, & Shrihari Sankarasubramanian
Published: 2023

Low temperature electrolysis for fuel production


---

## Starship and Super Heavy

Super Heavy
Fuel tank capacity 
2700 t of LOX
700 t of CH4

Starship
52.1 m tall
9 m diameter
Dry mass: 100 t
1170 t of LOX
330 t of CH4


System capacity
100-150 t to LEO
27 t to Geostationary Transfer Orbit (GTO)
Claim 100+ t to Moon or Mars

https://en.wikipedia.org/wiki/SpaceX_Super_Heavy
https://en.wikipedia.org/wiki/SpaceX_Starship_(spacecraft)
https://www.spacex.com/media/starship_users_guide_v1.pdf?utm_source=chatgpt.com

---

## Sabatier System Design Study for a Mars ISRU Propellant Production Plant
Authors: Paul E. Hintze1, Anne J. Meier, Malay G. Shah, & Robert DeVor
Published: 2018

Evaluates different Sabatier reactor designs and their performance. Methane purity is is lacking in the current designs.

---

## Sabatier Deep Dive
https://www.sciencedirect.com/science/article/abs/pii/S0016236125010233
https://link.springer.com/article/10.1007/s10665-021-10134-2
https://ntrs.nasa.gov/api/citations/20170007818/downloads/20170007818.pdf?utm_source=chatgpt.com





