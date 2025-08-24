---
title: How Long Will It Take to Build a Research Base on Mars?
description: Exploring the logistics of building a Martian research base
image: mars-bfrs.jpg
---

Jim was excited for today. He’d been looking forward to the next series of resupply landings ever since the station had run out of ketchup four months ago. The food was never great at Musk Manor—what the inhabitants of the officially titled International Martian Advanced Research Station, or IMARS, called their home—but ketchup at least made the rations feel like food. Soon enough, the first of over 300 resupply ships would begin landing, and Jim would finally get his hands on some sweet, non-Newtonian processed tomato product.

Jim is a researcher focused on optimizing solar power generation. He hopes that, in addition to cementing IMARS as a permanent research station, his work will aid Earth’s transition to renewable energy, and pave the way for other outposts to be established on other planets.

Research like Jim’s, done on Mars, is likely to accelerate and enable the further expansion of humanity into the solar system, while also driving the  deployment of useful technologies on Earth. The engineering and infrastructure needed to support a Martian outpost will form a blueprint for establishing ourselves on Venus, in the asteroid belt, and beyond. But how long will it actually take to establish a large scientific outpost on Mars?

⸻

Scaling the Outpost

Settling a sizeable scientific and engineering outpost on Mars will require massive logistical support from Earth. To get a rough sense of the infrastructure required, I’m borrowing an imperfect but illustrative analogy: an aircraft carrier, specifically the USS Gerald R. Ford. The Ford supports 4,600 personnel and displaces 101,000 tons, or about 22 tons per person. Of course, much of that mass is dedicated to aircraft, weapons systems, and nuclear propulsion. But for the purposes of estimating what it takes to support thousands of people in a self-contained environment, that “extra stuff” serves as a stand-in for what we’ll need on Mars: life support, ISRU systems, energy storage, radiation shielding, scientific equipment, and more. So, if we imagine a Martian research outpost supporting 5,000 people, a rough target deployment mass of 110,000 tons seems reasonable. That number roughly mirrors the peak summer population of Antarctica, a model for remote, research-driven habitation.

⸻

The Space X Architecture

The Mars architecture outlined by Space X envisions multiple tanker-class Starships ferrying liquid oxygen (LOX) and methane (CH₄) to a fuel depot in low Earth orbit (LEO). These tankers can launch more or less continuously (aside from some turnaround time), since they only fly to LEO and back.

Crew and cargo-class ships will launch and refuel at the depot. Every 780 days (a Martian synodic period) a growing flotilla of these ships will depart for Mars. The journey takes roughly 250 days. Upon landing on the Martian surface, the ships will be refueled by In-Situ Resource Utilization (ISRU) plants, then wait approximately 18 months for the next return window. After the 250 day trip back to Earth, the ships can be refurbished and added back into the fleet alongside newly produced vehicles.

This raises several questions. How many ships will be needed to transport people and equipment to Mars? How quickly can we build ships? How much fuel can we get to the LEO depot?

⸻

Building the Simulation

To explore these questions, I built an interactive simulation tool that lets you tweak the parameters of the mission architecture and observe how they affect the timeline for building out a Martian research base.

The simulator models the full end-to-end logistics pipeline: from ship construction and fuel deliveries to launch window synchronization and ISRU-powered return flights. You can adjust variables like:
- Ship capacities (people per crew ship, cargo per cargo ship)
- Build timelines and production line capacities
- Tanker fuel delivery rate and turnaround time
- Mission lifespans (crew/cargo/tanker)
- Fuel required per Mars round trip

The simulation tracks the system state over a 25-year window, using daily timesteps and realistic constraints. Launch windows occur every 780 days. Each crew or cargo ship must complete a 250-day journey to Mars, spend ~18 months on the surface, and then return during the next window. Tankers deliver fuel to the depot daily. Production lines continuously build new ships constrained by lead times and line capacity.

⸻

So… How Long Will It Take?

Using a reasonable default configuration:
- Each crew ship carries 40 people
- Each cargo ship carries 100 tons of cargo
- 1 crew ship production line, 4 for cargo, 3 for tankers
- Build times of 60 days (crew) and 30 days (cargo/tanker)
- Fuel required per Mars mission: 1600 tons
- Tanker turnaround: 7 days, each carrying 150 tons of fuel
- Launch window every 780 days, with a full round trip taking 1,040 days
- Lifespans: 20 missions (crew/cargo), 50 missions (tankers)

…the simulation shows that we can transport 6,240 people and 123,900 tons of cargo to Mars in just six launch windows, or 12.8 years.

That’s more than enough to establish a self-sufficient outpost with a crew of 5,000 and the necessary infrastructure. Even after accounting for retirement and replacement of aging ships, the system supports sustained growth at this scale. In other words: with an ambitious but achievable production effort and a few hundred ships, a robust, continuously growing Martian base isn't just possible, it’s realistic.


Here’s how the fleet grows across 25 years of continuous shipbuilding and launch window cycles:

![Fleet Size](/static/images/fleet_size.png)

Figure 1: Available Fleet Size.
Cargo ships (green) dominate the fleet composition due to their higher production line capacity and shorter build times. Crew ships (blue) grow more slowly, constrained by a single production line. Tankers (orange) cycle rapidly but stabilize at a relatively flat ~35 ships, bounded by their mission lifespan.

Notice the sharp drops in crew and cargo ship numbers every 780 days, these are the Mars launch windows, when available ships are dispatched en masse to Mars. The first launch window sees a fleet of 13 crew and 101 cargo ships using 182,400 tons of fuel. This initial group will transport 520 people and 10,100 tons of cargo to the Martian surface. By the sixth launch window the fleet has grown to 39 crew and 312 cargo ships using 561,600 tons of fuel. The first group of returning ships will need 182,400 tons of fuel to return to Earth. Splitting this into the 3.54:1 oxygen-to-methane ratio yields approximately 142,100 tons of LOX and 40,200 tons of CH₄.

Fuel delivery does not start as the bottleneck in this configuration, but after the early years the fleet size begins to move ahead of the fuel delivery rate.

![Fuel Depot](/static/images/fuel_depot.png)

Figure 2: LEO Fuel Depot vs. Fleet Needs.
The purple area represents fuel available at the depot. The dashed red line shows the fuel demand of the fleet at each launch window. Fuel supply initially exceeds demand, suggesting that fleet size and production cadence, not fuel, are the bottlenecks in base construction at least in the early phases. But after the early years, tanker fleet size starts to hinder the ability of the depot to keep up with the demand.

⸻

Assumptions & Reality

Of course, this assumes:
- ISRU plants on Mars are reliably producing enough return fuel to sustain the fleet. This is a big assumption, and one I will address in a future post.
- The LEO depot can keep up with tanker deliveries. The sheer number of launches required was a large surprise to me.
- Launches and landings proceed without catastrophic failures. 

These numbers are likely optimistic as production lines don't just poof into existence. In all reality the first few launches will see a trickle of ships as technologies need to be developed and tested before a full scale settlement effort can begin. But under the conditions of this simulation, the model suggests that a city-scale scientific settlement on Mars is achievable in a little over a decade.

Elon Musk has stated the Space X's goal is to produce 1,000 Starships per year. Given that the current lead time for a Falcon 9 is estimated at 12-18 months, this goal might seem fantastical. But Space X has a history of compressing timelines that once seemed impossible. The amount of advanced manufacturing experience and talent Elon Musk has access to both within Space X and at friendly companies like Tesla is likely to be an accelerant to this goal. For this simulation, I assumed an approximate tenfold increase over Falcon 9’s production rate, roughly one Starship per month per line. This is still speculative, but within the realm of engineering plausibility.

I also ignore opposition class transfers, which depending on specific mission parameters, could allow quicker fleet buildup times at the cost of fuel.

These figures are based on what I believe to be reasonable first-pass assumptions. But different parameters will absolutely produce different results, so try your own. **[The simulator is yours to explore →](/fleet-simulator/)**

⸻

A Crucible for Human Progress

Once the floodgates of a functioning base are open, and the nature of the frontier drives invention, capital will begin to flow to Mars. As markets recognize the immense growth potential of not just Mars but a linked, solar system wide economy, we’ll see the beginnings of an off-world commercial and industrial complex.

At this point, it’s fair to ask: doesn’t this sound a lot like the classic imperialistic extractive colonization that reached its zenith in the early 20th century?

I think that’s a reasonable concern. But I also think this is different.

This isn’t a resurrection of imperial capitalism. It’s the continuation of human progress that began when our ancestors first stepped out of Africa. It’s tempting to draw a straight line between this project and Earth’s painful history of extractive colonization. But this is something else, not a conquest, but an expansion of possibility. The goal isn’t plunder, it’s participation. Not domination, but discovery.

Mars is not a colony it’s a crucible. The logistical challenges of building a Martian research base are immense, but not insurmountable. Not with reusable rockets. Not with well-engineered ISRU. Not with the kind of ambition Space X has made demonstrated. A city on Mars is no longer science fiction. It’s a supply chain problem, and supply chains can be solved.

⸻
Addendum

My friend [Gerrit Bruhaug](https://x.com/GBruhaug) noted that the sheer scale of methane required to fuel fleets of this size could be significant enough to influence global markets and drive up prices. While I don’t see this as a limiting factor, I’ve added parameters to the simulation to allow methane price to be adjusted. I've also split the monolithic fuel parameter into individual LOX and methane parameters.


