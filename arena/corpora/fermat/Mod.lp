// Congruence modulo n on natural numbers.

require open Stdlib.Set Stdlib.Prop Stdlib.FOL Stdlib.Eq Stdlib.Nat Stdlib.Bool;
require open Fermat.Divides;

// a ≡ b [mod n] iff there exist naturals x y with a + x*n = b + y*n.
symbol cong (n a b : ℕ) : Prop ≔ `∃ x, `∃ y, a + x * n = b + y * n;

// Reflexivity.
opaque symbol cong_refl n a : π (cong n a a) ≔
begin
  assume n a; refine ∃ᵢ 0 _; refine ∃ᵢ 0 _; simplify; reflexivity;
end;

// Symmetry.
opaque symbol cong_sym [n a b] : π (cong n a b) → π (cong n b a) ≔
begin
  assume n a b h; refine ∃ₑ h _; assume x hx;
  refine ∃ₑ hx _; assume y e;
  refine ∃ᵢ y _; refine ∃ᵢ x _;
  symmetry; refine e;
end;

// Addition congruence: a ≡ b and c ≡ d imply a + c ≡ b + d mod n.
opaque symbol cong_add [n a b c d] :
  π (cong n a b) → π (cong n c d) → π (cong n (a + c) (b + d)) ≔
begin
  assume n a b c d hab hcd;
  refine ∃ₑ hab _; assume x1 hx1; refine ∃ₑ hx1 _; assume y1 e1;
  refine ∃ₑ hcd _; assume x2 hx2; refine ∃ₑ hx2 _; assume y2 e2;
  refine ∃ᵢ (x1 + x2) _; refine ∃ᵢ (y1 + y2) _; simplify;
  rewrite mulnDl; rewrite mulnDl;
  // Goal: a + c + (x1*n + x2*n) = b + d + (y1*n + y2*n)
  // Rearrange to match feq2 form.
  rewrite addnAC c (x1 * n) (x2 * n);
  // Now LHS: a + (x1*n + (c + x2*n)) after reassoc.
  rewrite addnAC d (y1 * n) (y2 * n);
  refine feq2 (λ u v, u + v) e1 e2;
end;

// Multiplication by a constant on the right preserves congruence.
opaque symbol cong_mul_r [n a b] c :
  π (cong n a b) → π (cong n (a * c) (b * c)) ≔
begin
  assume n a b c h; refine ∃ₑ h _; assume x hx; refine ∃ₑ hx _; assume y e;
  refine ∃ᵢ (x * c) _; refine ∃ᵢ (y * c) _; simplify;
  // Goal: a*c + (x*c)*n = b*c + (y*c)*n.
  rewrite left mulnAC x n c;
  rewrite left mulnAC y n c;
  // Now: a*c + (x*n)*c = b*c + (y*n)*c.
  rewrite left mulnDl a (x * n) c;
  rewrite left mulnDl b (y * n) c;
  // Now: (a + x*n)*c = (b + y*n)*c.
  refine feq (λ z, z * c) e;
end;

// Multiplication by a constant on the left preserves congruence.
opaque symbol cong_mul_l [n a b] c :
  π (cong n a b) → π (cong n (c * a) (c * b)) ≔
begin
  assume n a b c h; rewrite mulnC c a; rewrite mulnC c b;
  refine @cong_mul_r n a b c h;
end;

// Full multiplication congruence: a ≡ b and c ≡ d imply a*c ≡ b*d mod n.
opaque symbol cong_mul [n a b c d] :
  π (cong n a b) → π (cong n c d) → π (cong n (a * c) (b * d)) ≔
begin
  assume n a b c d hab hcd;
  have s1 : π (cong n (a * c) (b * c)) { refine @cong_mul_r n a b c hab };
  have s2 : π (cong n (b * c) (b * d)) { refine @cong_mul_l n c d b hcd };
  // Need transitivity, declared below, so forward-reference.
  refine ∃ₑ s1 _; assume x1 hx1; refine ∃ₑ hx1 _; assume y1 e1;
  refine ∃ₑ s2 _; assume x2 hx2; refine ∃ₑ hx2 _; assume y2 e2;
  refine ∃ᵢ (x1 + x2) _; refine ∃ᵢ (y1 + y2) _; simplify;
  rewrite mulnDl; rewrite mulnDl;
  have H1 : π (a * c + (x1 * n + x2 * n) = b * c + (y1 * n + x2 * n))
    { refine feq (λ z, z + (x2 * n)) e1 };
  have H2 : π (b * c + (x2 * n + y1 * n) = b * d + (y2 * n + y1 * n))
    { refine feq (λ z, z + (y1 * n)) e2 };
  rewrite H1;
  rewrite addnC (y1 * n) (x2 * n);
  rewrite H2;
  rewrite addnC (y2 * n) (y1 * n); reflexivity;
end;

// If n divides a, then a ≡ 0 mod n.
opaque symbol cong_from_dvd [n a] : π (n ∣ a) → π (cong n a 0) ≔
begin
  assume n a h; refine ∃ₑ h _; assume k e;
  // e : a = n * k. Want: a + x*n = 0 + y*n for some x, y.
  // Take x = 0, y = k: a + 0*n = 0 + k*n, i.e., a = k*n. Use mulnC.
  refine ∃ᵢ 0 _; refine ∃ᵢ k _; simplify;
  rewrite e; rewrite mulnC; reflexivity;
end;

// Transitivity.
opaque symbol cong_trans [n a b c] :
  π (cong n a b) → π (cong n b c) → π (cong n a c) ≔
begin
  assume n a b c hab hbc;
  refine ∃ₑ hab _; assume x1 hx1; refine ∃ₑ hx1 _; assume y1 e1;
  refine ∃ₑ hbc _; assume x2 hx2; refine ∃ₑ hx2 _; assume y2 e2;
  refine ∃ᵢ (x1 + x2) _; refine ∃ᵢ (y1 + y2) _; simplify;
  rewrite mulnDl; rewrite mulnDl;
  // Goal: a + (x1 * n + x2 * n) = c + (y1 * n + y2 * n).
  have H1 : π (a + (x1 * n + x2 * n) = b + (y1 * n + x2 * n))
    { refine feq (λ z, z + (x2 * n)) e1 };
  have H2 : π (b + (x2 * n + y1 * n) = c + (y2 * n + y1 * n))
    { refine feq (λ z, z + (y1 * n)) e2 };
  rewrite H1;
  // Goal: b + (y1*n + x2*n) = c + (y1*n + y2*n).
  rewrite addnC (y1 * n) (x2 * n);
  // Goal: b + (x2*n + y1*n) = c + (y1*n + y2*n).
  rewrite H2;
  // Goal: c + (y2*n + y1*n) = c + (y1*n + y2*n).
  rewrite addnC (y2 * n) (y1 * n); reflexivity;
end;
