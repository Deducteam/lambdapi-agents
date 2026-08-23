"""tool_signature: the flat, classified symbol list.

Every declaration comes back with a status (definitional / axiomatic)
and a `via` explaining the classification. These tests pin the
classification on the small self-contained fixtures."""

from lambdapi_mcp import tools


def _by_name(r):
    return {s["name"]: s for s in r["symbols"]}


def test_ok_true_on_success(lsp, fixture_path):
    r = tools.tool_signature(lsp, [fixture_path("simple.lp")], scope="file")
    assert r["ok"] is True
    assert r["scope"] == "file"


def test_postulates_and_rule_defined(lsp, fixture_path):
    """simple.lp: the primitives are axiomatic postulates; `double`,
    defined by two rewrite rules, is definitional-via-rules."""
    r = tools.tool_signature(lsp, [fixture_path("simple.lp")], scope="file")
    by = _by_name(r)
    for prim in ("Nat", "zero", "succ"):
        assert by[prim]["status"] == "axiomatic"
        assert by[prim]["via"] == "postulate"
    assert by["double"]["status"] == "definitional"
    assert by["double"]["via"] == "rules"


def test_symbol_entry_shape(lsp, fixture_path):
    r = tools.tool_signature(lsp, [fixture_path("simple.lp")], scope="file")
    for s in r["symbols"]:
        assert {"file", "line", "name", "type", "kind", "status", "via"} <= s.keys()
        assert s["line"] >= 1
        assert s["status"] in ("definitional", "axiomatic")
        assert s["kind"] in ("symbol", "inductive", "constructor")


def test_definition_body_is_definitional(lsp, fixture_path):
    """modifiers.lp: `op : Nat ≔ zero` has a body → definitional/body;
    the bodyless declarations are axiomatic postulates."""
    r = tools.tool_signature(lsp, [fixture_path("modifiers.lp")], scope="file")
    by = _by_name(r)
    assert by["op"]["status"] == "definitional"
    assert by["op"]["via"] == "body"
    for bodyless in ("Nat", "zero", "inj", "priv", "prot", "seq"):
        assert by[bodyless]["status"] == "axiomatic", by[bodyless]


def test_qualified_definition(lsp, fixture_path):
    """qualified.lp: `two : Stdlib.Nat.ℕ ≔ …` — a definition; its type
    keeps the qualified path."""
    r = tools.tool_signature(lsp, [fixture_path("qualified.lp")], scope="file")
    by = _by_name(r)
    assert by["two"]["via"] == "body"
    assert by["two"]["type"] == "Stdlib.Nat.ℕ"


def test_propositional_postulate_is_axiom(lsp, tmp_path):
    """A bodyless π-typed symbol is an `axiom`; a bodyless data-typed one
    is a `postulate`."""
    f = tmp_path / "ax.lp"
    f.write_text(
        "constant symbol Prop : TYPE;\n"
        "injective symbol π : Prop → TYPE;\n"
        "constant symbol ⊤ : Prop;\n"
        "symbol triv : π ⊤;\n"
    )
    r = tools.tool_signature(lsp, [str(f)], scope="file")
    by = _by_name(r)
    assert by["triv"]["via"] == "axiom"
    assert by["triv"]["status"] == "axiomatic"
    assert by["Prop"]["via"] == "postulate"


def test_propositional_stays_axiom_even_with_rule(lsp, tmp_path):
    """A propositional symbol keyed by a rewrite rule is NOT silently
    reclassified as definitional — only data-typed rule heads are."""
    f = tmp_path / "prop_rule.lp"
    f.write_text(
        "constant symbol Prop : TYPE;\n"
        "injective symbol π : Prop → TYPE;\n"
        "constant symbol ⊤ : Prop;\n"
        "symbol em : π ⊤;\n"
        "rule em ↪ em;\n"
    )
    r = tools.tool_signature(lsp, [str(f)], scope="file")
    by = _by_name(r)
    assert by["em"]["status"] == "axiomatic"
    assert by["em"]["via"] == "axiom"
