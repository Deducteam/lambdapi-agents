// Divisibility on natural numbers.

require open Stdlib.Set Stdlib.Prop Stdlib.FOL Stdlib.Eq Stdlib.Nat Stdlib.Bool;

symbol ∣ a b ≔ `∃ k, b = a * k;
notation ∣ infix 10;

// Divides introduction: witness k with b = a * k.
opaque symbol dvdᵢ [a b] (k : ℕ) : π (b = a * k) → π (a ∣ b) ≔
begin
  assume a b k h; refine ∃ᵢ k h;
end;

// Every number divides 0.
opaque symbol dvd_0 a : π (a ∣ 0) ≔
begin
  assume a; refine ∃ᵢ 0 _; reflexivity;
end;

// Reflexivity: a | a.
opaque symbol dvd_refl a : π (a ∣ a) ≔
begin
  assume a; refine ∃ᵢ 1 _; simplify; rewrite muln1; reflexivity;
end;

// 1 divides everything.
opaque symbol dvd_1 a : π (1 ∣ a) ≔
begin
  assume a; refine ∃ᵢ a _; reflexivity;
end;

// If a | b, then a | b * c.
opaque symbol dvd_mul_r [a b] c : π (a ∣ b) → π (a ∣ b * c) ≔
begin
  assume a b c h; refine ∃ₑ h _; assume k e;
  refine ∃ᵢ (k * c) _; simplify; rewrite e; rewrite mulnA; reflexivity;
end;

// If a | b, then a | c * b.
opaque symbol dvd_mul_l [a b] c : π (a ∣ b) → π (a ∣ c * b) ≔
begin
  assume a b c h; rewrite mulnC; refine @dvd_mul_r a b c h;
end;

// Divides is additive.
opaque symbol dvd_add [a b c] : π (a ∣ b) → π (a ∣ c) → π (a ∣ b + c) ≔
begin
  assume a b c hb hc;
  refine ∃ₑ hb _; assume kb eb;
  refine ∃ₑ hc _; assume kc ec;
  refine ∃ᵢ (kb + kc) _; simplify;
  rewrite eb; rewrite ec; rewrite mulnDr; reflexivity;
end;

// Divides is preserved by truncated subtraction.
opaque symbol dvd_sub [a b c] : π (a ∣ b) → π (a ∣ c) → π (a ∣ b - c) ≔
begin
  assume a b c hb hc;
  refine ∃ₑ hb _; assume kb eb;
  refine ∃ₑ hc _; assume kc ec;
  refine ∃ᵢ (kb - kc) _; simplify;
  rewrite eb; rewrite ec; rewrite mulnBr; reflexivity;
end;

// Transitivity: a | b and b | c imply a | c.
opaque symbol dvd_trans [a b c] : π (a ∣ b) → π (b ∣ c) → π (a ∣ c) ≔
begin
  assume a b c hab hbc;
  refine ∃ₑ hab _; assume k1 e1;
  refine ∃ₑ hbc _; assume k2 e2;
  refine ∃ᵢ (k1 * k2) _; simplify;
  rewrite e2; rewrite e1; rewrite mulnA; reflexivity;
end;
