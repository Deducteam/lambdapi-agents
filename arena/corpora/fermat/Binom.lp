// Binomial coefficients via Pascal's rule.

require open Stdlib.Set Stdlib.Prop Stdlib.FOL Stdlib.Eq Stdlib.Nat Stdlib.Bool;
require open Fermat.Divides Fermat.Mod Fermat.Prime;

// Pascal's triangle. C n k = "n choose k".
symbol C : ℕ → ℕ → ℕ;

rule C _0 _0 ↪ _0 +1
with C _0 (_ +1) ↪ _0
with C ($n +1) _0 ↪ _0 +1
with C ($n +1) ($k +1) ↪ C $n $k + C $n ($k +1);

// Boundary: C n 0 = 1.
opaque symbol binC_n0 n : π (C n 0 = 1) ≔
begin
  induction { reflexivity } { assume n h; reflexivity };
end;

// Pascal's recurrence (restated as a rewrite target).
opaque symbol binC_rec n k : π (C (n +1) (k +1) = C n k + C n (k +1)) ≔
begin
  assume n k; reflexivity;
end;

// C n 1 = n.
opaque symbol binC_n1 n : π (C n 1 = n) ≔
begin
  induction
  { reflexivity }
  { assume n h;
    // C (n+1) 1 = C n 0 + C n 1 = 1 + n = n + 1.
    have p : π (C (n +1) 1 = C n 0 + C n 1) { reflexivity };
    rewrite p; rewrite binC_n0; rewrite h;
    // Goal: 1 + n = n + 1. True by addnC (in fact definitionally with +1).
    reflexivity;
  };
end;

// C 0 k = 0 for k ≥ 1.
opaque symbol binC_0_succ k : π (C 0 (k +1) = 0) ≔
begin
  assume k; reflexivity;
end;

// C n k = 0 when k > n. Stated as: for every offset k, C n ((n+k)+1) = 0.
// Proved by induction on n, with the inner ∀ k re-introduced each step.
opaque symbol binC_over n : Π k, π (C n ((n + k) +1) = 0) ≔
begin
  induction
  { assume k; reflexivity }
  { assume n ih k;
    // Goal: C (n+1) (((n+1)+k)+1) = 0, which normalizes to
    //       C (n+1) (((n+k)+1)+1) = 0. Pascal rule fires automatically.
    // Reduces to: C n ((n+k)+1) + C n (((n+k)+1)+1) = 0.
    simplify;
    have ih1 : π (C n ((n + k) +1) = 0) { refine ih k };
    have ih2 : π (C n (((n + k) +1) +1) = 0) { refine ih (k +1) };
    rewrite ih1; rewrite ih2; reflexivity;
  };
end;

// C n n = 1, derived via binC_over.
opaque symbol binC_nn n : π (C n n = 1) ≔
begin
  induction
  { reflexivity }
  { assume n h;
    // Pascal: C (n+1) (n+1) = C n n + C n (n+1).
    have p : π (C (n +1) (n +1) = C n n + C n (n +1)) { reflexivity };
    rewrite p; rewrite h;
    // Goal: 1 + C n (n+1) = 1. Use binC_over at offset 0.
    have q : π (C n (n +1) = 0) { refine binC_over n 0 };
    rewrite q; reflexivity;
  };
end;

// Absorption identity: (k+1) * C(n+1, k+1) = (n+1) * C(n, k).
// Proof: outer induction on n, inner induction on k.
opaque symbol binC_absorb : Π n k, π ((k +1) * C (n +1) (k +1) = (n +1) * C n k) ≔
begin
  induction
  { // n = 0
    induction
    { reflexivity }
    { assume k ih; reflexivity }
  }
  { assume n ih_n;
    induction
    { // k = 0. Goal: 1 * C(n+2, 1) = (n+2) * C(n+1, 0).
      simplify;
      have h1 : π (C n (0 +1) = n) { refine binC_n1 n };
      rewrite h1; rewrite binC_n0; rewrite muln1; rewrite (addnC 1 n);
      reflexivity;
    }
    { assume k ih_k;
      // Goal: (k+2) * C(n+2)(k+2) = (n+2) * C(n+1)(k+1).
      // Strategy: Pascal expansion + ih_n at k and (k+1).
      have hn1 : π ((k +1 +1) * C (n +1) ((k +1) +1) = (n +1) * C n (k +1)) { refine ih_n (k +1) };
      have hn0 : π ((k +1) * C (n +1) (k +1) = (n +1) * C n k) { refine ih_n k };
      // Pascal expansion of C((n+1)+1)((k+1)+1).
      have hC : π (C ((n +1) +1) ((k +1) +1) = C (n +1) (k +1) + C (n +1) ((k +1) +1)) { reflexivity };
      rewrite hC;
      // Goal: (k+1+1) * (C(n+1)(k+1) + C(n+1)((k+1)+1)) = (n+1+1) * C(n+1)(k+1).
      rewrite mulnDr (C (n +1) (k +1)) (C (n +1) ((k +1) +1)) (k +1 +1);
      // Goal: (k+1+1) * C(n+1)(k+1) + (k+1+1) * C(n+1)((k+1)+1) = (n+1+1) * C(n+1)(k+1).
      rewrite hn1;
      // Goal: (k+1+1) * C(n+1)(k+1) + (n+1) * C n (k+1) = (n+1+1) * C(n+1)(k+1).
      // Both sides reduce to (Y + ...) where Y = C(n+1)(k+1), so transport via feq.
      have inner : π ((k +1) * C (n +1) (k +1) + (n +1) * C n (k +1)
                       = (n +1) * C (n +1) (k +1))
        { rewrite hn0; symmetry; refine mulnDr (C n k) (C n (k +1)) (n +1) };
      refine feq (λ z, C (n +1) (k +1) + z) inner;
    }
  };
end;

// ─── Finite sums with binomial coefficients ──────────────────────────
// S n m a = Σ_{k=0}^m C(n, k) * a^k  (full partial sum, includes k=0 term)
symbol S : ℕ → ℕ → ℕ → ℕ;

rule S _ _0 _ ↪ _0 +1
with S $n ($m +1) $a ↪ S $n $m $a + C $n ($m +1) * $a ^ ($m +1);

// mid n m a = Σ_{k=1}^m C(n, k) * a^k  (excludes the k=0 term of S)
symbol mid : ℕ → ℕ → ℕ → ℕ;

rule mid _ _0 _ ↪ _0
with mid $n ($m +1) $a ↪ mid $n $m $a + C $n ($m +1) * $a ^ ($m +1);

// S = 1 + mid.
opaque symbol S_eq_1_mid n a : Π m, π (S n m a = 1 + mid n m a) ≔
begin
  assume n a; induction
  { reflexivity }
  { assume m ih; simplify; rewrite ih; reflexivity };
end;

// C n (n+1) = 0 specialised from binC_over, so S n (n+1) a = S n n a.
opaque symbol S_over n a : π (S n (n +1) a = S n n a) ≔
begin
  assume n a; simplify;
  have e : π (C n (n +1) = 0) { refine binC_over n 0 };
  rewrite e; simplify; reflexivity;
end;

// Key recurrence: Pascal-style, relating S at n+1 to S at n.
// S (n+1) (m+1) a = a * S n m a + S n (m+1) a.
opaque symbol S_rec n a : Π m,
  π (S (n +1) (m +1) a = a * S n m a + S n (m +1) a) ≔
begin
  assume n a; induction
  { // m = 0
    simplify; rewrite binC_n0 n; simplify; reflexivity;
  }
  { // m → m+1
    assume m ih;
    // Expose S (n+1) (m+1) a so `rewrite ih` can fire; a bare `simplify`
    // would eliminate it by cascading the S rule one step further.
    have h1 : π (S (n +1) ((m +1) +1) a
                 = S (n +1) (m +1) a + C (n +1) ((m +1) +1) * a ^ ((m +1) +1))
      { reflexivity };
    rewrite h1; rewrite ih; simplify;
    rewrite mulnDl (C n (m +1)) (C n ((m +1) +1)) (a * (a * a ^ m));
    rewrite mulnDr (S n m a) (C n (m +1) * (a * a ^ m)) a;
    rewrite mulnCA a (C n (m +1)) (a * a ^ m);
    rewrite addnAC (C n (m +1) * (a * a ^ m))
                   (C n (m +1) * (a * (a * a ^ m)))
                   (C n ((m +1) +1) * (a * (a * a ^ m)));
    rewrite addnAC (S n m a)
                   (C n (m +1) * (a * (a * a ^ m)))
                   (C n (m +1) * (a * a ^ m) + C n ((m +1) +1) * (a * (a * a ^ m)));
    reflexivity;
  };
end;

// Multiplicative step lemma: (a+1) * S n n a = S (n+1) (n+1) a.
opaque symbol S_step n a : π ((a +1) * S n n a = S (n +1) (n +1) a) ≔
begin
  assume n a;
  rewrite S_rec n a n;
  rewrite S_over n a;
  refine addnC (S n n a) (a * S n n a);
end;

// Binomial theorem: (a+1)^n = S n n a.
opaque symbol bin_thm a : Π n, π ((a +1) ^ n = S n n a) ≔
begin
  assume a; induction
  { reflexivity }
  { assume n ih;
    rewrite expnS (a +1) n;
    rewrite ih;
    refine S_step n a;
  };
end;

// Reshape for Fermat: (a+1)^(n+1) = a^(n+1) + 1 + mid (n+1) n a.
opaque symbol binomial_expand n a :
  π ((a +1) ^ (n +1) = a ^ (n +1) + 1 + mid (n +1) n a) ≔
begin
  assume n a;
  rewrite bin_thm a (n +1);
  rewrite S_eq_1_mid (n +1) a (n +1);
  simplify;
  have eover : π (C n (n +1) = 0) { refine binC_over n 0 };
  rewrite eover; rewrite binC_nn n; simplify;
  rewrite addnC; reflexivity;
end;
