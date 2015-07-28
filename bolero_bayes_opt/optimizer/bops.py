# Author: Jan Hendrik Metzen <jhm@informatik.uni-bremen.de>

import numpy as np

from bolero.optimizer import Optimizer
from bolero.utils.validation import check_random_state, check_feedback

from bayesian_optimization import (BayesianOptimizer, GaussianProcessModel,
    create_acquisition_function)


class BOPSOptimizer(Optimizer):
    """Bayesian Optimization for Policy Search (BO-PS).

    This optimizer models the landscape of the function to be optimized
    internally by a Gaussian process (GP) and evaluates always those parameters
    which are considered as global optimum of an acquisition function defined
    over this GP. Different acquisition functions and optimizers can be used
    internally.

    Bayesian optimization aims at reducing the number of evaluations of the
    actual function, which is assumed to be costly. To achieve this, a large
    computational budget is allocated at modelling the true function and finding
    potentially optimal positions based on this model.

    .. seealso:: Brochu, Cora, de Freitas
                 "A tutorial on Bayesian optimization of expensive cost
                  functions, with application to active user modelling and
                  hierarchical reinforcement learning"

    Parameters
    ----------
    boundaries : list of pair of floats
        The boundaries of the parameter space in which the optimum is search.

    acquisition_function : optional, string
        String identifying the acquisition function to be used. Supported are
        * "UCB": Upper-Confidence Bound (default)
        * "PI": Probability of Improvement
        * "EI": Expected Improvement

    optimizer: optional, string
        The global optimizer used internally to find the global optimum of the
        respective acquisition function. Supported are:
        * "direct": Using the DIRECT optimizer
        * "lbfgs": Use L-BFGS optimizer
        * "direct+lbfgs": Using the DIRECT optimizer with subsequent L-BFGS
        * "random": Randomly search the parameter space
        * "random+lbfgs": Randomly search parameter space with subsequent
                          L-BFGS
        * "cmaes": Using CMA-ES
        * "cmaes+lbfgs": Using CMA-ES with subsequent L-BFGS

    optimizer_kwargs: optional, dict
        Optional keyword arguments passed to optimize function. Currently
        supported is maxf (an integer, default=100), which determines the
        maximum number of function evaluations

    acq_fct_kwargs: option, dict
        Optional keyword arguments passed to acquisition function. Currently
        supported is kappa (a float >= 0.0, default=0.0), which handles
        the exploration-exploitation trade-off in the acquisition function.

    gp_kwargs: optional, dict
        Optional configuration parameters passed to Gaussian process model.
        See documentation of GaussianProcessModel for details.

    value_transform : optional, function
        Function mapping actual values to values internally by GP modelled.
        For instance, in some situations, a log-transform might be useful.
        Should be a monotonic increasing function. Defaults to identity.

    approx_grad : optional, bool
        Whether the gradient will be approximated numerically during
        optimization or computed analytically. Defaults to False.

    random_state : optional, int
        Seed for the random number generator.
    """
    def __init__(self, boundaries, acquisition_function="ucb",
                 optimizer="direct+lbfgs", optimizer_kwargs={},
                 acq_fct_kwargs={}, gp_kwargs={},
                 value_transform=lambda x: x,
                 approx_grad=True, random_state=None, **kwargs):
        assert isinstance(boundaries, list), \
            "Boundaries must be passed as a list of tuples (pairs)."

        self.boundaries = boundaries
        self.value_transform = value_transform
        if isinstance(self.value_transform, basestring):
            self.value_transform = eval(self.value_transform)
        self.optimizer = optimizer

        self.rng = check_random_state(random_state)

        # Create surrogate model, acquisition function and Bayesian optimizer
        self.model = \
            GaussianProcessModel(random_state=self.rng, **gp_kwargs)

        self.acquisition_function = \
            create_acquisition_function(acquisition_function, self.model,
                                        **acq_fct_kwargs)

        self.bayes_opt = BayesianOptimizer(
            model=self.model, acquisition_function=self.acquisition_function,
            optimizer=self.optimizer,
            maxf=optimizer_kwargs.get("maxf", 100))

    def init(self, dimension):
        self.dimension = dimension

        if len(self.boundaries) == 1:
            self.boundaries = np.array(self.boundaries * self.dimension)
        elif len(self.boundaries) == self.dimension:
            self.boundaries = np.array(self.boundaries)
        else:
            raise Exception("Boundaries not specified for all dimensions")

    def get_next_parameters(self, params, explore=True):
        """Return parameter vector that shall be evaluated next.

        Parameters
        ----------
        params : array-like
            The selected parameters will be written into this as a side-effect.
        explore : bool
            Whether exploration in parameter selection is enabled
        """
        self.parameters = self.bayes_opt.select_query_point(self.boundaries)
        params[:] = self.parameters

    def set_evaluation_feedback(self, feedbacks):
        """Inform optimizer of outcome of a rollout with current weights."""
        return_ = check_feedback(feedbacks, compute_sum=True)
        # Transform reward (e.g. to a log-scale)
        return_ = self.value_transform(return_)

        self.bayes_opt.update(self.parameters, return_)

    def get_best_parameters(self):
        return self.bayes_opt.best_params()

    def is_behavior_learning_done(self):
        # TODO
        return False

    def __getstate__(self):
        """Return a pickable state for this object """
        odict = self.__dict__.copy()  # copy the dict since we change it
        if "value_transform" in odict:
            odict.pop("value_transform")
        return odict
