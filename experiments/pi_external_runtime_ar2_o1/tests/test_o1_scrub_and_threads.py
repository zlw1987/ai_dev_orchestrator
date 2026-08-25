"""O1's record identity, and reuse of AR2's unmodified scrub/redaction backstop.

No thread-leak assertion is written here explicitly: EVERY test in this
suite is already covered by the autouse ``_no_leaked_ar2_threads`` fixture in
``conftest.py``, which fails any test (this one included) that leaves an
``ar2-``-prefixed thread alive. A green run of the whole suite is itself the
proof that no O1-owned worker/thread survives.
"""

from __future__ import annotations

import threading

from o1 import EXPERIMENT_ID, EXPERIMENT_RECORD_VERSION, PARENT_ARCHITECTURE, PARENT_ARCHITECTURE_STATUS
from o1.record import record_header, refusal_record, scrub_check


def test_o1_record_identity_is_new_and_not_ar2s():
    header = record_header(preflight={}, run={})
    assert header["experiment"] == "5F3A-AR2-O1"
    assert header["experiment"] != "5F3A-AR2"
    assert header["record_version"] == "ar2-o1-run-record.v1"
    assert header["record_version"] != "ar2-run-record.v2"
    assert header["parent_architecture"] == "5F3A-AR2"
    assert header["parent_architecture_status"] == "accepted_frozen"
    assert header["is_production_review_packet"] is False
    assert header["reviewer_invoked"] is False


def test_o1_refusal_record_identity_is_new_and_not_ar2s():
    refusal = refusal_record(phase="case", finding_count=1, finding_categories=["x"])
    assert refusal["experiment"] == EXPERIMENT_ID
    assert refusal["record_version"] == EXPERIMENT_RECORD_VERSION
    assert refusal["parent_architecture"] == PARENT_ARCHITECTURE
    assert refusal["parent_architecture_status"] == PARENT_ARCHITECTURE_STATUS


def test_scrub_check_is_ar2s_own_unmodified_function_and_detects_an_endpoint():
    dirty = {"note": "reached https://example.invalid/v1/chat/completions"}
    result = scrub_check(dirty)
    assert not result["clean"]
    assert "https_url_scheme_present" in result["findings"]


def test_scrub_check_detects_reasoning_content():
    dirty = {"reasoning": "step by step I will first read the file"}
    result = scrub_check(dirty)
    assert not result["clean"]
    assert "reasoning_content_present" in result["findings"]


def test_scrub_check_detects_broker_secret_via_extra_forbidden():
    dirty = {"log": "token=deadbeef"}
    result = scrub_check(dirty, extra_forbidden=(("broker_token_present", "deadbeef"),))
    assert not result["clean"]
    assert "broker_token_present" in result["findings"]


def test_clean_record_passes_scrub():
    clean = {"experiment": EXPERIMENT_ID, "note": "nothing sensitive here"}
    result = scrub_check(clean)
    assert result["clean"], result["findings"]


def test_no_ar2_owned_thread_is_alive_at_the_start_of_this_module():
    alive = [t.name for t in threading.enumerate() if t.name.startswith("ar2-") and t.is_alive()]
    assert not alive, alive
