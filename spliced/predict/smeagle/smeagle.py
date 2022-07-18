# Copyright 2013-2021 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import os
import json
import re
import sys
import copy

from spliced.logger import logger
import spliced.utils as utils

# Smeagle TODO:
# account for flags (volatile, restrict, const, etc.) for pointers "CV qualified"
# CV qualification is not in the model!

# We want the root
here = os.path.abspath(os.path.dirname(__file__))
class_types = ["Struct", "Union", "Array", "Enum", "Class"]

try:
    import clingo

    clingo_cffi = hasattr(clingo.Symbol, "_rep")
except ImportError:
    clingo = None


def _id(thing):
    """
    Quote string if needed for it to be a valid identifier.
    """
    if isinstance(thing, AspFunction):
        return thing
    elif isinstance(thing, bool):
        return '"%s"' % str(thing)
    elif isinstance(thing, int):
        return str(thing)
    else:
        return '"%s"' % str(thing)


class AspFunction:
    """
    An asp function
    """

    def __init__(self, name, args=None):
        self.name = name
        self.args = [] if args is None else args

    def __call__(self, *args):
        return AspFunction(self.name, args)

    def symbol(self, positive=True):
        def argify(arg):
            if isinstance(arg, bool):
                return clingo.String(str(arg))
            elif isinstance(arg, int):
                return clingo.Number(arg)
            else:
                return clingo.String(str(arg))

        return clingo.Function(
            self.name, [argify(arg) for arg in self.args], positive=positive
        )

    def __getitem___(self, *args):
        self.args[:] = args
        return self

    def __str__(self):
        return "%s(%s)" % (self.name, ", ".join(str(_id(arg)) for arg in self.args))

    def __repr__(self):
        return str(self)


class AspFunctionBuilder(object):
    def __getattr__(self, name):
        return AspFunction(name)


fn = AspFunctionBuilder()


class Result:
    """
    Result of an ASP solve.
    """

    def __init__(self, asp=None):
        self.asp = asp
        self.satisfiable = None
        self.optimal = None
        self.warnings = None
        self.nmodels = 0

        # specs ordered by optimization level
        self.answers = []
        self.cores = []


class PyclingoDriver:
    def __init__(self, cores=True, out=None):
        """
        Driver for the Python clingo interface.
        Arguments:
            cores (bool): whether to generate unsatisfiable cores for better
                error reporting.
            out (file-like): optional stream to write a text-based ASP program
                for debugging or verification.
        """
        global clingo
        if out:
            self.out = out
        else:
            self.devnull()
        self.cores = cores

    def devnull(self):
        self.f = open(os.devnull, "w")
        self.out = self.f

    def __exit__(self):
        self.f.close()

    def title(self, name, char):
        self.out.write("\n")
        self.out.write("%" + (char * 76))
        self.out.write("\n")
        self.out.write("%% %s\n" % name)
        self.out.write("%" + (char * 76))
        self.out.write("\n")

    def h1(self, name):
        self.title(name, "=")

    def h2(self, name):
        self.title(name, "-")

    def newline(self):
        self.out.write("\n")

    def fact(self, head):
        """
        ASP fact (a rule without a body).
        """
        symbol = head.symbol() if hasattr(head, "symbol") else head

        self.out.write("%s.\n" % str(symbol))

        atom = self.backend.add_atom(symbol)
        self.backend.add_rule([atom], [], choice=self.cores)
        if self.cores:
            self.assumptions.append(atom)

    def solve(
        self,
        setup,
        nmodels=0,
        stats=False,
        logic_programs=None,
        facts_only=False,
    ):
        """
        Run the solver for a model and some number of logic programs
        """
        # logic programs to give to the solver
        logic_programs = logic_programs or []
        if not isinstance(logic_programs, list):
            logic_programs = [logic_programs]

        # Initialize the control object for the solver
        self.control = clingo.Control()
        self.control.configuration.solve.models = nmodels
        self.control.configuration.asp.trans_ext = "all"
        self.control.configuration.asp.eq = "5"
        self.control.configuration.configuration = "tweety"
        self.control.configuration.solve.parallel_mode = "2"
        self.control.configuration.solver.opt_strategy = "usc,one"

        # set up the problem -- this generates facts and rules
        self.assumptions = []
        with self.control.backend() as backend:
            self.backend = backend
            setup.setup(self)

        # If we only want to generate facts, cut out early
        if facts_only:
            return

        # read in provided logic programs
        for logic_program in logic_programs:
            self.control.load(logic_program)

        # Grounding is the first step in the solve -- it turns our facts
        # and first-order logic rules into propositional logic.
        self.control.ground([("base", [])])

        # With a grounded program, we can run the solve.
        result = Result()
        models = []  # stable models if things go well
        cores = []  # unsatisfiable cores if they do not

        def on_model(model):
            models.append((model.cost, model.symbols(shown=True, terms=True)))

        # Won't work after this, need to write files
        solve_kwargs = {
            "assumptions": self.assumptions,
            "on_model": on_model,
            "on_core": cores.append,
        }
        if clingo_cffi:
            solve_kwargs["on_unsat"] = cores.append
        solve_result = self.control.solve(**solve_kwargs)

        # once done, construct the solve result
        result.satisfiable = solve_result.satisfiable

        def stringify(x):
            if clingo_cffi:
                # Clingo w/ CFFI will throw an exception on failure
                try:
                    return x.string
                except RuntimeError:
                    return str(x)
            else:
                return x.string or str(x)

        if result.satisfiable:
            min_cost, best_model = min(models)
            result.answers = {}
            for sym in best_model:
                if sym.name not in result.answers:
                    result.answers[sym.name] = []
                result.answers[sym.name].append([stringify(a) for a in sym.arguments])

        elif cores:
            symbols = dict((a.literal, a.symbol) for a in self.control.symbolic_atoms)
            for core in cores:
                core_symbols = []
                for atom in core:
                    sym = symbols[atom]
                    core_symbols.append(sym)
                result.cores.append(core_symbols)

        if stats:
            print("Statistics:")
            logger.info(self.control.statistics)
        return result


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

    def __init__(self, lib1, lib2):
        """
        Create a driver to run a compatibility model test for two libraries.
        """
        # The driver will generate facts rules to generate an ASP program.
        self.driver = PyclingoDriver()
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


class FactGenerator(SolverBase):
    """
    Class to orchestrate fact generation (uses FactGeneratorSetup)
    """

    def __init__(self, lib, out=None, lib_basename=False):
        """
        Create a driver to run a compatibility model test for two libraries.
        """
        # The driver will generate facts rules to generate an ASP program.
        self.driver = PyclingoDriver(out=out or sys.stdout)
        self.setup = FactGeneratorSetup(lib, lib_basename=lib_basename)

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

    def add_library(self, lib, identifier=None):
        """
        Given a loaded Smeagle Model, generate facts for it.
        """
        lib_name = lib.get("library")
        if lib_name:
            if self.lib_basename:
                lib_name = os.path.basename(lib_name)
            self.gen.h2("Library: %s" % lib_name)

        # Don't replicate callsites used twice
        self.seen_callsites = set()

        # Set type lookup to current library
        self.types = lib.get("types", {})

        # Generate a fact for each location
        for loc in lib.get("locations", []):
            if "variables" in loc:
                for var in loc["variables"]:
                    self.generate_variable(lib, var, identifier)

            elif "function" in loc:
                self.generate_function(lib, loc.get("function"), identifier)
            elif "callsite" in loc:
                self.generate_function(
                    lib, loc.get("callsite"), identifier, callsite=True
                )

    def unwrap_type(self, func):
        """
        Unwrap the type
        """
        # Get underlying type from lookup
        if "type" not in func and "underlying_type" not in func:
            return None, {}

        while "underlying_type" in func:
            func = func["underlying_type"]

        # If the typ is already there, return it
        if "type" not in func:
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
            classes.add(next_type.get("class"))

            # we found a pointer or reference
            while "underlying_type" in next_type:
                next_type = next_type["underlying_type"]
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

    def generate_variable(self, lib, var, identifier=None):
        """
        Generate facts for a variable
        """
        if not var:
            return

        # Don't represent what we aren't sure about - no unknown types
        typ = self.unwrap_immediate_type(var)
        libname = os.path.basename(lib["library"])

        if not typ:
            return

        # Array we include the type in the top level
        self.parse_type(
            typ, libname, var["name"], variable=True, direction=var.get("direction")
        )

    def unwrap_location(self, param):
        """
        Unwrap the type
        """
        loc = location = param.get("location", "")

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
        Parse an underlying type fact.
        """
        offset = None
        original = param

        # Structs have types written out
        if "type" in param and isinstance(param["type"], dict):
            param = param["type"]

        if param.get("class") in ["Struct", "Class"]:
            for field in param.get("fields", []):
                self.parse_type(field, libname, top_name, variable=variable)
            return

        elif param.get("class") == "Function":
            # TODO note that we have another nesting of params here...
            param_type = "function"
        else:

            # Only get top level type (but recurse into pointers)
            offset = param.get("offset")

            if param.get("class") == "Void":
                param_type = param
            else:
                param_type, classes = self.unwrap_type(param)

            if not param_type:
                return

            # TODO need to handle array being parsed here...
            if param_type.get("class") in ["Struct", "Class"]:
                location = self.unwrap_location(param)
                for field in param_type.get("fields", []):

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
                    self.parse_type(field, libname, top_name, variable=variable)
                return

            # TODO need a location for pointer
            # abi_typelocation("lib.so","_Z11struct_funciP3Foo","Import","Opaque","(%rsi)+16").
            elif param_type.get("type") == "Recursive":
                direction = direction or "import"
                self.gen.fact(
                    fn.abi_typelocation(
                        libname,
                        top_name,
                        direction.capitalize(),
                        "Opaque",
                        "(" + param.get("location") + ")",
                    )
                )
                return

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
        elif variable:
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
        self.gen.fact(
            fn.abi_typelocation(
                libname,
                top_name,
                direction.capitalize(),
                param_type,
                location,
            )
        )

    def generate_function(self, lib, func, identifier=None, callsite=False):
        """
        Generate facts for a function
        """
        if not func:
            return

        # We cannot generate an atom for anything without a name
        if "name" not in func or func["name"] == "unknown":
            return

        libname = os.path.basename(lib["library"])
        seen = set()
        param_count = 0

        for param in func.get("parameters", []):
            self.parse_type(param, libname, func["name"])
            param_count += 1

            # If no identifier, skip the last step
            if not identifier:
                continue

            # This is only needed for the stability model to identify membership
            # of a particular function symbol, etc. with a library set (e.g., a or b)
            # Symbol, Type, Register, Direction
            args = [
                func["name"],
                param_type,
                location,
                param["direction"],
            ]

            fact = AspFunction("is_%s" % identifier, args=args)
            if fact not in seen:
                self.gen.fact(fact)
                seen.add(fact)

        # Parse the return type
        return_type = func.get("return")
        if not return_type or (return_type.get("class") == "Void" and param_count != 0):
            return
        self.parse_type(return_type, libname, func["name"])


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

    def __init__(self, lib, lib_basename=False):
        self.lib = lib

        # Use a basename instead of full path (for testing)
        self.lib_basename = lib_basename

    def setup(self, driver):
        """
        Setup to prepare for the solve.
        This base function provides fact generation for one library.
        """
        self.gen = driver
        self.gen.h1("Library Facts")
        self.add_library(self.lib)


class SmeagleRunner:

    # Currently we require a container
    # to be conservative, we require the user to export SMEAGLE_CONTAINER
    # in the environment instead of risking pulling a gazillion times.
    container = "docker://vanessa/smeagle:callsites"

    def __init__(self):
        """
        Load in Smeagle output files, write to database, and run solver.
        """
        self.stability_lp = os.path.join(here, "lp", "stability.lp")
        self.set_container()
        self.records = []

    def set_container(self):
        """
        Get the path to the container.
        """
        self.container = os.environ.get("SMEAGLE_CONTAINER")

    def check(self):
        """
        Ensure we have clingo and spython, return False is check fails.
        """
        if not self.container or not os.path.exists(self.container):
            logger.warning(
                "The container is not correctly set at SMEAGLE_CONTAINER, skipping running smeagle."
            )
            return False

        singularity = utils.which("singularity")
        if not singularity:
            logger.warning(
                "singularity is not installed, which is currently required for Smeagle."
            )
            return False

        if not clingo:
            logger.warning("We weren't able to import clingo. pip install clingo")
            return False
        return True

    def load_data(self, lib=None, data=None):
        """
        Common function to derive json data and a library.
        Each is optional to be provided, and we are flexible to accept either.
        """
        if not data and not lib:
            sys.exit("You must provide data or a library path.")
        if not data:
            data = self.get_smeagle_data(lib)

        if not lib:
            lib = data.get("library", "unknown")

        # Cut out early if we don't have the records
        if not data:
            sys.exit("Cannot find database entry for %s." % lib)
        return data, lib

    def generate_facts(self, lib=None, data=None, out=None, lib_basename=False):
        """
        Generate facts for one entry.
        """
        data, _ = self.load_data(lib, data)
        setup = FactGenerator(data, out=out, lib_basename=lib_basename)
        setup.solve()

    def get_smeagle_data(self, lib=None, data=None):
        """
        Get smeagle data
        """
        if not os.path.exists(lib):
            logger.exit("Library %s does not exist!" % lib)

        # Entrypoint is to Smeagle executable
        cmd = ["singularity", "run", self.container, "-l", lib]
        res = utils.run_command(cmd)
        if res["return_code"] != 0:
            logger.warning("Non-zero exit code for Smeagle %s" % res["message"])
        return res

    def stability_test(self, lib1, lib2, detail=False, data1=None, data2=None):
        """
        Run the stability test for two entries.
        """
        # We must have the stability program!
        if not os.path.exists(self.stability_lp):
            logger.exit("Logic program %s does not exist!" % self.stability_lp)

        # First get facts from smeagle
        lib1_res, lib1 = self.load_data(lib1, data1)
        lib2_res, lib2 = self.load_data(lib2, data2)

        # The spliced lib and original (assume failure)
        res = {"original_lib": lib1, "lib": lib2, "prediction": False}

        # If either result has nonzero return code, no go
        if lib1_res["return_code"] != 0 and lib2_res["return_code"] != 0:
            res.update(
                {
                    "return_code": -1,
                    "return_code_original": lib1_res["return_code"],
                    "return_code_splice": lib2_res["return_code"],
                    "message_original": lib1_res["message"],
                    "message_splice": lib2_res["message"],
                    "message": "Smeagle failed to generate facts for both libraries",
                }
            )
            return res

        # The original library running smeagle failed
        if lib1_res["return_code"] != 0:
            res.update(
                {
                    "return_code": -1,
                    "return_code_original": lib1_res["return_code"],
                    "return_code_splice": lib2_res["return_code"],
                    "message_original": lib1_res["message"],
                    "message": "Smeagle failed to generate facts for the original library",
                }
            )
            return res

        # The spliced library running smeagle failed
        if lib2_res["return_code"] != 0:
            res.update(
                {
                    "return_code": -1,
                    "return_code_original": lib1_res["return_code"],
                    "return_code_splice": lib2_res["return_code"],
                    "message_splice": lib2_res["message"],
                    "message": "Smeagle failed to generate facts for the spliced library",
                }
            )
            return res

        # Success case gets here
        try:
            original_data = json.loads(lib1_res["message"])
            splice_data = json.loads(lib2_res["message"])
        except:
            res["message"] = "One of the Smeagle results was not json load-able."
            return res

        # Setup and run the stability solver
        setup = StabilitySolver(original_data, splice_data)
        result = setup.solve(logic_programs=self.stability_lp)

        # Assuming anything missing is failure
        res["prediction"] = True

        # Keep a subset of data (missing stuff) for the result
        missing = {}
        for key in ["missing_imports", "missing_exports", "changed_callsites"]:
            if key in result:
                res["prediction"] = False
                missing[key] = result[key]

        # Add details about missing only if missing!
        if missing:
            res["message"] = missing
        return res
