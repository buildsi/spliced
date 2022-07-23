# Spliced to print Asp

## Single Facts

This is an example of using spliced just to print asp facts to the terminal,
which is an easy thing it can do! We start with [smeagle-output.json](smeagle-output.json),
load it, and then use the same SmeagleRunner to print facts to the terminal.

```python
import spliced.utils as utils
import spliced.predict.smeagle as smeagle

cli = smeagle.SmeagleRunner()
data = utils.read_json("smeagle-output.json")

# We can accept a path (will run smeagle) or the raw data, so
# it is important to provide a kwarg here!
cli.generate_facts(data=data)
```
```bash
%============================================================================
% Library Facts
%============================================================================

%----------------------------------------------------------------------------
% Library: libtest.so
%----------------------------------------------------------------------------
abi_typelocation("libtest.so","_Z7bigcallllllln","a","Integer","%rdi","import","0").
abi_typelocation("libtest.so","_Z7bigcallllllln","b","Integer","%rsi","import","0").
abi_typelocation("libtest.so","_Z7bigcallllllln","c","Integer","%rdx","import","0").
abi_typelocation("libtest.so","_Z7bigcallllllln","d","Integer","%rcx","import","0").
abi_typelocation("libtest.so","_Z7bigcallllllln","e","Integer","%r8","import","0").
abi_typelocation("libtest.so","_Z7bigcallllllln","f","Integer","framebase+8","import","0").
```

This is provided in a little [generate-facts.py](generate-facts.py) courtesy script.

```bash
$ python generate-facts.py smeagle-output.json
```
```bash
%============================================================================
% Library Facts
%============================================================================

%----------------------------------------------------------------------------
% Library: libtest.so
%----------------------------------------------------------------------------
abi_typelocation("libtest.so","_Z7bigcallllllln","a","Integer","%rdi","import","0").
abi_typelocation("libtest.so","_Z7bigcallllllln","b","Integer","%rsi","import","0").
abi_typelocation("libtest.so","_Z7bigcallllllln","c","Integer","%rdx","import","0").
abi_typelocation("libtest.so","_Z7bigcallllllln","d","Integer","%rcx","import","0").
abi_typelocation("libtest.so","_Z7bigcallllllln","e","Integer","%r8","import","0").
abi_typelocation("libtest.so","_Z7bigcallllllln","f","Integer","framebase+8","import","0").
```


## Simulating a Solve

### Stability Test
If you want to simulate a stability test, first run the script, providing two libs as "A" (original)
and "B" (comparison). Here are examples (both ways) with our math library:

```bash
$ python stability-test.py ../../../compspec/compspec-python/examples/dwarf/lib/libmath/v1/lib.v1.so  ../../../compspec/compspec-python/examples/dwarf/lib/libmath/v2/lib.v2.so

Missing Imports
---------------
 _ZN11MathLibrary10Arithmetic3AddEdd Float64 %xmm0
 _ZN11MathLibrary10Arithmetic3AddEdd Float64 %xmm1

Missing Exports
---------------
 _ZN11MathLibrary10Arithmetic3AddEdd Float64 %xmm0
```
```bash
$ python stability-test.py ../../../compspec/compspec-python/examples/dwarf/lib/libmath/v2/lib.v2.so  ../../../compspec/compspec-python/examples/dwarf/lib/libmath/v1/lib.v1.so

Missing Imports
---------------
 _ZN11MathLibrary10Arithmetic3AddEii Integer32 %rdi
 _ZN11MathLibrary10Arithmetic3AddEii Integer32 %rsi

Missing Exports
---------------
 _ZN11MathLibrary10Arithmetic3AddEii Integer32 %rax
```

This will generate A.asp and B.asp. To run this more manually with clingo, you can copy your stability model here:

```bash
$ cp ../../spliced/predict/smeagle/lp/stability.lp .
```
and run these in a clingo container (or via a local clingo install) like:

```bash
$ docker run -v $PWD:/data --rm -it ghcr.io/autamus/clingo bash
$ cd /data
$ clingo --out-ifs=\\n A.asp B.asp stability.lp
```
And you'll get the same answer:

```bash
clingo version 5.5.1
Reading from A.asp ...
Solving...
Answer: 1
missing_exports("_ZN11MathLibrary10Arithmetic3AddEii","Integer32","%rax")
missing_imports("_ZN11MathLibrary10Arithmetic3AddEii","Integer32","%rdi")
missing_imports("_ZN11MathLibrary10Arithmetic3AddEii","Integer32","%rsi")
SATISFIABLE

Models       : 1
Calls        : 1
Time         : 0.003s (Solving: 0.00s 1st Model: 0.00s Unsat: 0.00s)
CPU Time     : 0.003s
```

### Compatible Test

This is the test that smeagle is doing for our experiment, since we are loading
all symbols within a space for a library A and dependencies (B) (to the scoped set we
can find).


```bash
$ docker run -v $PWD:/data --rm -it ghcr.io/autamus/clingo bash
$ cd /data
$ clingo --out-ifs=\\n ccache-swig.asp compatible.lp 
```

