// Fixture for admit-form detection. `tool_axioms` is a static scanner,
// so this file does not need to type-check — only the textual shapes
// matter.
// Line 4: admit with trailing `;`.
opaque symbol a1 : TYPE ≔
begin admit; end;

// Line 8: bare admit at end-of-block (no `;`).
opaque symbol a2 : TYPE ≔
begin
  reflexivity;
  admit
end;

// Line 16: admit inline inside `{ … }` subgoal.
opaque symbol a3 : TYPE ≔
begin apply ∨ₑ X { admit } { bar } end;

// Line 20: `admit` inside a comment must NOT be counted.
// admit
opaque symbol a4 : TYPE ≔
begin reflexivity; end;

// Line 24: `admitted` must NOT be counted.
opaque symbol a5 : TYPE ≔
begin admitted;
