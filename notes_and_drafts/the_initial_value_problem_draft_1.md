In my quest to simulate chemical reactions I realizeed that my grounding in differential equations could use some work. to this end a aksed chat gpt to constuct a bit of a lecture series on the initial value problem and the parctical aspects of using scipy's solve_ivp function to solve it. Much of this post is a regurgitation in my own words of what I've learned, but I think it will be a useful exercise for me and a useful resource for others.

## The Initial Value Problem
Many of the systems we humans find ourselves interested in can be considered dynamical systems. In a dynamical system, future states depend on how the system evolves over time, and the rules governing that evolution can be described by differential equations. To solve for a system’s state at a future time (often a useful thing to do) we must know the initial conditions of the system. When we're in possession of both the initial conditions and a set of differential equations, we can construct an initial value problem (IVP). Solving the IVP not only lets us predict how a system behaves but also enables us to tune it to behave in accordance with our desires.

Before we dig into the mathematical meat of solving the IVP, there are a few concepts which we must concern ourselves with where a strong foundational understanding is an absolute necessity.

The system: This is the real-world system we’re trying to model. A cooling cup of coffee is a classic example, but it could be anything. In many of the examples that follow, I’ll use a chemical reactor.

The model: This is the collection of differential equations that describe how the system evolves. Centuries of great minds have given us a wealth of models to choose from. For our cooling cup of coffee, we can use Newton’s law of cooling. For our chemical reactor, we can use the laws of thermodynamics and chemical kinetics.

> All models are wrong, but some are useful. - George E. P. Box

This adage is essential to keep in mind when constructing models. It is rather easy to get caught up in the chase of adding ever more sophistication to a model. However, we must keep the end goal in our minds eye and ensure we are justifying each layer of complexity's utility to solving the problem at hand.

The state: This is a collection of variables that describe the system at a given time. For our cooling cup of coffee, this is simply temperature. For our chemical reactor, these might include the molar flow rates or concentrations of the chemical species, along with the reactor’s temperature and pressure.

### The Modeling Workflow 
Step 1. Define the system and states. 
- Should we treat a system as one lump or should we try and isolate a section?
- What variables describe the system state?

Step 2: Write the balance.
- Write down the applicable conservation laws.

Step 3: Write the constitutive laws.

Step 4: Make simplifying assumptions.

Step 5: Rewrite the system in first order form.


