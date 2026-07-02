// Inductive type fixture: used by test_symbols_inductive.
// `inductive` needs Prop's builtins to elaborate the auto-generated
// induction principle.
require open Stdlib.Set Stdlib.Prop;

inductive Foo : TYPE ≔
  | foo_a : Foo
  | foo_b : Foo → Foo;
