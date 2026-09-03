"""Tests for FormulaSecurityError inheritance from PcsError (Task 1.8.2)."""

from app.services.exceptions import PcsError
from app.services.formula_engine import FormulaSecurityError


def test_formula_security_error_inherits_pcs_error():
    assert issubclass(FormulaSecurityError, PcsError)


def test_formula_security_error_code_and_status():
    e = FormulaSecurityError("test")
    assert e.code == "FORMULA_SECURITY"
    assert e.status == 422
