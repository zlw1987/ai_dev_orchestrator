"""``ArtifactSafetyContext`` repr safety (5F3B-I2-FU1, item 1/required regression C).

**Narrow, explicitly authorized change to accepted I1 code.** I2 is the
first phase that populates ``ArtifactSafetyContext`` with a REAL future
credential/endpoint/broker/path value; independent review demonstrated the
previous default dataclass ``repr()`` printed every populated field
verbatim. This test module proves the fix and nothing else --
``forbidden_needles()``, ``none_declared()``, ``qualification_scrub_check``,
and every other I1 scrub/emission semantic are exercised elsewhere
(``test_records.py``, ``test_lineage.py``) and are UNCHANGED here.
"""

from __future__ import annotations

import dataclasses

from qualification.safety import ArtifactSafetyContext

SYNTHETIC_API_KEY = "sk-synthetic-safety-repr-needle-0001"
SYNTHETIC_ENDPOINT_HOST = "b300-internal.example.invalid"
SYNTHETIC_BEARER_TOKEN = "synthetic-bearer-token-0001"
SYNTHETIC_BROKER_TOKEN = "synthetic-broker-token-0001"
SYNTHETIC_PIPE_NAME = r"\\.\pipe\synthetic-qualification-pipe"
SYNTHETIC_CAPABILITY_ID = "synthetic-capability-id-0001"
SYNTHETIC_WORKSPACE_PATH = r"C:\fake\workspace\qualification_run_0001"

FULLY_POPULATED = ArtifactSafetyContext(
    endpoint_host=SYNTHETIC_ENDPOINT_HOST,
    api_key=SYNTHETIC_API_KEY,
    bearer_token=SYNTHETIC_BEARER_TOKEN,
    broker_token=SYNTHETIC_BROKER_TOKEN,
    pipe_name=SYNTHETIC_PIPE_NAME,
    capability_id=SYNTHETIC_CAPABILITY_ID,
    workspace_absolute_path=SYNTHETIC_WORKSPACE_PATH,
)

ALL_NEEDLES = (
    SYNTHETIC_API_KEY,
    SYNTHETIC_ENDPOINT_HOST,
    SYNTHETIC_BEARER_TOKEN,
    SYNTHETIC_BROKER_TOKEN,
    SYNTHETIC_PIPE_NAME,
    SYNTHETIC_CAPABILITY_ID,
    SYNTHETIC_WORKSPACE_PATH,
)


def test_repr_of_fully_populated_context_leaks_no_value():
    rendered = repr(FULLY_POPULATED)
    for needle in ALL_NEEDLES:
        assert needle not in rendered


def test_str_of_fully_populated_context_leaks_no_value():
    rendered = str(FULLY_POPULATED)
    for needle in ALL_NEEDLES:
        assert needle not in rendered


def test_repr_names_which_fields_were_declared_without_values():
    rendered = repr(FULLY_POPULATED)
    assert "endpoint_host" in rendered
    assert "api_key" in rendered
    assert "bearer_token" in rendered
    assert "broker_token" in rendered
    assert "pipe_name" in rendered
    assert "capability_id" in rendered
    assert "workspace_absolute_path" in rendered


def test_repr_of_none_declared_context_shows_no_declared_fields():
    ctx = ArtifactSafetyContext.none_declared()
    rendered = repr(ctx)
    assert rendered == "ArtifactSafetyContext(declared_fields=())"


def test_repr_of_partially_populated_context_leaks_no_value():
    ctx = ArtifactSafetyContext(api_key=SYNTHETIC_API_KEY)
    rendered = repr(ctx)
    assert SYNTHETIC_API_KEY not in rendered
    assert "api_key" in rendered
    assert "endpoint_host" not in rendered  # not declared, so not listed


def test_all_fields_are_repr_false():
    field_by_name = {f.name: f for f in dataclasses.fields(FULLY_POPULATED)}
    for name in (
        "endpoint_host",
        "api_key",
        "bearer_token",
        "broker_token",
        "pipe_name",
        "capability_id",
        "workspace_absolute_path",
    ):
        assert field_by_name[name].repr is False


def test_forbidden_needles_semantics_unchanged():
    # This narrow repr fix must not touch scrub/needle semantics at all.
    needle_codes = dict(FULLY_POPULATED.forbidden_needles())
    assert needle_codes["api_key_value_present"] == SYNTHETIC_API_KEY
    assert needle_codes["endpoint_host_value_present"] == SYNTHETIC_ENDPOINT_HOST
    assert needle_codes["bearer_token_value_present"] == SYNTHETIC_BEARER_TOKEN
    assert needle_codes["broker_token_present"] == SYNTHETIC_BROKER_TOKEN
    assert needle_codes["broker_pipe_name_present"] == SYNTHETIC_PIPE_NAME
    assert needle_codes["broker_capability_id_present"] == SYNTHETIC_CAPABILITY_ID
    assert needle_codes["workspace_absolute_path_present"] == SYNTHETIC_WORKSPACE_PATH


def test_none_declared_still_produces_no_forbidden_needles():
    assert ArtifactSafetyContext.none_declared().forbidden_needles() == ()


def test_no_serialization_helper_was_added():
    for forbidden_attr in ("to_dict", "asdict", "model_dump", "as_dict", "to_json"):
        assert not hasattr(FULLY_POPULATED, forbidden_attr)
