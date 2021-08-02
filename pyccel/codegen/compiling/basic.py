#!/usr/bin/python
# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------------------#
# This file is part of Pyccel which is released under MIT License. See the LICENSE file or #
# go to https://github.com/pyccel/pyccel/blob/master/LICENSE for full license details.     #
#------------------------------------------------------------------------------------------#
"""
Module handling classes for compiler information relevant to a given object
"""
import os
import sys
from filelock import FileLock

class CompileObj:
    """
    Class containing all information necessary for compiling

    Parameters
    ----------
    file_name     : str
                    Name of file to be compiled

    folder        : str
                    Name of the folder where the file is found

    is_module     : bool
                    Indicates whether we are compiling a module or a program
                    Default : True

    flags         : str
                    Any non-default flags passed to the compiler

    includes      : iterable of strs
                    include directories paths

    libs          : iterable of strs
                    required libraries

    libdirs       : iterable of strs
                    paths to directories containing the required libraries

    dependencies  : iterable of CompileObjs
                    objects which must also be compiled in order to compile this module/program

    accelerators  : str
                    Tool used to accelerate the code (e.g. openmp openacc)
    """
    def __init__(self,
                 file_name,
                 folder,
                 is_module    = True,
                 flags        = (),
                 includes     = (),
                 libs         = (),
                 libdirs      = (),
                 dependencies = (),
                 accelerators = ()):
        if not all(isinstance(d, CompileObj) for d in dependencies):
            raise TypeError("Dependencies require necessary compile information")

        self._file = os.path.join(folder, file_name)
        self._folder = folder

        self._module_name = os.path.splitext(file_name)[0]
        rel_mod_name = os.path.join(folder, self._module_name)
        self._module_target = rel_mod_name+'.o'

        self._prog_target = rel_mod_name
        if sys.platform == "win32":
            self._prog_target += '.exe'

        self._target = self._module_target if is_module else self._prog_target
        self._target = os.path.join(folder, self._target)

        self._lock         = FileLock(self.target+'.lock')

        self._flags        = list(flags or ())
        self._includes     = [folder, *(includes or ())]
        self._libs         = list(libs or ())
        self._libdirs      = list(libdirs or ())
        self._accelerators = set(accelerators or ())
        self._dependencies = set()
        if dependencies:
            self.add_dependencies(*dependencies)
        self._is_module    = is_module

    def reset_folder(self, folder):
        """
        Change the folder in which the source file is saved (useful for stdlib)
        """
        self._file = os.path.join(folder, os.path.basename(self._file))
        self._folder = folder

        rel_mod_name = os.path.join(folder, self._module_name)
        self._module_target = rel_mod_name+'.o'

        self._prog_target = rel_mod_name
        if sys.platform == "win32":
            self._prog_target += '.exe'

        self._target = self._module_target if self.is_module else self._prog_target
        self._target = os.path.join(folder, self._target)

        self._lock         = FileLock(self.target+'.lock')

    @property
    def source(self):
        """ Returns the file to be compiled
        """
        return self._file

    @property
    def source_folder(self):
        """ Returns the location of the file to be compiled
        """
        return self._folder

    @property
    def python_module(self):
        """ Returns the python name of the file to be compiled
        """
        return self._module_name

    @property
    def module_target(self):
        """ Returns the file to be generated by the compilation step
        """
        return self._module_target

    @property
    def target(self):
        """ Returns the file to be generated by the compilation step
        """
        return self._target

    @property
    def flags(self):
        """ Returns the additional flags required to compile the file
        """
        return self._flags

    @property
    def includes(self):
        """ Returns the additional include directories required to compile the file
        """
        return self._includes

    @property
    def libs(self):
        """ Returns the additional libraries required to compile the file
        """
        return self._libs

    @property
    def libdirs(self):
        """ Returns the additional library directories required to compile the file
        """
        return self._libdirs

    @property
    def extra_modules(self):
        """ Returns the additional objects required to compile the file
        """
        deps = set(d.target for d in self._dependencies)
        for d in self._dependencies:
            deps = deps.union(d.extra_modules)
        return deps

    @property
    def dependencies(self):
        """ Returns the objects which the file to be compiled uses
        """
        return self._dependencies

    def add_dependencies(self, *args):
        """
        Indicate that the file to be compiled depends on a given other file

        Parameters
        ----------
        *args : CompileObj
        """
        if not all(isinstance(d, CompileObj) for d in args):
            raise TypeError("Dependencies require necessary compile information")
        self._dependencies = self._dependencies.union(args)
        for a in args:
            self._includes.append(a.source_folder)
            self._includes.extend(a.includes)
            self._libs.extend(a.libs)
            self._libdirs.extend(a.libdirs)
            self._accelerators = self._accelerators.union(a.accelerators)

    def acquire_lock(self):
        """
        Lock the file and its dependencies to prevent race conditions
        """
        self._lock.acquire()
        for d in self.dependencies:
            d.acquire_simple_lock()

    def acquire_simple_lock(self):
        """
        Lock the file to prevent race conditions but not its dependencies
        """
        self._lock.acquire()

    def release_lock(self):
        """
        Unlock the file and its dependencies
        """
        self._lock.release()
        for d in self.dependencies:
            d.release_simple_lock()

    def release_simple_lock(self):
        """
        Unlock the file
        """
        self._lock.release()

    @property
    def accelerators(self):
        """ Returns the names of the accelerators required to compile the file
        """
        return self._accelerators

    @property
    def is_module(self):
        """ Indicates if the result is a module or a program
        """
        return self._is_module

    def __eq__(self, other):
        return self.target == other.target

    def __hash__(self):
        return hash(self.target)
