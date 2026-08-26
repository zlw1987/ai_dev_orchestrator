"""I2-4 -- credential read ordering and the connection contract (I2A Sec. 8/16.A).

No real ``os.environ`` is ever read here. Every "environment" is a synthetic
``dict`` handed to an injected reader callback.

**5F3B-I2-FU1** hardened this module: ``PreflightGateResult.detail`` (free
prose) was replaced by ``failure_code`` (a bounded, declared set), and
``resolve_connection_after_preflight`` now translates a missing/blank/
malformed connection value into the SAME bounded
:class:`InfrastructureRefusal` shape every other pre-prompt gate uses.
"""

from __future__ import annotations

import pytest

from qualification.i2_credentials import (
    PREFLIGHT_FAILURE_CODES,
    ConnectionValueError,
    ConnectionValues,
    InfrastructureRefusal,
    PreflightGateResult,
    read_connection_values,
    resolve_connection_after_preflight,
)
from qualification.i2_secret_context import InvalidBaseUrlError

SYNTHETIC_ENVIRON = {
    "AIDO_LITELLM_BASE_URL": "https://b300-proxy.example.invalid:8443/v1",
    "AIDO_LITELLM_API_KEY": "sk-synthetic-b300-connection-key",
}


def _reader_from(mapping: dict[str, str]):
    def reader(name: str) -> str | None:
        return mapping.get(name)

    return reader


# -- connection contract -------------------------------------------------


def test_read_connection_values_success():
    values = read_connection_values(_reader_from(SYNTHETIC_ENVIRON))
    assert values == ConnectionValues(
        base_url=SYNTHETIC_ENVIRON["AIDO_LITELLM_BASE_URL"],
        api_key=SYNTHETIC_ENVIRON["AIDO_LITELLM_API_KEY"],
    )


def test_missing_base_url_rejected_and_error_names_variable_not_value():
    environ = {"AIDO_LITELLM_API_KEY": "sk-synthetic"}
    with pytest.raises(ConnectionValueError) as excinfo:
        read_connection_values(_reader_from(environ))
    message = str(excinfo.value)
    assert "AIDO_LITELLM_BASE_URL" in message
    assert "sk-synthetic" not in message


def test_blank_base_url_rejected():
    environ = {"AIDO_LITELLM_BASE_URL": "   ", "AIDO_LITELLM_API_KEY": "sk-synthetic"}
    with pytest.raises(ConnectionValueError):
        read_connection_values(_reader_from(environ))


def test_malformed_base_url_rejected_via_shared_validator():
    environ = {"AIDO_LITELLM_BASE_URL": "not-a-url", "AIDO_LITELLM_API_KEY": "sk-synthetic"}
    with pytest.raises(InvalidBaseUrlError):
        read_connection_values(_reader_from(environ))


def test_missing_api_key_rejected_and_error_names_variable_not_value():
    environ = {"AIDO_LITELLM_BASE_URL": "https://b300-proxy.example.invalid/v1"}
    with pytest.raises(ConnectionValueError) as excinfo:
        read_connection_values(_reader_from(environ))
    message = str(excinfo.value)
    assert "AIDO_LITELLM_API_KEY" in message
    assert "https://b300-proxy.example.invalid/v1" not in message


def test_blank_api_key_rejected():
    environ = {
        "AIDO_LITELLM_BASE_URL": "https://b300-proxy.example.invalid/v1",
        "AIDO_LITELLM_API_KEY": "",
    }
    with pytest.raises(ConnectionValueError):
        read_connection_values(_reader_from(environ))


def test_error_message_never_contains_a_header_or_scheme_leak_beyond_variable_name():
    environ: dict[str, str] = {}
    with pytest.raises(ConnectionValueError) as excinfo:
        read_connection_values(_reader_from(environ))
    message = str(excinfo.value)
    assert "Authorization" not in message
    assert "Bearer" not in message


# -- 5F3B-I2-FU1: ConnectionValues repr safety (regression A) ----------------


def test_repr_of_connection_values_does_not_leak_base_url_or_key():
    values = ConnectionValues(
        base_url=SYNTHETIC_ENVIRON["AIDO_LITELLM_BASE_URL"],
        api_key=SYNTHETIC_ENVIRON["AIDO_LITELLM_API_KEY"],
    )
    rendered = repr(values)
    assert SYNTHETIC_ENVIRON["AIDO_LITELLM_BASE_URL"] not in rendered
    assert SYNTHETIC_ENVIRON["AIDO_LITELLM_API_KEY"] not in rendered
    assert "b300-proxy.example.invalid" not in rendered


def test_str_of_connection_values_also_does_not_leak():
    values = ConnectionValues(
        base_url=SYNTHETIC_ENVIRON["AIDO_LITELLM_BASE_URL"],
        api_key=SYNTHETIC_ENVIRON["AIDO_LITELLM_API_KEY"],
    )
    rendered = str(values)
    assert SYNTHETIC_ENVIRON["AIDO_LITELLM_BASE_URL"] not in rendered
    assert SYNTHETIC_ENVIRON["AIDO_LITELLM_API_KEY"] not in rendered


# -- 5F3B-I2-FU1: bounded preflight failure codes -----------------------------


def test_preflight_gate_result_rejects_unknown_failure_code():
    with pytest.raises(ValueError):
        PreflightGateResult(name="pi_package_installed", passed=False, failure_code="ANYTHING")


def test_preflight_gate_result_accepts_declared_codes():
    for code in PREFLIGHT_FAILURE_CODES:
        PreflightGateResult(name="pi_package_installed", passed=False, failure_code=code)


def test_preflight_gate_result_rejects_prose_shaped_gate_name():
    with pytest.raises(ValueError):
        PreflightGateResult(name="Pi Package Installed!!", passed=True)


SYNTHETIC_CREDENTIAL_NEEDLE = "sk-synthetic-should-never-survive-0001"
SYNTHETIC_ENDPOINT_NEEDLE = "https://internal-b300.example.invalid/v1"
SYNTHETIC_PATH_NEEDLE = r"C:\fake\workspace\secret_run"


def test_gate_failure_cannot_embed_a_synthetic_secret_in_gate_name():
    with pytest.raises(ValueError):
        PreflightGateResult(name=SYNTHETIC_CREDENTIAL_NEEDLE, passed=False)


def test_gate_failure_cannot_embed_a_synthetic_endpoint_in_gate_name():
    with pytest.raises(ValueError):
        PreflightGateResult(name=SYNTHETIC_ENDPOINT_NEEDLE, passed=False)


def test_gate_failure_cannot_embed_a_synthetic_path_in_gate_name():
    with pytest.raises(ValueError):
        PreflightGateResult(name=SYNTHETIC_PATH_NEEDLE, passed=False)


def test_infrastructure_refusal_cannot_embed_a_synthetic_secret_in_gate_name():
    with pytest.raises(ValueError):
        InfrastructureRefusal(SYNTHETIC_CREDENTIAL_NEEDLE, "CHECK_FAILED")


def test_infrastructure_refusal_cannot_embed_a_synthetic_secret_as_failure_code():
    with pytest.raises(ValueError):
        InfrastructureRefusal("some_gate", SYNTHETIC_CREDENTIAL_NEEDLE)


def test_infrastructure_refusal_repr_and_message_never_echo_a_needle():
    refusal = InfrastructureRefusal("route_reachability_gate", "CHECK_FAILED")
    for needle in (
        SYNTHETIC_CREDENTIAL_NEEDLE,
        SYNTHETIC_ENDPOINT_NEEDLE,
        SYNTHETIC_PATH_NEEDLE,
    ):
        assert needle not in repr(refusal)
        assert needle not in str(refusal)


# -- read ordering -------------------------------------------------------


def test_failing_non_secret_gate_never_calls_the_credential_reader():
    calls = {"count": 0}

    def read_connection() -> ConnectionValues:
        calls["count"] += 1
        return read_connection_values(_reader_from(SYNTHETIC_ENVIRON))

    def failing_gate() -> PreflightGateResult:
        return PreflightGateResult(
            name="pi_package_installed", passed=False, failure_code="NOT_INSTALLED"
        )

    def never_reached_gate() -> PreflightGateResult:  # pragma: no cover - must not run
        raise AssertionError("a later gate must not run after an earlier one fails")

    with pytest.raises(InfrastructureRefusal) as excinfo:
        resolve_connection_after_preflight(
            non_secret_gates=[failing_gate, never_reached_gate],
            read_connection=read_connection,
        )
    assert excinfo.value.gate_name == "pi_package_installed"
    assert excinfo.value.failure_code == "NOT_INSTALLED"
    assert calls["count"] == 0


def test_all_gates_passing_calls_reader_exactly_once():
    calls = {"count": 0}

    def read_connection() -> ConnectionValues:
        calls["count"] += 1
        return read_connection_values(_reader_from(SYNTHETIC_ENVIRON))

    def passing_gate() -> PreflightGateResult:
        return PreflightGateResult(name="config_schema_check", passed=True)

    result = resolve_connection_after_preflight(
        non_secret_gates=[passing_gate, passing_gate, passing_gate],
        read_connection=read_connection,
    )
    assert calls["count"] == 1
    assert result.base_url == SYNTHETIC_ENVIRON["AIDO_LITELLM_BASE_URL"]


def test_gates_evaluated_in_order_and_stop_at_first_failure():
    order: list[str] = []

    def gate_one() -> PreflightGateResult:
        order.append("one")
        return PreflightGateResult(name="one", passed=True)

    def gate_two() -> PreflightGateResult:
        order.append("two")
        return PreflightGateResult(
            name="two", passed=False, failure_code="SCHEMA_INVALID"
        )

    def gate_three() -> PreflightGateResult:  # pragma: no cover - must not run
        order.append("three")
        return PreflightGateResult(name="three", passed=True)

    def read_connection() -> ConnectionValues:  # pragma: no cover - must not run
        raise AssertionError("must not be called")

    with pytest.raises(InfrastructureRefusal):
        resolve_connection_after_preflight(
            non_secret_gates=[gate_one, gate_two, gate_three],
            read_connection=read_connection,
        )
    assert order == ["one", "two"]


# -- 5F3B-I2-FU1: connection-value failures become a true InfrastructureRefusal
# (required regression G) -----------------------------------------------------


def _all_gates_pass() -> PreflightGateResult:
    return PreflightGateResult(name="all_non_secret_gates", passed=True)


def test_missing_base_url_reaches_zero_prompt_infrastructure_refusal():
    def read_connection() -> ConnectionValues:
        return read_connection_values(_reader_from({"AIDO_LITELLM_API_KEY": "sk-synthetic"}))

    with pytest.raises(InfrastructureRefusal) as excinfo:
        resolve_connection_after_preflight(
            non_secret_gates=[_all_gates_pass], read_connection=read_connection
        )
    assert excinfo.value.gate_name == "connection_values"
    assert excinfo.value.failure_code == "CONNECTION_VALUE_MISSING_OR_BLANK"


def test_blank_api_key_reaches_zero_prompt_infrastructure_refusal():
    def read_connection() -> ConnectionValues:
        return read_connection_values(
            _reader_from(
                {
                    "AIDO_LITELLM_BASE_URL": "https://b300-proxy.example.invalid/v1",
                    "AIDO_LITELLM_API_KEY": "",
                }
            )
        )

    with pytest.raises(InfrastructureRefusal) as excinfo:
        resolve_connection_after_preflight(
            non_secret_gates=[_all_gates_pass], read_connection=read_connection
        )
    assert excinfo.value.gate_name == "connection_values"
    assert excinfo.value.failure_code == "CONNECTION_VALUE_MISSING_OR_BLANK"


def test_malformed_base_url_reaches_zero_prompt_infrastructure_refusal():
    def read_connection() -> ConnectionValues:
        return read_connection_values(
            _reader_from(
                {"AIDO_LITELLM_BASE_URL": "not-a-url", "AIDO_LITELLM_API_KEY": "sk-synthetic"}
            )
        )

    with pytest.raises(InfrastructureRefusal) as excinfo:
        resolve_connection_after_preflight(
            non_secret_gates=[_all_gates_pass], read_connection=read_connection
        )
    assert excinfo.value.gate_name == "connection_values"
    assert excinfo.value.failure_code == "CONNECTION_VALUE_INVALID"


def test_connection_value_error_never_escapes_the_orchestration_boundary():
    def read_connection() -> ConnectionValues:
        return read_connection_values(_reader_from({}))

    with pytest.raises(InfrastructureRefusal):
        resolve_connection_after_preflight(
            non_secret_gates=[_all_gates_pass], read_connection=read_connection
        )
    # And specifically NOT the low-level, uncategorized exception type.
    try:
        resolve_connection_after_preflight(
            non_secret_gates=[_all_gates_pass], read_connection=read_connection
        )
    except ConnectionValueError:
        pytest.fail("ConnectionValueError must not escape resolve_connection_after_preflight")
    except InfrastructureRefusal:
        pass


# -- 5F3B-I2-FU2 item B: ConnectionValues is valid by construction ------------
# (required regression 2)


def test_direct_construction_with_malformed_url_is_impossible():
    with pytest.raises(InvalidBaseUrlError):
        ConnectionValues(base_url="not-a-url", api_key="sk-synthetic")


def test_direct_construction_with_blank_key_is_impossible():
    with pytest.raises(ConnectionValueError):
        ConnectionValues(base_url=SYNTHETIC_ENVIRON["AIDO_LITELLM_BASE_URL"], api_key="")


def test_direct_construction_with_both_invalid_is_impossible():
    with pytest.raises((InvalidBaseUrlError, ConnectionValueError)):
        ConnectionValues(base_url="not-a-url", api_key="")


def test_valid_direct_construction_is_accepted():
    values = ConnectionValues(
        base_url=SYNTHETIC_ENVIRON["AIDO_LITELLM_BASE_URL"],
        api_key=SYNTHETIC_ENVIRON["AIDO_LITELLM_API_KEY"],
    )
    assert values.base_url == SYNTHETIC_ENVIRON["AIDO_LITELLM_BASE_URL"]
    assert values.api_key == SYNTHETIC_ENVIRON["AIDO_LITELLM_API_KEY"]


def test_injected_read_connection_returning_forged_object_cannot_bypass_policy():
    # The exact independent-review counterexample: a read_connection double
    # that TRIES to fabricate an invalid ConnectionValues directly.
    def read_connection() -> ConnectionValues:
        return ConnectionValues(base_url="not-a-url", api_key="")

    def _all_pass() -> PreflightGateResult:
        return PreflightGateResult(name="all_gates", passed=True)

    with pytest.raises(InfrastructureRefusal) as excinfo:
        resolve_connection_after_preflight(
            non_secret_gates=[_all_pass], read_connection=read_connection
        )
    assert excinfo.value.gate_name == "connection_values"
    # Never leaks the attempted invalid value.
    assert "not-a-url" not in str(excinfo.value)


def test_forged_connection_values_error_never_echoes_secret_value():
    with pytest.raises(ConnectionValueError) as excinfo:
        ConnectionValues(base_url=SYNTHETIC_ENVIRON["AIDO_LITELLM_BASE_URL"], api_key="")
    assert SYNTHETIC_ENVIRON["AIDO_LITELLM_BASE_URL"] not in str(excinfo.value)


# -- 5F3B-I2-FU2 item F: PreflightGateResult state coherence ------------------


def test_passed_true_with_failure_code_is_rejected():
    with pytest.raises(ValueError):
        PreflightGateResult(name="some_gate", passed=True, failure_code="CHECK_FAILED")


def test_passed_false_with_none_failure_code_is_rejected():
    with pytest.raises(ValueError):
        PreflightGateResult(name="some_gate", passed=False, failure_code=None)


def test_valid_pass_is_accepted():
    result = PreflightGateResult(name="some_gate", passed=True)
    assert result.passed is True
    assert result.failure_code is None


def test_valid_fail_is_accepted_and_reaches_bounded_infrastructure_refusal():
    def failing_gate() -> PreflightGateResult:
        return PreflightGateResult(name="some_gate", passed=False, failure_code="NOT_READY")

    def read_connection() -> ConnectionValues:  # pragma: no cover - must not run
        raise AssertionError("must not be called")

    with pytest.raises(InfrastructureRefusal) as excinfo:
        resolve_connection_after_preflight(
            non_secret_gates=[failing_gate], read_connection=read_connection
        )
    assert excinfo.value.gate_name == "some_gate"
    assert excinfo.value.failure_code == "NOT_READY"


def test_all_declared_failure_codes_are_valid_for_a_failing_result():
    for code in PREFLIGHT_FAILURE_CODES:
        result = PreflightGateResult(name="some_gate", passed=False, failure_code=code)
        assert result.failure_code == code


# -- 5F3B-I2-FU3 item 6: exact bool type for passed (required regressions 6/7)


def test_passed_string_false_is_rejected():
    with pytest.raises(ValueError):
        PreflightGateResult(name="some_gate", passed="false")


def test_passed_string_true_is_rejected_too():
    # Python truthiness would treat "false" AND "true" as truthy; both must
    # be rejected outright rather than one accidentally slipping through.
    with pytest.raises(ValueError):
        PreflightGateResult(name="some_gate", passed="true", failure_code="NOT_READY")


def test_passed_integer_1_is_rejected():
    with pytest.raises(ValueError):
        PreflightGateResult(name="some_gate", passed=1)


def test_passed_integer_0_is_rejected():
    with pytest.raises(ValueError):
        PreflightGateResult(name="some_gate", passed=0, failure_code="NOT_READY")


def test_passed_none_is_rejected():
    with pytest.raises(ValueError):
        PreflightGateResult(name="some_gate", passed=None)


def test_passed_true_is_valid_only_without_a_failure_code():
    result = PreflightGateResult(name="some_gate", passed=True)
    assert result.passed is True
    assert result.failure_code is None
    with pytest.raises(ValueError):
        PreflightGateResult(name="some_gate", passed=True, failure_code="NOT_READY")


def test_passed_false_is_valid_only_with_a_failure_code():
    result = PreflightGateResult(name="some_gate", passed=False, failure_code="NOT_READY")
    assert result.passed is False
    with pytest.raises(ValueError):
        PreflightGateResult(name="some_gate", passed=False)


def test_string_false_gate_never_authorizes_the_pass_branch_via_resolve():
    # Reproduces the exact independent-review shape: a "false"-valued
    # passed field must never be treated as truthy anywhere in the
    # orchestration path either.
    def string_false_gate() -> PreflightGateResult:
        return PreflightGateResult(name="some_gate", passed="false")  # type: ignore[arg-type]

    def read_connection() -> ConnectionValues:  # pragma: no cover - must not run
        raise AssertionError("must not be called")

    with pytest.raises(ValueError):
        resolve_connection_after_preflight(
            non_secret_gates=[string_false_gate], read_connection=read_connection
        )
