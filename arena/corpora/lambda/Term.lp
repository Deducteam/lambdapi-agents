// Untyped λ-calculus, de Bruijn indices. Lift, substitution, key lemmas.

require open Stdlib.Set Stdlib.Prop Stdlib.FOL Stdlib.Eq Stdlib.Nat;

// ---------------------------------------------------------------------------
// Terms
// ---------------------------------------------------------------------------

inductive Term : TYPE ≔
  | Var : ℕ → Term
  | App : Term → Term → Term
  | Lam : Term → Term;

constant symbol term : Set;
rule τ term ↪ Term;

// ---------------------------------------------------------------------------
// Lifting
// liftIdx k i = i   if i < k
//             = i+1 if i ≥ k
// encoded by nested recursion on (k, i).
// ---------------------------------------------------------------------------

symbol liftIdx : ℕ → ℕ → ℕ;
rule liftIdx _0 $i ↪ $i +1
with liftIdx ($k +1) _0 ↪ _0
with liftIdx ($k +1) ($i +1) ↪ (liftIdx $k $i) +1;

symbol lift : ℕ → Term → Term;
rule lift $k (Var $i) ↪ Var (liftIdx $k $i)
with lift $k (App $s $t) ↪ App (lift $k $s) (lift $k $t)
with lift $k (Lam $t) ↪ Lam (lift ($k +1) $t);

// ---------------------------------------------------------------------------
// Substitution
// substVar k u i = Var i      if i < k
//                = u           if i = k
//                = Var (i-1)   if i > k
//
// The outer `subst` passes `u` unchanged under binders; each k→k+1 step
// inside substVar introduces a `lift 0`, so a Var found at depth d under
// the target appears as lift 0 applied d times to u — equivalent to the
// classical "lift u at each binder crossing" definition.
// ---------------------------------------------------------------------------

symbol substVar : ℕ → Term → ℕ → Term;
rule substVar _0 $u _0 ↪ $u
with substVar _0 _ ($i +1) ↪ Var $i
with substVar ($k +1) _ _0 ↪ Var _0
with substVar ($k +1) $u ($i +1) ↪ lift _0 (substVar $k $u $i);

symbol subst : ℕ → Term → Term → Term;
rule subst $k $u (Var $i) ↪ substVar $k $u $i
with subst $k $u (App $s $t) ↪ App (subst $k $u $s) (subst $k $u $t)
with subst $k $u (Lam $t) ↪ Lam (subst ($k +1) $u $t);

// ---------------------------------------------------------------------------
// Basic lift lemmas
// ---------------------------------------------------------------------------

// lift congruence for variables: stated separately since liftIdx is an
// arithmetic symbol.

opaque symbol lift_Var k i : π (lift k (Var i) = Var (liftIdx k i)) ≔
begin
  assume k i; reflexivity
end;

// Key fact about liftIdx at threshold _0: every index is shifted by 1.
opaque symbol liftIdx0 i : π (liftIdx _0 i = i +1) ≔
begin
  assume i; reflexivity
end;

// liftIdx ($k +1) doesn't touch _0.
opaque symbol liftIdx_S0 k : π (liftIdx (k +1) _0 = _0) ≔
begin
  assume k; reflexivity
end;

// ---------------------------------------------------------------------------
// Core lift / subst cancellation:
//   subst k w (lift k t) = t
// via substVar (liftIdx k i) = Var i.  Nested induction on k, then i.
// ---------------------------------------------------------------------------

opaque symbol substVar_liftIdx w : Π k i, π (substVar k w (liftIdx k i) = Var i) ≔
begin
  assume w;
  induction
  { // k = 0: liftIdx 0 i = i +1, substVar 0 w (i+1) = Var i
    assume i; reflexivity }
  { // k = k' +1
    assume k' IHk;
    induction
    { // i = 0
      reflexivity }
    { // i = i' +1
      assume i' IHi;
      simplify; rewrite IHk; reflexivity } }
end;

opaque symbol subst_lift : Π t k w, π (subst k w (lift k t) = t) ≔
begin
  induction
  { // Var
    assume i k w; apply substVar_liftIdx w k i }
  { // App
    assume s IHs t IHt k w;
    simplify; rewrite IHs; rewrite IHt; reflexivity }
  { // Lam
    assume t IH k w;
    simplify; rewrite IH; reflexivity }
end;

// ---------------------------------------------------------------------------
// Interchange of two lifts.
// Shape: lift m (lift (n+m) t) = lift ((n+m) +1) (lift m t)
// Rationale: having n on the LEFT of + means n + (m+1) reduces to (n+m)+1
// under Stdlib's right-associativity rule, keeping the induction clean.
// ---------------------------------------------------------------------------

opaque symbol liftIdx_liftIdx : Π m n i,
  π (liftIdx m (liftIdx (n + m) i) = liftIdx ((n + m) +1) (liftIdx m i)) ≔
begin
  induction
  { // m = 0
    assume n i; reflexivity }
  { // m = m' +1
    assume m' IHm n;
    induction
    { // i = 0
      reflexivity }
    { // i = i' +1
      assume i' IHi;
      simplify; rewrite IHm; reflexivity } }
end;

opaque symbol lift_lift : Π t m n,
  π (lift m (lift (n + m) t) = lift ((n + m) +1) (lift m t)) ≔
begin
  induction
  { // Var
    assume i m n; simplify; rewrite liftIdx_liftIdx m n i; reflexivity }
  { // App
    assume s IHs t IHt m n;
    simplify; rewrite IHs; rewrite IHt; reflexivity }
  { // Lam
    assume t IH m n;
    simplify; refine feq Lam (IH (m +1) n) }
end;

// Convenient specialisation: lift 0 commutes with lift j at the right shift.
opaque symbol lift_lift_0 j t : π (lift _0 (lift j t) = lift (j +1) (lift _0 t)) ≔
begin
  assume j t; apply lift_lift t _0 j
end;

// ---------------------------------------------------------------------------
// Commutation of subst and lift.
// substVar version: push the outer lift j through substVar.
// Key ingredient of the main substitution lemma.
// ---------------------------------------------------------------------------

opaque symbol substVar_liftIdx_comm u : Π j m i,
  π (substVar (m + (j +1)) u (liftIdx j i) = lift j (substVar (m + j) u i)) ≔
begin
  assume u;
  induction
  { // j = 0
    assume m i; reflexivity }
  { // j = j' +1
    assume j' IHj m;
    induction
    { // i = 0
      reflexivity }
    { // i = i' +1
      assume i' IHi;
      have h : π (substVar ((m + j') +1) u (liftIdx j' i') = lift j' (substVar (m + j') u i'))
        { apply IHj m i' };
      simplify;
      rewrite h;
      apply lift_lift_0 j' (substVar (m + j') u i') } }
end;

opaque symbol subst_lift_comm : Π t j m u,
  π (subst (m + (j +1)) u (lift j t) = lift j (subst (m + j) u t)) ≔
begin
  induction
  { // Var
    assume i j m u; simplify; apply substVar_liftIdx_comm u j m i }
  { // App
    assume s IHs t IHt j m u;
    simplify; refine feq2 App (IHs j m u) (IHt j m u) }
  { // Lam
    assume t IH j m u;
    simplify; refine feq Lam (IH (j +1) m u) }
end;

// Convenient j=0 specialisation.
opaque symbol subst_lift_0 m u t : π (subst (m +1) u (lift _0 t) = lift _0 (subst m u t)) ≔
begin
  assume m u t; apply subst_lift_comm t _0 m u
end;

// ---------------------------------------------------------------------------
// Main substitution lemma (Barendregt-style).
//
// General form with binder depth i:
//   subst i (subst k u v) (subst (k + i + 1) u t) = subst (k + i) u (subst i v t)
//
// Specialisation at i=0 is the shape needed for parallel β:
//   subst 0 (subst k u v) (subst (k+1) u t) = subst k u (subst 0 v t)
// ---------------------------------------------------------------------------

// Var-level lemma (k, u, v fixed parameters; induct on i, then on j).
opaque symbol subst_substVar k u v : Π i j,
  π (subst i (subst k u v) (substVar (k + i + 1) u j) = subst (k + i) u (substVar i v j)) ≔
begin
  assume k u v;
  induction
  { // i = 0
    induction
    { // j = 0
      reflexivity }
    { // j = j' +1
      assume j' IHj;
      simplify;
      apply subst_lift (substVar k u j') _0 (subst k u v) } }
  { // i = i' +1
    assume i' IHi;
    induction
    { // j = 0
      reflexivity }
    { // j = j' +1
      assume j' IHj;
      simplify;
      rewrite subst_lift_0 i' (subst k u v) (substVar ((k + i') +1) u j');
      rewrite subst_lift_0 (k + i') u (substVar i' v j');
      refine feq (lift _0) (IHi j') } }
end;

opaque symbol subst_subst : Π t i k u v,
  π (subst i (subst k u v) (subst (k + i + 1) u t) = subst (k + i) u (subst i v t)) ≔
begin
  induction
  { // Var
    assume j i k u v; simplify; apply subst_substVar k u v i j }
  { // App
    assume s IHs t IHt i k u v;
    simplify; refine feq2 App (IHs i k u v) (IHt i k u v) }
  { // Lam
    assume t IH i k u v;
    simplify; refine feq Lam (IH (i +1) k u v) }
end;

// Corollary at i = 0 — the shape used by β.
opaque symbol subst_subst_0 t k u v :
  π (subst _0 (subst k u v) (subst (k +1) u t) = subst k u (subst _0 v t)) ≔
begin
  assume t k u v; apply subst_subst t _0 k u v
end;
