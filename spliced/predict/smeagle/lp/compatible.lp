%=============================================================================
% A is a primary target binary/library and B is the scoped set of deps we want
% to use to satisfy what A needs.
%=============================================================================

% Imports of A must be a subset of exports of B
not_compatible(Symbol, Location, Type) :-
    abi_typelocation("a", Symbol, "Import", Type, Location),
    not abi_typelocation("b", Symbol, "Export", Type, Location).

% Imports of B must be a subset of exports of A
not_compatible(Symbol, Location, Type) :-
    abi_typelocation("b", Symbol, "Import", Type, Location),
    not abi_typelocation("a", Symbol, "Export", Type, Location).

#show not_compatible/3.
