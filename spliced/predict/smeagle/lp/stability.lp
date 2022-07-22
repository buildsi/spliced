%=============================================================================
% A and B are two instances of the same library. Can B replace A?
%=============================================================================

% Let Exported(BinSet) be a set of interface/type/locations triples exported by a set of binaries
% Let Imported(BinSet) be a set of interface/type/location triples imported by some binary
% Mark symbols as exported or imported for each library
% We assume that we don't miss params based on name because the types/locations are unique
exported(Namespace, Library, Symbol, Type, Location) :- 
    abi_typelocation(Namespace, Library, Symbol, Type, "Export", Location).

imported(Namespace, Library, Symbol, Type, Location) :- 
    abi_typelocation(Namespace, Library, Symbol, Type, "Import", Location).

% Let Dependencies(Bin) be the set of binaries that binary Bin depends on. 
% We don't have this represented yet?

% - We’ll say B can safely replace A if: Exported({A}) is a subset of Exported({B})
% This also says that there can't be any symbols in A not in B
missing_exports(Symbol, Library, Type, Location) :-

    % The symbol is exported for A
    exported("A", Library, Symbol, Type, Location),
    
    % And it's not exported for B
    not exported("B", Library, Symbol, Type, Location).


% -and- Imported({B}) is a subset of Imported({A}) U Exported(Dependencies(B))
% This is not tractable here so we will derive this list but not use it.
missing_imports(Symbol, Library, Type, Location) :-

    % The symbol is imported for A
    imported("A", Library, Symbol, Type, Location),
    
    % And it's not imported for B
    not exported("B", Library, Symbol, Type, Location).

#show missing_imports/4.
#show missing_exports/4.
