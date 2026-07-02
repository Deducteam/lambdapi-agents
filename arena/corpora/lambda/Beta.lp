// One-step β-reduction, reflexive-transitive closure, context congruences.

require open Stdlib.Set Stdlib.Prop Stdlib.FOL Stdlib.Eq Stdlib.Nat;
require open Lambda.Term;

// ---------------------------------------------------------------------------
// One-step β-reduction — TYPE-valued inductive predicate.
// ---------------------------------------------------------------------------

inductive beta : Term → Term → TYPE ≔
  | beta_redex s u    : beta (App (Lam s) u) (subst _0 u s)
  | beta_app_l s s' t : beta s s' → beta (App s t) (App s' t)
  | beta_app_r s t t' : beta t t' → beta (App s t) (App s t')
  | beta_lam s s'     : beta s s' → beta (Lam s) (Lam s');

// ---------------------------------------------------------------------------
// Reflexive-transitive closure  t →β* u
// ---------------------------------------------------------------------------

inductive beta_star : Term → Term → TYPE ≔
  | bs_refl t     : beta_star t t
  | bs_step s t u : beta_star s t → beta t u → beta_star s u;

// ---------------------------------------------------------------------------
// Propositional reflection of beta_star, needed because `ind_beta_star`'s
// motive returns Prop.  Wrap s t reduces to beta_star s t — no axiom.
// ---------------------------------------------------------------------------

symbol Wrap : Term → Term → Prop;
rule π (Wrap $s $t) ↪ beta_star $s $t;

// ---------------------------------------------------------------------------
// Basic closure properties
// ---------------------------------------------------------------------------

opaque symbol bs_of_beta s t : beta s t → beta_star s t ≔
begin
  assume s t h; refine bs_step s s t (bs_refl s) h
end;

// Transitivity — induction on the second derivation via ind_beta_star.
opaque symbol bs_trans s t u : beta_star s t → beta_star t u → beta_star s u ≔
begin
  assume s t u hst htu;
  refine ind_beta_star (λ t0 u0 _, Wrap s t0 ⇒ Wrap s u0) _ _ t u htu hst
  { // refl
    assume t0 h; apply h }
  { // step
    assume a b c hab IH hbc hsa;
    refine bs_step s b c (IH hsa) hbc }
end;

// ---------------------------------------------------------------------------
// Context congruences for →β*
// ---------------------------------------------------------------------------

opaque symbol bs_lam s s' : beta_star s s' → beta_star (Lam s) (Lam s') ≔
begin
  assume s s' h;
  refine ind_beta_star (λ a b _, Wrap (Lam a) (Lam b)) _ _ s s' h
  { assume a; apply bs_refl }
  { assume a b c hab IH hbc;
    refine bs_step (Lam a) (Lam b) (Lam c) IH (beta_lam b c hbc) }
end;

opaque symbol bs_app_l s s' t :
  beta_star s s' → beta_star (App s t) (App s' t) ≔
begin
  assume s s' t h;
  refine ind_beta_star (λ a b _, Wrap (App a t) (App b t)) _ _ s s' h
  { assume a; apply bs_refl }
  { assume a b c hab IH hbc;
    refine bs_step (App a t) (App b t) (App c t) IH (beta_app_l b c t hbc) }
end;

opaque symbol bs_app_r s t t' :
  beta_star t t' → beta_star (App s t) (App s t') ≔
begin
  assume s t t' h;
  refine ind_beta_star (λ a b _, Wrap (App s a) (App s b)) _ _ t t' h
  { assume a; apply bs_refl }
  { assume a b c hab IH hbc;
    refine bs_step (App s a) (App s b) (App s c) IH (beta_app_r s b c hbc) }
end;

// Two-sided App congruence.
opaque symbol bs_app s s' t t' :
  beta_star s s' → beta_star t t' → beta_star (App s t) (App s' t') ≔
begin
  assume s s' t t' hs ht;
  refine bs_trans (App s t) (App s' t) (App s' t') _ _
  { apply bs_app_l s s' t hs }
  { apply bs_app_r s' t t' ht }
end;
