%=============================================================================
% A and B are two instances of the same library. Can B replace A?
%=============================================================================


missing_exports(Symbol, Type, Location) :-

    % The symbol is exported for A
    abi_typelocation("a", Symbol, "Export", Type, Location),
    
    % And it's not exported for B
    not abi_typelocation("b", Symbol, "Export", Type, Location).

% -and- Imported({B}) is a subset of Imported({A}) U Exported(Dependencies(B))
% This is not tractable here so we will derive this list but not use it.
missing_imports(Symbol, Type, Location) :-
    abi_typelocation("a", Symbol, "Import", Type, Location),
    not abi_typelocation("b", Symbol, "Import", Type, Location).
    
#show missing_imports/3.
#show missing_exports/3.
