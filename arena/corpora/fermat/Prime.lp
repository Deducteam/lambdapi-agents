// Primality predicate.

require open Stdlib.Set Stdlib.Prop Stdlib.FOL Stdlib.Eq Stdlib.Nat Stdlib.Bool;
require open Fermat.Divides;

// A prime is a natural p ≥ 2 whose only divisors are 1 and p.
symbol prime (p : ℕ) : Prop ≔
  istrue (2 ≤ p) ∧ (`∀ d, d ∣ p ⇒ (d = 1) ∨ (d = p));

// Projection: a prime is at least 2.
opaque symbol prime_ge2 [p] : π (prime p) → π (istrue (2 ≤ p)) ≔
begin
  assume p h; refine ∧ₑ₁ h;
end;

// Projection: a prime's divisors are 1 or p.
opaque symbol prime_dvd [p] : π (prime p) → Π d, π (d ∣ p) → π ((d = 1) ∨ (d = p)) ≔
begin
  assume p h d hd; refine ∧ₑ₂ h d hd;
end;

// A prime is positive.
opaque symbol prime_gt0 [p] : π (prime p) → π (istrue (0 < p)) ≔
begin
  assume p h;
  have t : π (istrue (2 ≤ p)) { refine prime_ge2 h };
  // 0 < p iff 1 ≤ p, and 2 ≤ p → 1 ≤ p.
  // 0 < p is 0+1 ≤ p, i.e. 1 ≤ p.
  refine @leq_trans 1 2 p _ t; simplify; apply ⊤ᵢ;
end;
