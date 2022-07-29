# Copyright 2013-2021 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import os
import re
import sys
import copy

from .asp import PyclingoDriver, fn
from spliced.logger import logger
import spliced.utils as utils


# We want the root
class_types = ["Struct", "Union", "Array", "Enum", "Class"]


class SolverBase:
    """
    Common base functions for some kind of solver.
    For stability, compatibility, or just fact generation.
    """

    def setup(self, driver):
        """
        Setup to prepare for the solve.
        """
        self.gen = driver

    def print(self, data, title):
        """
        Print a result to the terminal
        """
        if data:
            print("\n" + title)
            print("---------------")
            for entry in data:
                print(" " + " ".join(entry))


class StabilitySolver(SolverBase):
    """
    Class to orchestrate a Stability Solver.
    """

    def __init__(self, lib1, lib2, out=None):
        """
        Create a driver to run a compatibility model test for two libraries.
        """
        # The driver will generate facts rules to generate an ASP program.
        self.driver = PyclingoDriver(out=out)
        self.setup = StabilitySolverSetup(lib1, lib2)

    def solve(self, logic_programs, detail=True):
        """
        Run the solve
        """
        result = self.driver.solve(self.setup, logic_programs=logic_programs)
        missing_imports = result.answers.get("missing_imports", [])
        missing_exports = result.answers.get("missing_exports", [])
        if missing_imports or missing_exports:
            logger.info(
                "Libraries are not stable: %s missing exports, %s missing_imports"
                % (len(missing_exports), len(missing_imports))
            )
            if detail:
                self.print(missing_imports, "Missing Imports")
                self.print(missing_exports, "Missing Exports")
        return result.answers


class StabilitySetSolver(StabilitySolver):
    """
    Class to orchestrate a Stability Set Solver.
    """

    def __init__(self, libA, libsB, lookup, out=None):
        """
        Create a driver to run a compatibility model test for two libraries.
        """
        # The driver will generate facts rules to generate an ASP program.
        self.driver = PyclingoDriver(out=out)
        self.setup = StabilitySetSolverSetup(libA, libsB, lookup)


class FactGenerator(SolverBase):
    """
    Class to orchestrate fact generation (uses FactGeneratorSetup)
    """

    def __init__(self, lib, out=None, lib_basename=False, namespace=None):
        """
        Create a driver to run a compatibility model test for two libraries.
        """
        # The driver will generate facts rules to generate an ASP program.
        self.driver = PyclingoDriver(out=out or sys.stdout)
        self.setup = FactGeneratorSetup(
            lib, lib_basename=lib_basename, namespace=namespace
        )

    def solve(self):
        """
        Generate facts
        """
        return self.driver.solve(self.setup, facts_only=True)


class GeneratorBase:
    """
    The GeneratorBase is the base for any kind of Setup (fact generator or solve)
    Base functions to set up an ABI Stability and Compatability Solver.
    """

    lib_basename = False

    def add_library(self, lib, identifier=None, symbols=None):
        """
        Given a loaded Smeagle Model, generate facts for it.

        If an identifier is given we are doing a comparison / diff between two
        libraries, and this is akin to a namespace, usually A and B.
        Otherwise we just output facts without one.
        """
        lib_name = lib.get("library")
        if lib_name:
            if self.lib_basename:
                lib_name = os.path.basename(lib_name)
            self.gen.h2("Library: %s" % lib_name)

        # Set type lookup to current library
        self.types = lib.get("types", {})

        # Generate a fact for each location
        for loc in lib.get("locations", []):
            if "variables" in loc:
                for var in loc["variables"]:
                    self.generate_variable(
                        lib, var, symbols=symbols, identifier=identifier
                    )

            elif "function" in loc:
                self.generate_function(
                    lib, loc.get("function"), identifier=identifier, symbols=symbols
                ),
            elif "callsite" in loc:
                self.generate_function(
                    lib,
                    loc.get("callsite"),
                    callsite=True,
                    identifier=identifier,
                    symbols=symbols,
                )

    def unwrap_type(self, func):
        """
        Unwrap the type
        """
        # If we are given an array, return early
        if func.get("class") == "Array":
            return func, {}

        # Get underlying type from lookup
        if "type" not in func and "underlying_type" not in func:
            return None, {}

        while "underlying_type" in func:
            func = func["underlying_type"]

        # If the typ is already there, return it
        if "type" not in func:
            return func, {}

        # Another check for array
        if func.get("class") == "Array":
            return func, {}

        typ = func["type"]
        if isinstance(typ, dict) or len(typ) != 32:
            return func, {}

        typ = typ.lstrip("*")

        # This is better on an actual type not having this length.
        # I haven't seen one yet, we could better use a regular expression.
        classes = set()
        while len(typ) == 32:
            next_type = self.types.get(typ)

            # Need to break in parsing array
            if next_type.get("class") == "Array":
                return copy.deepcopy(next_type), classes

            classes.add(next_type.get("class"))

            # we found a pointer or reference
            while "underlying_type" in next_type:
                next_type = next_type["underlying_type"]
                if next_type.get("class") == "Array":
                    return copy.deepcopy(next_type), classes

                if "class" in next_type and next_type["class"]:
                    classes.add(next_type.get("class"))

            if "type" not in next_type:
                break
            typ = next_type["type"].lstrip("*")

        return copy.deepcopy(next_type), classes

    def unwrap_immediate_type(self, func):
        """
        Unwrap the type just one level
        """
        # Get underlying type from lookup
        if "type" not in func:
            return func
        typ = func["type"]

        # We already have the underlying type unwrapped (structs)
        if isinstance(typ, dict):
            return typ
        if len(typ) == 32:
            return self.types.get(typ)
        if "underlying_type" in typ:
            return self.types.get(typ["underlying_type"].get("type")) or typ

    def generate_variable(self, lib, var, identifier=None, symbols=None):
        """
        Generate facts for a variable
        """
        if not var:
            return

        # If symbols defined, scope to that
        if symbols and var.get("name") not in symbols:
            return

        # Don't represent what we aren't sure about - no unknown types
        typ = self.unwrap_immediate_type(var)
        libname = identifier or os.path.basename(lib["library"])

        if not typ:
            return

        # Array we include the type in the top level
        self.parse_type(
            typ,
            libname,
            var["name"],
            variable=True,
            direction=var.get("direction"),
        )

    def unwrap_location(self, param):
        """
        Unwrap the type
        """
        loc = param.get("location", "")

        # Get underlying type from lookup
        if "type" not in param:
            return loc
        typ = param["type"]
        offset = param.get("offset")

        # This is better on an actual type not having this length.
        # I haven't seen one yet, we could better use a regular expression.
        while len(typ) == 32:
            next_type = self.types.get(typ)

            # we found a pointer!
            if next_type.get("class") in ["Pointer", "Reference"]:
                if offset:
                    loc = "(%s+%s)" % (loc, offset)
                else:
                    loc = "(%s)" % loc
                next_type = next_type["underlying_type"]

            elif next_type.get("class") == "TypeDef":
                while "underlying_type" in next_type:
                    if next_type.get("class") in ["Pointer", "Reference"]:
                        loc = "(%s)" % loc
                    next_type = next_type["underlying_type"]

            if "type" not in next_type:
                break
            typ = next_type["type"]

        return loc

    def parse_empty_struct(self, libname, top_name, param, variable=False):
        """
        Make up a fact for an empty struct
        """
        loc = param.get("location")
        if loc:
            loc = self.unwrap_location(param)
        self.add_location(libname, top_name, "Import", "Empty", loc or "none")

    def parse_aggregate_by_value(self, param, libname, top_name, direction):
        """
        Parse an aggregate by value.

        When it's by value the parser cle has already provided registers
        and we don't need to worry about offsets
        """
        fields = param.get("fields", [])
        for field in fields:
            self.parse_type(field, libname, top_name)
        if not fields:
            self.parse_empty_struct(libname, top_name, param)

    def parse_type(
        self,
        param,
        libname,
        top_name,
        variable=False,
        offset_added=False,
        direction=None,
    ):
        """
        Top level function to parse an underlying type fact.
        """
        original = param

        # Structs have types written out
        if "type" in param and isinstance(param["type"], dict):
            param = param["type"]

        if param.get("class") in ["Struct", "Class"]:
            if variable:

                # This adds offsets
                return self.parse_aggregate(
                    param,
                    param,
                    original,
                    libname,
                    top_name,
                    variable=variable,
                    direction=direction,
                )

            # Otherwise it's passed by value - no offsets (known registers)
            return self.parse_aggregate_by_value(
                param, libname, top_name, direction=direction
            )

        elif param.get("class") == "Function":
            param_type = "function"
        else:
            if param.get("class") == "Void":
                param_type = param
            else:
                param_type, classes = self.unwrap_type(param)

            if not param_type:
                return

            if param_type.get("class") == "Array":
                return self.parse_array(
                    param,
                    param_type,
                    libname,
                    top_name,
                    variable=variable,
                    direction=direction,
                )

            if param_type.get("class") in ["Struct", "Class"]:
                return self.parse_aggregate(
                    param,
                    param_type,
                    original,
                    libname,
                    top_name,
                    variable=variable,
                    direction=direction,
                )

            # TODO need a location for pointer
            # abi_typelocation("lib.so","_Z11struct_funciP3Foo","Import","Opaque","(%rsi)+16").
            elif param_type.get("type") == "Recursive":
                return self.parse_opaque(param, libname, top_name, direction)

            # Sizes, directions, and offsets
            size = param_type.get("size")
            direction = direction or param_type.get("direction")
            param_type = param_type.get("class")

            if size and param_type not in class_types + ["var"]:
                size = size * 8

                # If it's an array and has a size, add
                if original.get("class") == "Array" and original.get("size"):
                    size = f"{size}[" + str(original.get("size")) + "]"
                param_type = f"{param_type}{size}"

        # We are using the generic class name instead
        if not param_type or param_type == "Unknown":
            return

        # Get nested location?
        # This skips functions that are used as params...
        location = self.unwrap_location(param)

        if variable and original.get("class") in ["Pointer", "Reference"]:
            location = "(var)"
        elif variable and not location:
            location = "var"
        if not location:
            return

        direction = param.get("direction") or direction or "import"

        # volatile: must be imported
        # const: says cannot read from me (must not be exported)
        # restrictive: I promise none of the other parameters aliases me
        if param.get("volatile") == True or param.get("constant") == True:
            direction = "import"

        # Location and direction are always with the original parameter
        self.add_location(libname, top_name, direction, param_type, location)

    def add_location(self, libname, func, direction, param_type, location):
        """
        Convenience function to print a location, ensuring to add identifier if defined
        """
        self.gen.fact(
            fn.abi_typelocation(
                libname,
                func,
                direction.capitalize(),
                param_type,
                location,
            )
        )

    def parse_opaque(self, param, libname, top_name, direction):
        """
        Parse an opaque (recursive) type
        """
        direction = direction or "import"

        loc = "unknown"
        if "location" in param and param["location"]:
            loc = param["location"]

        self.add_location(
            libname,
            top_name,
            direction,
            "Opaque",
            "(" + loc + ")",
        )

    def parse_array(
        self,
        param,
        param_type,
        libname,
        top_name,
        variable=False,
        direction=None,
    ):
        """
        Parse a struct or a class (and maybe union)

        abi_typelocation("example","_Z3fooiPP7Structy","Import","Array[5]","((%rsi))").
        """
        direction = direction or "import"
        loc = param.get("location")
        if variable:
            loc = "var"

        cls = param_type.get("class", "Array")
        size = param_type.get("size")
        counts = param_type.get("counts")
        if counts:
            counts = ",".join([str(x) for x in counts])
        if size and counts:
            cls = f"{cls}[{size}:{counts}]"
        elif size:
            cls = f"{cls}[{size}]"

        self.add_location(libname, top_name, direction, cls, loc)

        # Pass on the parent array location to underlying type
        if "underlying_type" in param_type:
            ut = param_type["underlying_type"]
            if loc and ut.get("class") in ["Pointer", "Reference"]:
                ut["location"] = "(" + loc + ")"
            elif loc:
                ut["location"] = loc
            return self.parse_type(
                ut,
                libname,
                top_name,
                variable=variable,
                direction=direction,
            )

    def parse_aggregate(
        self,
        param,
        param_type,
        original,
        libname,
        top_name,
        variable=False,
        direction=None,
    ):
        """
        Parse a struct or a class (and maybe union)
        """
        location = self.unwrap_location(param)
        if variable:
            location = "var"
        fields = param_type.get("fields", [])
        for field in fields:
            offset = field.get("offset")

            # If the struct needes to be unwrapped again
            field["location"] = location

            if re.search("[+][0-9]+$", field["location"]) and offset:
                loc, value = field["location"].rsplit("+", 1)
                value = int(value) + offset
                field["location"] = f"{loc}+{value}"

            elif offset:
                field["location"] += f"+{offset}"
            if offset:
                del field["offset"]
            self.parse_type(
                field,
                libname,
                top_name,
                variable=variable,
                direction=direction,
            )

        # Empty structure, etc.
        if not fields:
            self.parse_empty_struct(libname, top_name, original, variable=variable)

    def generate_function(
        self, lib, func, identifier=None, callsite=False, symbols=None
    ):
        """
        Generate facts for a function
        """
        if not func:
            return

        # We cannot generate an atom for anything without a name
        if "name" not in func or func["name"] == "unknown":
            return

        # If symbols defined, scope to that
        if symbols and func.get("name") not in symbols:
            return

        libname = identifier or os.path.basename(lib["library"])
        param_count = 0

        for param in func.get("parameters", []):
            self.parse_type(param, libname, func["name"])
            param_count += 1

        # Parse the return type
        return_type = func.get("return")
        if not return_type or (return_type.get("class") == "Void" and param_count != 0):
            return
        self.parse_type(return_type, libname, func["name"])


class StabilitySetSolverSetup(GeneratorBase):
    """
    Class to set up and run an ABI Stability and Compatability Solver
    using one library A, a set of symbols for it, and a set of dependency
    libraries B, under namespace B, also each with symbols.
    """

    def __init__(self, libA, libsB, symbols):
        self.libA = libA
        self.libsB = libsB
        self.symbols = symbols

    def setup(self, driver):
        """
        Setup to prepare for the solve.
        This function overrides the base setup, which will generate facts only
        for one function.
        """
        self.gen = driver
        self.gen.h1("Library Facts")
        self.add_library(utils.read_json(self.libA), "a", self.symbols[self.libA])
        for B in self.libsB:
            self.add_library(utils.read_json(B), "b", self.symbols[B])


class StabilitySolverSetup(GeneratorBase):
    """
    Class to set up and run an ABI Stability and Compatability Solver.
    """

    def __init__(self, lib1, lib2):
        self.lib1 = lib1
        self.lib2 = lib2

    def setup(self, driver):
        """
        Setup to prepare for the solve.
        This function overrides the base setup, which will generate facts only
        for one function.
        """
        self.gen = driver
        self.gen.h1("Library Facts")
        self.add_library(self.lib1, "a")
        self.add_library(self.lib2, "b")


class FactGeneratorSetup(GeneratorBase):
    """
    Class to accept one library and generate facts.
    """

    def __init__(self, lib, lib_basename=False, namespace=None):
        self.lib = lib

        # Use a basename instead of full path (for testing)
        self.lib_basename = lib_basename
        self.namespace = namespace

    def setup(self, driver):
        """
        Setup to prepare for the solve.
        This base function provides fact generation for one library.
        """
        self.gen = driver
        self.gen.h1("Library Facts")
        self.add_library(self.lib, identifier=self.namespace)
