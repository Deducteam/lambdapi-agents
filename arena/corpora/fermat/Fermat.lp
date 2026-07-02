// Fermat's little theorem: reduced from the Freshman's dream mod p.

require open Stdlib.Set Stdlib.Prop Stdlib.FOL Stdlib.Eq Stdlib.Nat Stdlib.Bool;
require open Fermat.Divides Fermat.Mod Fermat.Prime Fermat.Binom Fermat.Euclid;

// The Freshman's dream mod p: (a+1)^p ≡ a^p + 1 [mod p].
symbol freshman_dream (p : ℕ) : Prop ≔
  `∀ a, cong p ((a +1) ^ p) ((a ^ p) + 1);

// Fermat reduction: from the Freshman's dream and p > 0,
// deduce Fermat's little theorem a^p ≡ a [mod p] by induction on a.
opaque symbol fermat_from_freshman p :
  π (freshman_dream p) → π (istrue (0 < p)) →
  Π a, π (cong p (a ^ p) a) ≔
begin
  assume p hFD hp;
  induction
  { // Base: a = 0. Goal: cong p (0^p) 0.
    // Using exp0n: for p > 0, 0^p = 0.
    have e : π (0 ^ p = 0) { refine exp0n p hp };
    rewrite e; refine cong_refl p 0;
  }
  { // Step: assume cong p (a^p) a. Show cong p ((a+1)^p) (a+1).
    assume a ih;
    have fd : π (cong p ((a +1) ^ p) (a ^ p + 1)) { refine hFD a };
    have step2 : π (cong p (a ^ p + 1) (a + 1))
      { refine @cong_add p (a ^ p) a 1 1 ih (cong_refl p 1) };
    refine @cong_trans p ((a +1) ^ p) (a ^ p + 1) (a + 1) fd step2;
  };
end;

// ─── Freshman's dream for primes ──────────────────────────────────────
// binomial_expand gives (a+1)^(n+1) = a^(n+1) + 1 + mid (n+1) n a,
// and mid_dvd gives (n+1) ∣ mid (n+1) n a. Package into a cong.
opaque symbol freshman_dream_prime [n] (hp : π (prime (n +1))) :
  π (freshman_dream (n +1)) ≔
begin
  assume n hp a;
  rewrite binomial_expand n a;
  have hmid : π ((n +1) ∣ mid (n +1) n a) { refine mid_dvd hp a n (≤_refl n) };
  refine ∃ₑ hmid _; assume T hT;
  refine ∃ᵢ 0 _; refine ∃ᵢ T _;
  simplify; rewrite hT; rewrite mulnC (n +1) T; reflexivity;
end;

// ─── Fermat's little theorem, unconditional ───────────────────────────
// For any prime p, a^p ≡ a (mod p). Case-split on p: p = 0 contradicts
// prime_gt0; p = n+1 feeds freshman_dream_prime into fermat_from_freshman.
opaque symbol fermat p (hp : π (prime p)) (a : ℕ) : π (cong p (a ^ p) a) ≔
begin
  induction
  { // p = 0: prime_gt0 would give istrue (0 < 0), an absurdity.
    assume hp a;
    refine @⊥ₑ (cong _0 (a ^ _0) a) (ltnn _0 (prime_gt0 hp));
  }
  { // p = n+1: apply the freshman-dream route.
    assume n _ih hp a;
    refine @fermat_from_freshman (n +1) (freshman_dream_prime hp) (prime_gt0 hp) a;
  };
end;
