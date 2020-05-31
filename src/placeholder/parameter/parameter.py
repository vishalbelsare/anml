from dataclasses import fields, field, InitVar
from dataclasses import dataclass
from typing import List, Callable
import numpy as np
from copy import deepcopy


from placeholder.parameter.prior import Prior
from placeholder.exceptions import PlaceholderError

BANNED_NAMES = ['intercept']


class VariableError(PlaceholderError):
    pass


class ParameterError(PlaceholderError):
    pass


class ParameterSetError(PlaceholderError):
    pass


@dataclass
class Variable:
    """A class that stores information about a variable.

    Parameters
    ----------
    covariate: str
        name of the covariate for this variable. 
    var_link_fun: callable
        link function for this variable. 
    fe_init: float
        initial value to be used in optimization for fixed effect. 
    re_init: float
        initial value to be used in optimization for random effect.
    re_zero_sum_std: float, optional
        standard deviation of zero sum prior for random effects.
    fe_gprior: Prior, optional
        a prior of class :class:`~placeholder.parameter.prior.Prior`
    re_gprior: Prior, optional
        a prior of class :class:`~placeholder.parameter.prior.Prior`

    Attributes
    ----------
    All parameters become attributes after validation.
    
    """
    var_link_fun: Callable = lambda x: x
    covariate: str = None

    fe_init: float = 0.
    re_init: float = 0.

    fe_gprior: Prior = Prior()
    re_gprior: Prior = Prior()

    re_zero_sum_std: float = field(default=np.inf)

    def __post_init__(self):
        if not isinstance(self.covariate, str):
            raise VariableError("Covariate name must be a string.")
        if self.covariate in BANNED_NAMES:
            raise VariableError("Choose a different covariate name that is"
                                f"not in {BANNED_NAMES}.")


@dataclass
class Intercept(Variable):
    covariate = 'intercept'


@dataclass
class Parameter:
    """A class for parameters. 
    
    Parameters
    ----------
    param_name: str
        name of the parameter 
    link_fun: callable
        link function for the parameter 
    variables: List[:class:`~placeholder.parameter.parameter.Variable`]
        a list of variables
    
    Attributes
    ----------
    All attributes from :class:`~placeholder.parameter.parameter.Variable`s in `variables` 
    are carried over but are put into a list.

    num_fe: int
        total number of effects (variables) for the parameter

    """
    param_name: str
    link_fun: Callable
    variables: InitVar[List[Variable]]

    num_fe: int = field(init=False)
    covariate: List[str] = field(init=False)
    var_link_fun: List[Callable] = field(init=False)

    fe_init: List[float] = field(init=False)
    re_init: List[float] = field(init=False)

    fe_gprior: List[List[Prior]] = field(init=False)
    re_gprior: List[List[Prior]] = field(init=False)
    fe_bounds: List[List[Prior]] = field(init=False)
    re_bounds: List[List[Prior]] = field(init=False)

    re_zero_sum_std: List[float] = field(init=False)

    def __post_init__(self, variables):
        assert isinstance(variables, list)
        assert len(variables) > 0
        assert isinstance(variables[0], Variable)
        self.num_fe = len(variables)
        for k, v in consolidate(Variable, variables).items():
            self.__setattr__(k, v)


@dataclass
class ParameterFunction:
    """A class for function on parameters.

    Parameters
    ----------
    param_function_name: str
        name of the parameter function
    param_function: callable
        parameter function
    param_function_fe_gprior: List[float]
        a list of two floats specifying mean and std for Gaussian prior on the function.
    """

    param_function_name: str
    param_function: Callable
    param_function_fe_gprior: List[Prior] = field(default_factory=lambda: [Prior])

    def __post_init__(self):
        assert isinstance(self.param_function_name, str)


@dataclass
class ParameterSet:
    """A class for a set of parameters.

    Parameters
    ----------
    parameters: List[:class:`~placeholder.parameter.parameter.Parameter`]
        a list of parameters.
    parameter_functions: List[:class:`~placeholder.parameter.parameter.ParameterFunction`]
        a list of parameter functions.

    Attributes
    ----------
    All attributes from :class:`~placeholder.parameter.parameter.Parameter`s in `parameters` 
    are carried over and put into a list of lists.

    num_fe: int
        total number of effects (variables) for the parameter set.
    """

    parameters: InitVar[List[Parameter]]
    parameter_functions: InitVar[List[ParameterFunction]] = None

    param_name: List[str] = field(init=False)
    num_fe: int = field(init=False)
    link_fun: List[Callable] = field(init=False)
    covariate: List[List[str]] = field(init=False)
    var_link_fun: List[List[Callable]] = field(init=False)

    fe_init: List[List[float]] = field(init=False)
    re_init: List[List[float]] = field(init=False)

    fe_gprior: List[List[List[Prior]]] = field(init=False)
    re_gprior: List[List[List[Prior]]] = field(init=False)
    fe_bounds: List[List[List[Prior]]] = field(init=False)
    re_bounds: List[List[List[Prior]]] = field(init=False)

    re_zero_sum_std: List[List[float]] = field(init=False)

    param_function_name: List[str] = field(init=False)
    param_function: List[Callable] = field(init=False)
    param_function_fe_gprior: List[List[float]] = field(init=False)

    def __post_init__(self, parameters, parameter_functions):

        for k, v in consolidate(Parameter, parameters, exclude=['num_fe']).items():
            self.__setattr__(k, v)

        for k, v in consolidate(ParameterFunction, parameter_functions).items():
            self.__setattr__(k, v)

        if len(set(self.param_name)) != len(self.param_name):
            raise RuntimeError("Cannot have duplicate parameters in a set.")
        if len(set(self.param_function_name)) != len(self.param_function_name):
            raise RuntimeError("Cannot have duplicate parameter functions in a set.")

        self.num_fe = 0
        for param in parameters:
            self.num_fe += param.num_fe

    def get_param_index(self, param_name: str):
        """A function that returns index of a given parameter.

        Parameters
        ----------
        param_name : str
            name of the parameter

        Returns
        -------
        int
            index of the parameter

        Raises
        ------
        RuntimeError
            parameter not found in the parameter set.
        """
        try:
            param_index = self.param_name.index(param_name)
        except ValueError:
            raise RuntimeError(f"No {param_name} parameter in this parameter set.")
        return param_index

    def get_param_function_index(self, param_function_name):
        """A function that returns index of a given parameter function. 

        Parameters
        ----------
        param_function_name : str
            name of the parameter function

        Returns
        -------
        int
            index of the parameter function

        Raises
        ------
        RuntimeError
            parameter function not found in the parameter set.
        """
        try:
            param_function_index = self.param_function_name.index(param_function_name)
        except ValueError:
            raise RuntimeError(f"No {param_function_name} parameter function in this parameter set.")
        return param_function_index

    def delete_random_effects(self):
        """A function that deletes random effects for all parameters in the parameter set.

        Returns
        -------
        :class:`~placeholder.parameter.parameter.ParameterSet`
            a parameter set with no random effects on parameters.
        """
        param_set = deepcopy(self)
        bounds = np.array(self.re_bounds)
        bounds[:] = 0.
        param_set.re_bounds = bounds.tolist()
        return param_set


def consolidate(cls, instance_list, exclude=None):
    """A function that given a list of objects of the same type, 
    collect their values corresponding to the same attribute and put into a list.

    Parameters
    ----------
    cls : Object
        the class of the objects in :python:`instance_list`
    instance_list : List[Object]
        a list of objects of the same type
    exclude : List[str], optional
        attributes that do not wish to be collected and consolidated, by default None

    Returns
    -------
    Dict[str, List]
        a dictionary where key is the name of an attribute and value a list of attribute values collected
        from the objects.
    """
    if exclude is None:
        exclude = []
    consolidated = {}
    for f in fields(cls):
        if f.name not in exclude:
            if instance_list is not None:
                consolidated[f.name] = [instance.__getattribute__(f.name) for instance in instance_list]
            else:
                consolidated[f.name] = list()
    return consolidated
