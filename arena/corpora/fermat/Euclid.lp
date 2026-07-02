// Strong induction, division-with-remainder, and Euclid's lemma for primes.

require open Stdlib.Set Stdlib.Prop Stdlib.FOL Stdlib.Eq Stdlib.Nat Stdlib.Bool;
require open Fermat.Divides Fermat.Prime Fermat.Binom;

// ─── Strong (course-of-values) induction on ℕ ────────────────────────────
// Auxiliary: ∀ n, ∀ m < n, P m, by ordinary induction on n.
opaque symbol cov_aux (P : ℕ → Prop)
  (h : Π n, (Π m, π (istrue (m < n)) → π (P m)) → π (P n))
  : Π n, Π m, π (istrue (m < n)) → π (P m) ≔
begin
  assume P h; induction
  { // n = 0: m < 0 absurd.
    assume m hm; apply ⊥ₑ; refine ltn0 m hm
  }
  { // n+1: m < n+1 means m ≤ n. Either m = n (use h) or m < n (use IH).
    assume n ih m hm;
    have hle : π (istrue (m ≤ n)) { refine letnS m n hm };
    apply ∨ₑ (∧ₑ₁ (leq_eqVlt m n) hle)
    { assume e; rewrite e; refine h n ih }
    { assume hlt; refine ih m hlt };
  };
end;

opaque symbol strong_ind (P : ℕ → Prop)
  (h : Π n, (Π m, π (istrue (m < n)) → π (P m)) → π (P n))
  : Π n, π (P n) ≔
begin
  assume P h n; refine cov_aux P h (n +1) n (ltnSn n);
end;

// ─── Division with remainder ────────────────────────────────────────────
// ∀ a > 0, ∀ n, ∃ q r, n = q * a + r ∧ r < a. Proved by induction on n.
opaque symbol divmod a (ha : π (istrue (_0 < a))) :
  Π n, π (`∃ q, `∃ r, (n = q * a + r) ∧ istrue(r < a)) ≔
begin
  assume a ha; induction
  { // n = 0
    refine ∃ᵢ 0 _; refine ∃ᵢ 0 _;
    refine ∧ᵢ _ ha; reflexivity;
  }
  { // n + 1
    assume n ih;
    refine ∃ₑ ih _; assume q hq;
    refine ∃ₑ hq _; assume r hcase;
    have eq : π (n = q * a + r) { refine ∧ₑ₁ hcase };
    have hr : π (istrue (r +1 ≤ a)) { refine ∧ₑ₂ hcase };
    apply ∨ₑ (∧ₑ₁ (leq_eqVlt (r +1) a) hr)
    { // r+1 = a: take (q+1, 0)
      assume e2;
      refine ∃ᵢ (q +1) _; refine ∃ᵢ 0 _;
      refine ∧ᵢ _ ha;
      rewrite eq; rewrite addn0; rewrite mulSnr; symmetry;
      rewrite left e2; reflexivity;
    }
    { // r+1 < a: take (q, r+1)
      assume hr2;
      refine ∃ᵢ q _; refine ∃ᵢ (r +1) _;
      refine ∧ᵢ _ hr2;
      rewrite eq; reflexivity;
    };
  };
end;

// ─── Helpers for Euclid ────────────────────────────────────────────────
// If a divides p and 1 < a < p, then prime p is contradicted.
opaque symbol prime_no_proper_divisor [p] (hp : π (prime p)) [a]
  (h1 : π (istrue (1 < a))) (hlt : π (istrue (a < p))) (hdvd : π (a ∣ p))
  : π ⊥ ≔
begin
  assume p hp a h1 hlt hdvd;
  apply ∨ₑ (prime_dvd hp a hdvd)
  { assume e1;
    refine ltnn 1 (ind_eq (eq_sym e1) (λ x, istrue (1 < x)) h1) }
  { assume e2;
    refine ltnn p (ind_eq (eq_sym e2) (λ x, istrue (x < p)) hlt) };
end;

// ─── Euclid's lemma for primes ────────────────────────────────────────
opaque symbol euclid_prime [p] (hp : π (prime p)) :
  Π a, π (istrue (_0 < a)) → π (istrue (a < p)) →
  Π b, π (p ∣ a * b) → π (p ∣ b) ≔
begin
  assume p hp;
  refine strong_ind (λ a, istrue (_0 < a) ⇒ istrue (a < p) ⇒
                          `∀ b, p ∣ a * b ⇒ p ∣ b) _;
  assume a ih ha hap b hab;
  // Split: a = 1 (base) or a > 1 (recursive).
  have hsplit : π ((1 = a) ∨ istrue (1 < a)) {
    refine ∧ₑ₁ (leq_eqVlt 1 a) ha
  };
  apply ∨ₑ hsplit
  { // a = 1: e1 : 1 = a, hab : p ∣ a*b. ind_eq e1 transports to p ∣ 1*b = p ∣ b.
    assume e1;
    refine ind_eq e1 (λ x, p ∣ x * b) hab
  }
  { // a > 1: use divmod p a.
    assume hagt1;
    refine ∃ₑ (divmod a ha p) _; assume q hq;
    refine ∃ₑ hq _; assume r hcase;
    have eq_p : π (p = q * a + r) { refine ∧ₑ₁ hcase };
    have hr_lt_a : π (istrue (r < a)) { refine ∧ₑ₂ hcase };
    // r = 0 → a ∣ p contradicts prime; r > 0 → use IH.
    have hsplit_r : π ((_0 = r) ∨ istrue (_0 < r)) {
      refine ∧ₑ₁ (leq_eqVlt _0 r) (leq0n r)
    };
    apply ∨ₑ hsplit_r
    { // r = 0: a ∣ p, contradiction.
      assume e_r;
      have a_dvd_p : π (a ∣ p) {
        refine ∃ᵢ q _;
        rewrite eq_p; rewrite left e_r;
        symmetry; refine mulnC a q
      };
      refine @⊥ₑ (p ∣ b)
        (@prime_no_proper_divisor p hp a hagt1 hap a_dvd_p)
    }
    { // r > 0: derive p | r*b, then IH.
      assume hr_pos;
      have hrp : π (istrue (r < p)) { refine ltn_trans r a p hr_lt_a hap };
      have h_pb_eq : π (p * b = q * a * b + r * b) {
        rewrite eq_p; refine mulnDl (q * a) r b
      };
      have h_rb_eq : π (r * b = p * b - q * a * b) {
        rewrite h_pb_eq;
        rewrite addnC (q * a * b) (r * b);
        symmetry; refine addnK (r * b) (q * a * b)
      };
      have h_p_pb : π (p ∣ p * b) {
        refine @dvd_mul_r p p b (dvd_refl p)
      };
      have h_p_qab : π (p ∣ q * a * b) {
        have h1 : π (p ∣ q * (a * b)) { refine @dvd_mul_l p (a * b) q hab };
        have h2 : π (q * (a * b) = q * a * b) { symmetry; refine mulnA q a b };
        refine ind_eq (eq_sym h2) (λ x, p ∣ x) h1
      };
      have h_p_rb : π (p ∣ r * b) {
        rewrite h_rb_eq; refine @dvd_sub p (p * b) (q * a * b) h_p_pb h_p_qab
      };
      refine ih r hr_lt_a hr_pos hrp b h_p_rb
    };
  };
end;

// ─── Prime divides "middle" binomial coefficients ─────────────────────
// For prime p = n+1 and 0 < k+1 < p, p divides C p (k+1).
// Proof: binC_absorb gives (k+1)*C(n+1)(k+1) = (n+1)*C n k, so p ∣ k+1 * C ... .
// Then Euclid's lemma with gcd(p, k+1)=1 (since k+1 < p) gives p ∣ C ... .
opaque symbol binC_dvd_p [n] (hp : π (prime (n +1))) :
  Π k, π (istrue ((k +1) < (n +1))) → π ((n +1) ∣ C (n +1) (k +1)) ≔
begin
  assume n hp k hk;
  have h_abs : π ((k +1) * C (n +1) (k +1) = (n +1) * C n k) {
    refine binC_absorb n k
  };
  have h_dvd_prod : π ((n +1) ∣ (k +1) * C (n +1) (k +1)) {
    rewrite h_abs; refine ∃ᵢ (C n k) _; reflexivity
  };
  have h_kpos : π (istrue (_0 < k +1)) { simplify; refine leq0n k };
  refine euclid_prime hp (k +1) h_kpos hk (C (n +1) (k +1)) h_dvd_prod;
end;

// ─── Prime divides the middle-sum ──────────────────────────────────────
// For prime (n+1) and m ≤ n, (n+1) divides Σ_{k=1}^m C(n+1, k) * a^k.
opaque symbol mid_dvd [n] (hp : π (prime (n +1))) a :
  Π m, π (istrue (m ≤ n)) → π ((n +1) ∣ mid (n +1) m a) ≔
begin
  assume n hp a; induction
  { // m = 0: mid (n+1) 0 a = 0.
    assume htop; simplify; refine dvd_0 (n +1);
  }
  { // m → m+1: with (m+1) ≤ n, we get m ≤ n (IH) and m+1 < n+1 (binC_dvd_p).
    assume m ih hm;
    have hm_le : π (istrue (m ≤ n))
      { refine @leq_trans m (m +1) n (leqnSn m) hm };
    refine @dvd_add (n +1) (mid (n +1) m a) (C (n +1) (m +1) * a ^ (m +1)) _ _
    { refine ih hm_le }
    { refine @dvd_mul_r (n +1) (C (n +1) (m +1)) (a ^ (m +1)) _;
      refine binC_dvd_p hp m hm };
  };
end;
