#------------------------------------------------------------------------------------------#
# This file is part of Pyccel which is released under MIT License. See the LICENSE file or #
# go to https://github.com/pyccel/pyccel/blob/master/LICENSE for full license details.     #
#------------------------------------------------------------------------------------------#
# pylint: disable=missing-function-docstring

"""
Handling the transitions between python code and C code.
"""

import numpy as np

from ..errors.errors import Errors
from ..errors.messages import PYCCEL_RESTRICTION_TODO

from .basic     import Basic

from .builtins  import PythonBool, PythonComplex
from .numpy_wrapper import pyarray_to_ndarray

from .datatypes import DataType
from .datatypes import NativeInteger, NativeReal, NativeComplex
from .datatypes import NativeBool, NativeString, NativeGeneric, NativeVoid

from .core      import FunctionCall, FunctionDef, FunctionAddress
from .core      import AliasAssign, Assign, Return, If, DottedVariable
from .core      import IfSection

from .literals  import LiteralTrue

from .numpyext  import NumpyReal, NumpyImag

from .operators import PyccelEq

from .variable  import Variable, ValuedVariable, VariableAddress


errors = Errors()

__all__ = (
#
# --------- CLASSES -----------
#
    'PyccelPyObject',
    'PyccelPyArrayObject',
    'PyArgKeywords',
    'PyArg_ParseTupleNode',
    'PyBuildValueNode',
#--------- CONSTANTS ----------
    'Py_True',
    'Py_False',
    'Py_None',
#----- C / PYTHON FUNCTIONS ---
    'pycomplex_real',
    'pycomplex_imag',
    'pycomplex_fromdoubles',
    'Py_DECREF',
    'PyLong_AsLong',
    'PyFloat_AsDouble',
    'PythonType_Check',
    'NumpyType_Check',
    'PyErr_SetString',
#------- CAST FUNCTIONS ------
    'pyint_to_bool',
    'bool_to_pyobj',
    'pycomplex_to_complex',
    'complex_to_pycomplex',
    'pybool_to_bool',
)

class PyccelPyObject(DataType):
    _name = 'pyobject'

class PyccelPyArrayObject(DataType):
    """ Datatype representing a PyArrayObject which is the
    class used to hold numpy objects"""
    _name = 'pyarrayobject'

PyArray_Type = Variable(NativeGeneric(), 'PyArray_Type')

#TODO: Is there an equivalent to static so this can be a static list of strings?
class PyArgKeywords(Basic):
    """
    Represents the list containing the names of all arguments to a function.
    This information allows the function to be called by keyword

    Parameters
    ----------
    name : str
        The name of the variable in which the list is stored
    arg_names : list of str
        A list of the names of the function arguments
    """
    _attribute_nodes = ()
    def __init__(self, name, arg_names):
        self._name = name
        self._arg_names = arg_names
        super().__init__()

    @property
    def name(self):
        return self._name

    @property
    def arg_names(self):
        return self._arg_names

#using the documentation of PyArg_ParseTuple() and Py_BuildValue https://docs.python.org/3/c-api/arg.html
pytype_parse_registry = {
    (NativeInteger(), 4)       : 'i',
    (NativeInteger(), 8)       : 'l',
    (NativeInteger(), 2)       : 'h',
    (NativeInteger(), 1)       : 'b',
    (NativeReal(), 8)          : 'd',
    (NativeReal(), 4)          : 'f',
    (NativeComplex(), 4)       : 'O',
    (NativeComplex(), 8)       : 'O',
    (NativeBool(), 4)          : 'p',
    (NativeString(), 0)        : 's',
    (PyccelPyObject(), 0)      : 'O',
    (PyccelPyArrayObject(), 0) : 'O!',
    }

class PyArg_ParseTupleNode(Basic):
    """
    Represents a call to the function from Python.h which collects the expected arguments

    Parameters
    ----------
    python_func_args: Variable
        Args provided to the function in python
    python_func_kwargs: Variable
        Kwargs provided to the function in python
    c_func_args: list of Variable
        List of expected arguments. This helps determine the expected output types
    parse_args: list of Variable
        List of arguments into which the result will be collected
    arg_names : list of str
        A list of the names of the function arguments
    is_interface : boolean
        Default value False and True when working with interface functions
    """
    _attribute_nodes = ('_pyarg','_pykwarg','_parse_args','_arg_names')

    def __init__(self, python_func_args,
                        python_func_kwargs,
                        c_func_args, parse_args,
                        arg_names):
        if not isinstance(python_func_args, Variable):
            raise TypeError('Python func args should be a Variable')
        if not isinstance(python_func_kwargs, Variable):
            raise TypeError('Python func kwargs should be a Variable')
        if not all(isinstance(c, (Variable, FunctionAddress)) for c in c_func_args):
            raise TypeError('C func args should be a list of Variables')
        if not isinstance(parse_args, list) and any(not isinstance(c, Variable) for c in parse_args):
            raise TypeError('Parse args should be a list of Variables')
        if not isinstance(arg_names, PyArgKeywords):
            raise TypeError('Parse args should be a list of Variables')
        if len(parse_args) != len(c_func_args):
            raise TypeError('There should be the same number of c_func_args and parse_args')

        self._flags      = ''
        i = 0

        while i < len(c_func_args) and not isinstance(c_func_args[i], ValuedVariable):
            self._flags += self.get_pytype(c_func_args[i], parse_args[i])
            i+=1
        if i < len(c_func_args):
            self._flags += '|'
        while i < len(c_func_args):
            self._flags += self.get_pytype(c_func_args[i], parse_args[i])
            i+=1
        # Restriction as of python 3.8
        if any([isinstance(a, (Variable, FunctionAddress)) and a.is_kwonly for a in c_func_args]):
            errors.report('Kwarg only arguments without default values will not raise an error if they are not passed',
                          symbol=c_func_args, severity='warning')

        parse_args = [[PyArray_Type, a] if isinstance(a, Variable) and a.dtype is PyccelPyArrayObject()
                else [a] for a in parse_args]
        parse_args = [a for arg in parse_args for a in arg]

        self._pyarg      = python_func_args
        self._pykwarg    = python_func_kwargs
        self._parse_args = parse_args
        self._arg_names  = arg_names
        super().__init__()

    def get_pytype(self, c_arg, parse_arg):
        """Return the needed flag to parse or build value
        """
        print('[HERE]', parse_arg, parse_arg.dtype, parse_arg.precision)
        if isinstance(c_arg, FunctionAddress):
            return 'O'
        else:
            try:
                return pytype_parse_registry[(parse_arg.dtype, parse_arg.precision)]
            except KeyError as e:
                raise NotImplementedError("Type not implemented for argument collection : "+str(type(parse_arg))) from e

    @property
    def pyarg(self):
        return self._pyarg

    @property
    def pykwarg(self):
        return self._pykwarg

    @property
    def flags(self):
        return self._flags

    @property
    def args(self):
        return self._parse_args

    @property
    def arg_names(self):
        return self._arg_names

class PyBuildValueNode(Basic):
    """
    Represents a call to the function from Python.h which create a new value based on a format string

    Parameters
    ---------
    parse_args: list of Variable
        List of arguments which the result will be buit from
    """
    _attribute_nodes = ('_result_args',)

    def __init__(self, result_args = ()):
        self._flags = ''
        self._result_args = result_args
        for i in result_args:
            self._flags += pytype_parse_registry[(i.dtype, i.precision)]
        super().__init__()

    @property
    def flags(self):
        return self._flags

    @property
    def args(self):
        return self._result_args

#-------------------------------------------------------------------
#                      Python.h functions
#-------------------------------------------------------------------

# Python.h object  representing Booleans True and False
Py_True = Variable(PyccelPyObject(), 'Py_True',is_pointer=True)
Py_False = Variable(PyccelPyObject(), 'Py_False',is_pointer=True)

# Python.h object representing None
Py_None = Variable(PyccelPyObject(), 'Py_None', is_pointer=True)

# Python.h function managing complex data type
pycomplex_real = FunctionDef(name      = 'PyComplex_RealAsDouble',
                           body      = [],
                           arguments = [Variable(dtype=PyccelPyObject(), name = 'o', is_pointer=True)],
                           results   = [Variable(dtype=NativeReal(), name = 'r')])
pycomplex_imag = FunctionDef(name      = 'PyComplex_ImagAsDouble',
                           body      = [],
                           arguments = [Variable(dtype=PyccelPyObject(), name = 'o', is_pointer=True)],
                           results   = [Variable(dtype=NativeReal(), name = 'r')])
pycomplex_fromdoubles = FunctionDef(name      = 'PyComplex_FromDoubles',
                           body      = [],
                           arguments = [Variable(dtype=NativeReal(), name = 'r'),
                                        Variable(dtype=NativeReal(), name = 'i')],
                           results   = [Variable(dtype=PyccelPyObject(), name = 'o', is_pointer=True)])
Py_DECREF = FunctionDef(name = 'Py_DECREF',
                        body = [],
                        arguments = [Variable(dtype=PyccelPyObject(), name = 'o', is_pointer=True)],
                        results = [])
PyLong_AsLong = FunctionDef(name = 'PyLong_AsLong',
                        body = [],
                        arguments = [Variable(dtype=PyccelPyObject(), name = 'o', is_pointer=True)],
                        results   = [Variable(dtype=NativeInteger(), name = 'r')])
PyFloat_AsDouble = FunctionDef(name = 'PyFloat_AsDouble',
                        body = [],
                        arguments = [Variable(dtype=PyccelPyObject(), name = 'o', is_pointer=True)],
                        results   = [Variable(dtype=NativeReal(), name = 'r')])

def PythonType_Check(variable, argument):
    """
    Create FunctionCall responsible of checking python argument data type
    Parameters:
    ----------
    variable : Variable
        The variable needed for the generation of the type check
    argument : Variable
        argument of the check function

    Returns
    -------
    FunctionCall : Check type FunctionCall
    """
    try :
        check_type = check_type_registry[variable.dtype]
    except KeyError:
        errors.report(PYCCEL_RESTRICTION_TODO, symbol=variable.dtype,severity='fatal')
    check_func = FunctionDef(name = check_type,
                    body = [],
                    arguments = [Variable(dtype=PyccelPyObject(), name = 'o', is_pointer=True)],
                    results   = [Variable(dtype=NativeBool(), name = 'r')])
    return FunctionCall(check_func, [argument])

def PyErr_SetString(error_type, error_msg):
    func = FunctionDef(name = 'PyErr_SetString',
                body = [],
                arguments = [Variable(dtype=PyccelPyObject(), name = 'o'),
                             Variable(dtype =NativeString(), name = 's')],
                results   = [])
    err_type = Variable(PyccelPyObject(), error_type)
    return FunctionCall(func, [err_type, error_msg])

# Casting functions
# Represents type of cast function responsible of the conversion of one data type into another.
# Parameters :
# name of function , list of arguments ,  list of results

def pyint_to_bool(cast_function_name):
    cast_function_argument = Variable(dtype=NativeInteger(), name = 'i', precision=4)
    cast_function_result   = Variable(dtype=NativeBool(), name = 'b')
    cast_function_body     = [Assign(cast_function_result, PythonBool(cast_function_argument)),
                              Return([cast_function_result])  ]
    return FunctionDef(name      = cast_function_name,
                       arguments = [cast_function_argument],
                       body      = cast_function_body,
                       results   = [cast_function_result])

def bool_to_pyobj(cast_function_name):
    cast_function_argument = Variable(dtype=NativeBool(), name = 'b')
    cast_function_result   = Variable(dtype=PyccelPyObject(), name='o', is_pointer=True)
    cast_function_body = [If(
                            IfSection(PythonBool(cast_function_argument),
                                [AliasAssign(cast_function_result, Py_True)]),
                            IfSection(LiteralTrue(),
                                [AliasAssign(cast_function_result, Py_False)])
                          ),
                          Return([cast_function_result])]
    return FunctionDef(name      = cast_function_name,
                       arguments = [cast_function_argument],
                       body      = cast_function_body,
                       results   = [cast_function_result])

def complex_to_pycomplex(cast_function_name):
    cast_function_argument = Variable(dtype=NativeComplex(), name = 'c')
    cast_function_result   = Variable(dtype=PyccelPyObject(), name='o', is_pointer=True)
    real_part = Variable(dtype = NativeReal(), name = 'real_part')
    imag_part = Variable(dtype = NativeReal(), name = 'imag_part')
    cast_function_local_vars = [real_part, imag_part]

    cast_function_body = [Assign(real_part, NumpyReal(cast_function_argument)),
                          Assign(imag_part, NumpyImag(cast_function_argument)),
                          AliasAssign(cast_function_result,
                              FunctionCall(pycomplex_fromdoubles, [real_part, imag_part])),
                          Return([cast_function_result])]
    return FunctionDef(name       = cast_function_name,
                       arguments  = [cast_function_argument],
                       body       = cast_function_body,
                       results    = [cast_function_result],
                       local_vars = cast_function_local_vars)

def pycomplex_to_complex(cast_function_name):
    cast_function_argument = Variable(dtype=PyccelPyObject(), name='o', is_pointer=True)
    cast_function_result   = Variable(dtype=NativeComplex(), name = 'c')
    real_part = Variable(dtype = NativeReal(), name = 'real_part')
    imag_part = Variable(dtype = NativeReal(), name = 'imag_part')
    cast_function_local_vars = [real_part, imag_part]

    cast_function_body = [Assign(real_part, FunctionCall(pycomplex_real, [cast_function_argument])),
                          Assign(imag_part, FunctionCall(pycomplex_imag, [cast_function_argument])),
                          Assign(cast_function_result, PythonComplex(real_part, imag_part)),
                          Return([cast_function_result])]
    return FunctionDef(name      = cast_function_name,
                       arguments = [cast_function_argument],
                       body      = cast_function_body,
                       results   = [cast_function_result],
                       local_vars= cast_function_local_vars)

def pybool_to_bool(cast_function_name):
    cast_function_argument = Variable(dtype=PyccelPyObject(), name='o', is_pointer=True)
    cast_function_result   = Variable(dtype=NativeBool(), name = 'c')

    cast_function_body = [Assign(cast_function_result , PyccelEq(VariableAddress(cast_function_argument), VariableAddress(Py_True)))
                        , Return([cast_function_result])]

    return FunctionDef(name      = cast_function_name,
                       arguments = [cast_function_argument],
                       body      = cast_function_body,
                       results   = [cast_function_result])

cast_function_registry = {
    'pyint_to_bool' : pyint_to_bool,
    'bool_to_pyobj' : bool_to_pyobj,
    'pycomplex_to_complex' : pycomplex_to_complex,
    'complex_to_pycomplex': complex_to_pycomplex,
    'pybool_to_bool' : pybool_to_bool,
    'pyarray_to_ndarray' : pyarray_to_ndarray,
}

collect_function_registry = {
    NativeInteger(): PyLong_AsLong,
    NativeReal()   : PyFloat_AsDouble,
}

check_type_registry  = {
    NativeInteger() : 'PyLong_Check',
    NativeComplex() : 'PyComplex_Check',
    NativeReal()    : 'PyFloat_Check',
    NativeBool()    : 'PyBool_Check',
}

flags_registry = {
    (NativeInteger(), 4)       : 1,
    (NativeInteger(), 8)       : 2,
    (NativeInteger(), 2)       : 3,
    (NativeInteger(), 1)       : 4,
    (NativeReal(), 8)          : 5,
    (NativeReal(), 4)          : 6,
    (NativeComplex(), 4)       : 7,
    (NativeComplex(), 8)       : 8,
    (NativeBool(), 4)          : 9,
    (NativeString(), 0)        : 10
}
