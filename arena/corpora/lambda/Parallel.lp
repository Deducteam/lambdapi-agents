// Takahashi's parallel reduction ⇒.
//
// Reduces any number of non-overlapping β-redexes in one step. Crucially,
// ⇒ is reflexive and diamond (Takahashi's triangle), unlike single-step β.

require open Stdlib.Set Stdlib.Prop Stdlib.FOL Stdlib.Eq Stdlib.Nat;
require open Lambda.Term Lambda.Beta;

// ---------------------------------------------------------------------------
// Parallel reduction — TYPE-valued inductive predicate.
// ---------------------------------------------------------------------------

inductive par : Term → Term → TYPE ≔
  | par_var  i            : par (Var i) (Var i)
  | par_app  s s' t t'    : par s s' → par t t' → par (App s t) (App s' t')
  | par_lam  s s'         : par s s' → par (Lam s) (Lam s')
  | par_beta s s' t t'    : par s s' → par t t' →
                            par (App (Lam s) t) (subst _0 t' s');

// Prop wrapper for ind_par — as in Beta.lp.
symbol WrapP : Term → Term → Prop;
rule π (WrapP $s $t) ↪ par $s $t;

// ---------------------------------------------------------------------------
// Reflexivity: every term parallel-reduces to itself.
// ---------------------------------------------------------------------------

opaque symbol par_refl : Π t, par t t ≔
begin
  induction
  { assume i; apply par_var i }
  { assume s IHs t IHt; refine par_app s s t t IHs IHt }
  { assume s IH; refine par_lam s s IH }
end;

// ---------------------------------------------------------------------------
// β ⊆ ⇒  — every β-step embeds as a parallel step.
// ---------------------------------------------------------------------------

opaque symbol par_of_beta s t : beta s t → par s t ≔
begin
  assume s t hb;
  refine ind_beta (λ a b _, WrapP a b) _ _ _ _ s t hb
  { // beta_redex
    assume a u;
    refine par_beta a a u u (par_refl a) (par_refl u) }
  { // beta_app_l
    assume a a' u hab IH;
    refine par_app a a' u u IH (par_refl u) }
  { // beta_app_r
    assume a u u' hbc IH;
    refine par_app a a u u' (par_refl a) IH }
  { // beta_lam
    assume a a' hab IH;
    refine par_lam a a' IH }
end;

// ---------------------------------------------------------------------------
// ⇒ ⊆ β*
// Uses β*-congruences (bs_lam, bs_app, bs_of_beta) from Beta.
// ---------------------------------------------------------------------------

opaque symbol bs_of_par s t : par s t → beta_star s t ≔
begin
  assume s t h;
  refine ind_par (λ a b _, Wrap a b) _ _ _ _ s t h
  { // par_var
    assume i; apply bs_refl }
  { // par_app
    assume a a' u u' ha IHa hu IHu;
    apply bs_app a a' u u' IHa IHu }
  { // par_lam
    assume a a' ha IH;
    apply bs_lam a a' IH }
  { // par_beta — App (Lam a) u ⇒ subst 0 u' a'
    // Chain: App (Lam a) u →β* App (Lam a') u' →β subst 0 u' a'.
    assume a a' u u' ha IHa hu IHu;
    refine bs_trans (App (Lam a) u) (App (Lam a') u') (subst _0 u' a') _ _
    { apply bs_app (Lam a) (Lam a') u u' (bs_lam a a' IHa) IHu }
    { apply bs_of_beta (App (Lam a') u') (subst _0 u' a') (beta_redex a' u') } }
end;
