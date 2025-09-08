## Level 5 [WIP]

Level 5 introduces reversibility of the reaction, side reactions like the water-gas shift reaction, intermediate species like CO, surface species like CO2 and H2 adsorbed on the catalyst surface, a more complete treatment of kinetics, and non-ideal gas behavior. We also switch our integrator to use catalyst mass as the independent variable instead of length (maybe?).


#### Langmuir-Hinshelwood Kinetics
Catalytic reactions like methanation benefit from a more complete treatment of the surface phenomena at the catalyst. Langmuir-Hinshelwood (L-H) kinetics captures the adsorption and desorption of the reactants and products on the catalyst surface. This model requires intrinsic rate constants for each species as well as empirically derived equilibrium constants.

$$ r’=\frac{k\,K_{\mathrm{CO_2}}\,P_{\mathrm{CO_2}}\,P_{\mathrm{H_2}}^{\,4}\;\Big[1-\dfrac{P_{\mathrm{CH_4}}\,P_{\mathrm{H_2O}}^{\,2}}{K_\text{eq}(T)\,P_{\mathrm{CO_2}}\,P_{\mathrm{H_2}}^{\,4}}\Big]}
{\Big(1+a_{\mathrm{H_2}}\sqrt{P_{\mathrm{H_2}}}+K_{\mathrm{CO_2}}P_{\mathrm{CO_2}}+K_{\mathrm{H_2O}}P_{\mathrm{H_2O}}+K_{\mathrm{CH_4}}P_{\mathrm{CH_4}}\Big)^{2}} $$

Where \(r'\) is the reaction rate, \(k\) is the rate constant, \(K_i\) is the equilibrium constant for \(i\)th species, \(P_i\) is the partial pressure of \(i\)th species, \(K_\text{eq}(T)\) is the equilibrium constant at temperature \(T\), and \(a_{\mathrm{H_2}}\) is the reaction order w.r.t to H2. 

\(K_\text{eq}(T)\) is the equilibrium constant at temperature \(T\) and is calculated as the exponential of the negative ratio of the heat of reaction to the universal gas constant \(R\) and the temperature \(T\).

$$ K_\text{eq}(T) = e^{-\frac{\Delta H_r(T)}{R T}} $$

A note on coupled reactions: This model doesn't account for coupled reactions like the water-gas shift reaction, intermediate species, or surface species.

## Conclusion
Set up future post: reactors in series, heat exchangers, H20 removal, etc.