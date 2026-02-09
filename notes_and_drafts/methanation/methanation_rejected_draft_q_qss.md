First we will define the elementary mechanism for each reaction (step \(S\)). The goal is to define the plausible sequence of surface events for our catalyst.

Gas phase species:
$$ \nu_{i,s}^{gas} i \in \{H_2, CO_2, CO, H_2O, CH_4\} $$

Surface site \(s\) 
Vacant site \(*\)
Surface species:
$$ \nu_{i,s}^{surf} i \in \{*, CO_2, H_2O, CO, O, OH, H, HCO, H_2CO, H_3CO, CH_4, C\} $$


**Adsorption / Desorption:**
\(H_2\) dissociates upon adsorption to form 2 surface species:
$$ H_2(g) + 2* \rightleftharpoons 2H^* $$ 

$$ CO + * \rightleftharpoons CO^* $$

$$ CO_2(g) + * \rightleftharpoons CO_2^* $$

$$ H_2O(g) + * \rightleftharpoons H_2O^* $$

$$ CH_4(g) + * \rightleftharpoons CH_4^* $$

**Activation / Surface Reactions:**
\(CO_2\) activation RWGS pathway:
$$ CO_2^* + * \rightleftharpoons CO + O^* $$

Oxygen removal pathway:
$$ O^* + H^* \rightleftharpoons OH^* + * $$

$$ OH^* + H^* \rightleftharpoons H_2O^* + * $$

$$ H_2O^* \rightleftharpoons H_2O(g) + * $$

\(CO\) hydrogenation to \(CH_4\):
$$ CO^* + H^* \rightleftharpoons HCO^* + * $$

$$ HCO^* + H^* \rightleftharpoons H_2CO^* + * $$

$$ H_2CO^* + H^* \rightleftharpoons H_3CO^* + * $$

$$ H_3CO^* + H^* \rightleftharpoons CH_4^* + O^* $$

$$ CH_4^* \rightleftharpoons CH_4(g) + * $$

**Site Balance and Surface Coverage:**
All surface species compete for the same pool of sites on the catalyst surface.
$$ \theta_* + \theta_{s_1} + \theta_{s_2} ... + \theta_{s_n} + \theta_C = 1 $$

We need to solve for the surface coverage \(\theta_X\) for each surface species \(X\). The dynamic balances are given by:

$$ \frac{d\theta_X}{dt} = \sum_s \nu^{(\text{surf})}_{X,s}\, r_s(\theta,a,T) $$

Where \(\nu^{(\text{surf})}_{X,s}\) is the stoichiometric coefficient for the \(X\)th species on the \(s\)th reaction. \(r_s(\theta,a,T)\) is the rate of the \(s\)th reaction at temperature \(T\).

Because surface reactions occur much faster than gaseous transport, we can assume a quasi-steady state: surface coverages adjust essentially instantaneously relative to plug flow down the reactor. That means to find the steady state surface coverages at each axial position \(z\), we solve the nonlinear system:

$$ g(\theta; a, T) = \nu^{(surf)}\, r(\theta,a,T) = 0 $$

To solve this we can use use Newton's method. This is a iterative method where we start with an initial guess for the surface coverage of each surface species \((\theta_X^0)\). We then compute the residual vector \((\hat{g})\) to see how far we are from steady state.

$$ \hat{g}(\hat{\theta}) = \hat{\nu}^{surf} r $$

 We then consult the jacobian \((\hat{J})\) which contains the partial derivatives of the residual vector with respect to the surface coverage showing how small nudges to any one of the surface coverage will effect the rest. 

 $$ \hat{J} = \frac{\partial \hat{g}}{\partial \hat{\theta}} $$

 
 We solve a small linear system to get a new guess and iteratively repeat this process until the residual \((\hat{g})\) is less than a tolerance.

For each iteration \(k\) we:
$$ \text{Evaluate residuals} \quad g^{(k)} = g(\theta^{(k)}) $$

$$ \text{Evaluate jacobian} \quad J^{(k)} = \frac{\partial g}{\partial \theta} \bigg|_{\theta^{(k)}} $$

$$ \text{Newton step} \quad \Delta \theta^{(k)} = -(J^{(k)})^{-1} g^{(k)} $$

$$ \text{Update with damping and bounds} \quad \theta^{k+1} = \text{clip}(\theta^{k} + \alpha^{(k)}\Delta \theta^{(k)}, 0, 1) $$

Where \(\alpha^{(k)} \in [0, 1]\) is the damping factor and is chosen to keep all coverages and the vacancy fraction positive and \(\epsilon\) is the tolerance.

$$ \text{Stop if} \quad ||g^{(k)}||_\infty < \epsilon $$

With this in hand we can solve for the surface coverage at each axial position \(z\).

**Reaction Rates:**
For each reaction we need a forward \(k_f^s(T)\) and reverse \(k^r_s(T)\) rate constant, and a equilibrium constant \(K_s(T)\). We will use the familiar Arrhenius equation to model the forward rate constant and will combine the equilibrium constant with the forward rate constant to model the reverse rate constant. To be explicit I'll restate each of these equations here:
np
$$ k_f^s(T) = A_s T^{n_s} e^{-\frac{E_{a,s}}{RT}} $$

Where \(A_s\) is the pre-exponential factor, \(n_s\) is the temperature dependence (fit dependent), \(E_{a,s}\) is the activation energy, \(R\) is the universal gas constant, and \(T\) is the temperature.

$$ K_s(T) = e^{-\left(\frac{\Delta G^\circ_s(T)}{R T}\right)} $$

Where \(\Delta G^\circ_s(T)\) is the standard Gibbs free energy of reaction at temperature \(T\).

$$ k^r_s(T) = \frac{k_f^s(T)}{K_s(T)} $$

Whith these in hand we can calulate the reaction rate for each step reaction.

$$ r_s = k_{s}^f(T) \prod_X{\xi_X^{\nu_{X,s}^f}} - k_{s}^r(T) \prod_X{\xi_X^{\nu_{X,s}^r}} $$
Looks a bit scary, but stay with me. 
Where \(\xi_X\) = \(\theta_X\) for surface species and \(\xi_X\) = \(a_X\) for gas phase species. \(s\) is the surface site index. \(X\) is the species index. \(k_{s}^f(T)\) and \(k_{s}^r(T)\) are the forward and reverse rate constants for the \(s\)th surface site at temperature \(T\). \(\nu_{X,s}^f\) and \(\nu_{X,s}^r\) are the forward and reverse stoichiometric coefficients for the \(X\)th species on the \(s\)th surface site.

This system allows us to compute the per site step rate for each reaction.