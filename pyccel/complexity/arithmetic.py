# coding: utf-8
#------------------------------------------------------------------------------------------#
# This file is part of Pyccel which is released under MIT License. See the LICENSE file or #
# go to https://github.com/pyccel/pyccel/blob/master/LICENSE for full license details.     #
#------------------------------------------------------------------------------------------#

"""
This module provides us with functions and objects that allow us to compute
the arithmetic complexity a of a program.

Example
-------

>>> code = '''
... n = 10
... for i in range(0,n):
...     for j in range(0,n):
...         x = pow(i,2) + pow(i,3) + 3*i
...         y = x / 3 + 2* x
... '''

>>> from pyccel.complexity.memory import MemComplexity
>>> M = OpComplexity(code)
>>> d = M.cost()
>>> print "f = ", d['f']
f =  n**2*(2*ADD + DIV + 2*MUL + 2*POW)

"""

from collections import OrderedDict

from sympy import count_ops as sympy_count_ops
from sympy import Tuple
from sympy import summation
from sympy import Symbol

from pyccel.ast.literals import Literal
from pyccel.ast.core     import For, Assign, AugAssign, CodeBlock, Comment, EmptyNode
from pyccel.ast.core     import Allocate, Deallocate
from pyccel.ast.core     import FunctionDef, FunctionCall
from pyccel.ast.core     import Return
from pyccel.ast.core     import AddOp, SubOp, MulOp, DivOp
from pyccel.ast.internals import PyccelArraySize
from pyccel.ast.operators import PyccelAdd, PyccelMinus, PyccelDiv, PyccelMul
from pyccel.ast.variable  import IndexedElement, Variable
from pyccel.ast.numpyext import NumpyZeros, NumpyOnes
from pyccel.ast.operators import  PyccelOperator, PyccelAssociativeParenthesis
from pyccel.ast.sympy_helper import pyccel_to_sympy
from pyccel.complexity.basic import Complexity

__all__ = ["count_ops", "OpComplexity"]

ADD = Symbol('ADD')
SUB = Symbol('SUB')
MUL = Symbol('MUL')
DIV = Symbol('DIV')

op_registry = {
    AddOp(): ADD,
    SubOp(): SUB,
    MulOp(): MUL,
    DivOp(): DIV,
#    ModOp: MOD,
    }


# ==============================================================================
class OpComplexity(Complexity):
    """class for Operation complexity computation."""

    def cost(self, mode=None):
        """
        Computes the complexity of the given code.

        verbose: bool
            talk more

        mode: string
            possible values are (None, simple)
        """
        costs = OrderedDict()

        # ... first we treat declared functions
        if self.functions:
            for fname, d in self.functions.items():
                expr = count_ops(d, visual=True, costs=costs)

                if not(expr == 0) and (mode == 'simple'):
                    for i in ['ADD', 'SUB', 'DIV', 'MUL']:
                        expr = expr.subs(Symbol(i), 1)

                costs[fname] = expr
        # ...
#        print('*** ', costs)

        # ... then we compute the complexity for the main program
        expr = count_ops(self.ast, visual=True, costs=costs)

        if not(expr == 0) and (mode == 'simple'):
            for i in ['ADD', 'SUB', 'DIV', 'MUL']:
                expr = expr.subs(Symbol(i), 1)
        # ...

        # TODO use setter here
        self._costs = costs

        return expr

# ==============================================================================
# TODO move inside OpComplexity following the visiter algorithm
def count_ops(expr, visual=None, costs=None):

#    print('>>> ', expr)

    symbol_map = {}
    used_names = set()

    if isinstance(expr, Assign):
<<<<<<< Updated upstream
        rhs = pyccel_to_sympy(expr.rhs, symbol_map, used_names)
        return sympy_count_ops(rhs, visual)
    elif isinstance(expr, For):
        a = pyccel_to_sympy(expr.iterable, symbol_map, used_names).size
        ops = sum(count_ops(i, visual) for i in expr.body.body)
        return a*ops
=======
        if isinstance(expr.rhs, (NumpyZeros, NumpyOnes, Comment, EmptyNode)):
            return 0

        # ...
        if isinstance(expr, AugAssign):
            op = op_registry[expr.op]
        else:
            op = 0
        # ...

        return op + count_ops(expr.rhs, visual, costs=costs)

    elif isinstance(expr, For):
        ops = sum(count_ops(i, visual, costs=costs) for i in expr.body.body)

        i = expr.target
        b = expr.iterable.start
        e = expr.iterable.stop
        i = pyccel_to_sympy(i, symbol_map, used_names)
        b = pyccel_to_sympy(b, symbol_map, used_names)
        e = pyccel_to_sympy(e, symbol_map, used_names)
        # TODO treat the case step /= 1
        return summation(ops, (i, b, e-1))

    elif isinstance(expr, (Tuple, list)):
        return sum(count_ops(i, visual, costs=costs) for i in expr)

    elif isinstance(expr, FunctionDef):
        return count_ops(expr.body, visual, costs=costs)

    elif isinstance(expr, FunctionCall):
        if costs is None:
            raise ValueError('costs dict is None')

        fname = expr.func_name.name #func_name is sympy.Symbol here

        if not fname in costs.keys():
            raise ValueError('Cannot find the cost of the function {}'.format(fname))

        return costs[fname]

>>>>>>> Stashed changes
    elif isinstance(expr, CodeBlock):
        return sum(count_ops(i, visual, costs=costs) for i in expr.body)

    elif isinstance(expr, (NumpyZeros, NumpyOnes, Comment, EmptyNode, Allocate, Deallocate)):
        return 0

    elif isinstance(expr, PyccelArraySize):
        return 0

<<<<<<< Updated upstream
    expr = pyccel_to_sympy(expr, symbol_map, used_names)

    if isinstance(expr, Tuple):
        return sum(count_ops(i, visual) for i in expr)
=======
    elif isinstance(expr, Literal):
        return 0

    elif isinstance(expr, Variable):
        return 0

    elif isinstance(expr, IndexedElement):
        return 0

    elif expr is None:
        return 0

    elif isinstance(expr, Return):
        return sum(count_ops(i, visual, costs=costs) for i in [expr.stmt, expr.expr])

    elif isinstance(expr, PyccelAdd):
        ops = sum(count_ops(i, visual, costs=costs) for i in expr.args)
        return ops+ADD

    elif isinstance(expr, PyccelMinus):
        ops = sum(count_ops(i, visual, costs=costs) for i in expr.args)
        return ops+SUB

    elif isinstance(expr, PyccelDiv):
        ops = sum(count_ops(i, visual, costs=costs) for i in expr.args)
        return ops+DIV

    elif isinstance(expr, PyccelMul):
        ops = sum(count_ops(i, visual, costs=costs) for i in expr.args)
        return ops+MUL

    elif isinstance(expr, PyccelOperator):
        return sum(count_ops(i, visual, costs=costs) for i in expr.args)

>>>>>>> Stashed changes
    else:
        raise NotImplementedError('TODO count_ops for {}'.format(type(expr)))


##############################################
if __name__ == "__main__":
    code = '''
n = 10

for i in range(0,n):
    for j in range(0,n):
        x = pow(i,2) + pow(i,3) + 3*i
        y = x / 3 + 2* x
    '''

#    complexity = OpComplexity(code)
#    complexity = OpComplexity('ex1.py')
#    complexity = OpComplexity('ex_assembly.py')
#    complexity = OpComplexity('exam_exo1.py')
#    complexity = OpComplexity('ex2.py')
    complexity = OpComplexity('ex3.py')

#    expr = complexity.cost(mode='simple')
    expr = complexity.cost(mode=None)
    print(expr)
    print(complexity.costs)
    print('----------------------')
    for f, c in complexity.costs.items():
        print('> cost of {} = {}'.format(f, c))
