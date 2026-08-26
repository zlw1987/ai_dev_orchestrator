"""I2-6 -- the process-local I2 issuance authority registry
(5F3B-I2-FU3A, encapsulated in 5F3B-I2-FU3B).

Pure in-memory tests: no filesystem, no real config, no credential. Only the
registry's own contract is under test here -- ``i2_pi_config``'s tests cover
its integration into the generator/cleanup/consumption boundaries.

**5F3B-I2-FU3B.** Every mutating/reading function in ``i2_issuance`` is now
package-internal (underscore-prefixed) -- there is no supported public API
left to test "the normal way". These tests deliberately white-box the
underscored internals, which is explicitly permitted by the accepted FU3A/
FU3B threat boundary (importing underscored internals is not something this
package defends against); what matters is that NOTHING public remains that a
well-behaved caller could misuse the way independent review's self-issuance
and re-finalization attacks did.
"""

from __future__ import annotations

import dataclasses

import pytest

from qualification import i2_issuance

# -- 5F3B-I2-FU3B item F: no public issuance mutation/lookup API -------------


def test_no_public_register_finalize_discard_or_lookup_api():
    for forbidden_name in (
        "register_issuance",
        "finalize_issuance",
        "discard_issuance",
        "lookup_issuance",
    ):
        assert not hasattr(i2_issuance, forbidden_name), forbidden_name


def test_private_internals_exist_under_their_underscored_names():
    for internal_name in (
        "_register_issuance",
        "_finalize_issuance",
        "_discard_issuance",
        "_lookup_issuance",
    ):
        assert callable(getattr(i2_issuance, internal_name))


# -- basic round trip (white-box) ---------------------------------------------


def test_lookup_of_never_registered_token_returns_none(tmp_path):
    assert i2_issuance._lookup_issuance(token="never-issued", config_dir=tmp_path) is None


def test_register_then_lookup_round_trips(tmp_path):
    i2_issuance._register_issuance(
        token="tok-1", config_dir=tmp_path, provider_id="prov-a", model_id="model-a"
    )
    record = i2_issuance._lookup_issuance(token="tok-1", config_dir=tmp_path)
    assert record is not None
    assert record.provider_id == "prov-a"
    assert record.model_id == "model-a"
    assert record.is_finalized is False
    assert record.settings_sha256 is None
    assert record.models_sha256 is None


def test_lookup_requires_agreement_between_token_and_registered_path(tmp_path):
    i2_issuance._register_issuance(
        token="tok-2", config_dir=tmp_path, provider_id="prov-a", model_id="model-a"
    )
    assert i2_issuance._lookup_issuance(token="wrong-token", config_dir=tmp_path) is None
    other_dir = tmp_path / "elsewhere"
    other_dir.mkdir()
    # The SAME genuine token, used against a DIFFERENT directory, must not
    # resolve -- the record only ever describes the path it was issued for.
    assert i2_issuance._lookup_issuance(token="tok-2", config_dir=other_dir) is None


def test_finalize_sets_digests_and_is_finalized_becomes_true(tmp_path):
    i2_issuance._register_issuance(
        token="tok-3", config_dir=tmp_path, provider_id="prov-a", model_id="model-a"
    )
    i2_issuance._finalize_issuance(
        token="tok-3", config_dir=tmp_path, settings_sha256="a" * 64, models_sha256="b" * 64
    )
    record = i2_issuance._lookup_issuance(token="tok-3", config_dir=tmp_path)
    assert record.is_finalized is True
    assert record.settings_sha256 == "a" * 64
    assert record.models_sha256 == "b" * 64


def test_finalize_without_registration_is_refused(tmp_path):
    with pytest.raises(i2_issuance.IssuanceError) as excinfo:
        i2_issuance._finalize_issuance(
            token="never-registered",
            config_dir=tmp_path,
            settings_sha256="a" * 64,
            models_sha256="b" * 64,
        )
    assert excinfo.value.reason_code == "NOT_ISSUED_BY_I2"


def test_finalize_with_wrong_path_is_refused(tmp_path):
    i2_issuance._register_issuance(
        token="tok-3b", config_dir=tmp_path, provider_id="prov-a", model_id="model-a"
    )
    other_dir = tmp_path / "elsewhere_finalize"
    other_dir.mkdir()
    with pytest.raises(i2_issuance.IssuanceError) as excinfo:
        i2_issuance._finalize_issuance(
            token="tok-3b",
            config_dir=other_dir,
            settings_sha256="a" * 64,
            models_sha256="b" * 64,
        )
    assert excinfo.value.reason_code == "PATH_MISMATCH"


# -- 5F3B-I2-FU3B item D: token uniqueness (registry keyed by token alone) ---


def test_register_twice_for_same_token_across_different_paths_is_refused(tmp_path):
    i2_issuance._register_issuance(
        token="tok-4", config_dir=tmp_path, provider_id="prov-a", model_id="model-a"
    )
    other_dir = tmp_path / "different_path"
    other_dir.mkdir()
    with pytest.raises(i2_issuance.IssuanceError) as excinfo:
        i2_issuance._register_issuance(
            token="tok-4", config_dir=other_dir, provider_id="prov-b", model_id="model-b"
        )
    assert excinfo.value.reason_code == "ISSUANCE_ALREADY_REGISTERED"
    # The ORIGINAL registration is unaffected by the refused second call.
    record = i2_issuance._lookup_issuance(token="tok-4", config_dir=tmp_path)
    assert record.provider_id == "prov-a"


def test_register_twice_for_same_token_same_path_is_also_refused(tmp_path):
    i2_issuance._register_issuance(
        token="tok-4b", config_dir=tmp_path, provider_id="prov-a", model_id="model-a"
    )
    with pytest.raises(i2_issuance.IssuanceError) as excinfo:
        i2_issuance._register_issuance(
            token="tok-4b", config_dir=tmp_path, provider_id="prov-a", model_id="model-a"
        )
    assert excinfo.value.reason_code == "ISSUANCE_ALREADY_REGISTERED"


# -- 5F3B-I2-FU3B item C: finalization is one-shot ----------------------------


def test_second_finalization_of_the_same_token_is_refused(tmp_path):
    i2_issuance._register_issuance(
        token="tok-5", config_dir=tmp_path, provider_id="prov-a", model_id="model-a"
    )
    i2_issuance._finalize_issuance(
        token="tok-5", config_dir=tmp_path, settings_sha256="a" * 64, models_sha256="b" * 64
    )
    with pytest.raises(i2_issuance.IssuanceError) as excinfo:
        i2_issuance._finalize_issuance(
            token="tok-5",
            config_dir=tmp_path,
            settings_sha256="c" * 64,
            models_sha256="d" * 64,
        )
    assert excinfo.value.reason_code == "ISSUANCE_ALREADY_FINALIZED"


def test_second_finalization_never_replaces_the_trusted_digests(tmp_path):
    # The exact independent-review attack shape, at the registry level: a
    # re-finalization attempt with a DIFFERENT (e.g. tampered-file) digest
    # must never overwrite the digest recorded the first time.
    i2_issuance._register_issuance(
        token="tok-6", config_dir=tmp_path, provider_id="prov-a", model_id="model-a"
    )
    i2_issuance._finalize_issuance(
        token="tok-6",
        config_dir=tmp_path,
        settings_sha256="original-settings-digest".ljust(64, "0"),
        models_sha256="original-models-digest".ljust(64, "0"),
    )
    with pytest.raises(i2_issuance.IssuanceError):
        i2_issuance._finalize_issuance(
            token="tok-6",
            config_dir=tmp_path,
            settings_sha256="tampered-settings-digest".ljust(64, "9"),
            models_sha256="tampered-models-digest".ljust(64, "9"),
        )
    record = i2_issuance._lookup_issuance(token="tok-6", config_dir=tmp_path)
    assert record.settings_sha256 == "original-settings-digest".ljust(64, "0")
    assert record.models_sha256 == "original-models-digest".ljust(64, "0")


# -- 5F3B-I2-FU3B item B: IssuanceRecord is immutable -------------------------


def test_issuance_record_is_a_frozen_dataclass(tmp_path):
    i2_issuance._register_issuance(
        token="tok-7", config_dir=tmp_path, provider_id="prov-a", model_id="model-a"
    )
    record = i2_issuance._lookup_issuance(token="tok-7", config_dir=tmp_path)
    assert dataclasses.is_dataclass(record)
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.models_sha256 = "attacker-supplied-digest".ljust(64, "0")
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.model_id = "relabeled-model"
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.provider_id = "relabeled-provider"


def test_mutating_a_returned_record_cannot_change_the_registry(tmp_path):
    i2_issuance._register_issuance(
        token="tok-8", config_dir=tmp_path, provider_id="prov-a", model_id="model-a"
    )
    i2_issuance._finalize_issuance(
        token="tok-8", config_dir=tmp_path, settings_sha256="a" * 64, models_sha256="b" * 64
    )
    record = i2_issuance._lookup_issuance(token="tok-8", config_dir=tmp_path)
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.models_sha256 = "c" * 64
    # The registry's own copy is unaffected by the refused mutation attempt.
    still = i2_issuance._lookup_issuance(token="tok-8", config_dir=tmp_path)
    assert still.models_sha256 == "b" * 64


def test_finalize_replaces_the_registry_entry_not_the_old_returned_object(tmp_path):
    i2_issuance._register_issuance(
        token="tok-9", config_dir=tmp_path, provider_id="prov-a", model_id="model-a"
    )
    pre_finalize_record = i2_issuance._lookup_issuance(token="tok-9", config_dir=tmp_path)
    assert pre_finalize_record.is_finalized is False

    i2_issuance._finalize_issuance(
        token="tok-9", config_dir=tmp_path, settings_sha256="a" * 64, models_sha256="b" * 64
    )

    # The OLD object a caller was holding before finalization is untouched --
    # finalization replaced the registry's entry, it did not mutate anything.
    assert pre_finalize_record.is_finalized is False
    assert pre_finalize_record.settings_sha256 is None

    post_finalize_record = i2_issuance._lookup_issuance(token="tok-9", config_dir=tmp_path)
    assert post_finalize_record.is_finalized is True


# -- 5F3B-I2-FU3B item E: repr safety -----------------------------------------


def test_issuance_record_repr_never_contains_token_or_path(tmp_path):
    genuine_token = "genuine-authority-token-sk-should-never-appear"
    i2_issuance._register_issuance(
        token=genuine_token, config_dir=tmp_path, provider_id="prov-a", model_id="model-a"
    )
    record = i2_issuance._lookup_issuance(token=genuine_token, config_dir=tmp_path)
    rendered_repr = repr(record)
    rendered_str = str(record)
    assert genuine_token not in rendered_repr
    assert genuine_token not in rendered_str
    assert str(tmp_path) not in rendered_repr
    assert str(tmp_path) not in rendered_str
    assert str(tmp_path.resolve()) not in rendered_repr
    assert str(tmp_path.resolve()) not in rendered_str


def test_issuance_record_repr_shows_only_provider_model_and_finalized(tmp_path):
    i2_issuance._register_issuance(
        token="tok-10", config_dir=tmp_path, provider_id="prov-a", model_id="model-a"
    )
    record = i2_issuance._lookup_issuance(token="tok-10", config_dir=tmp_path)
    assert repr(record) == "IssuanceRecord(provider_id='prov-a', model_id='model-a', finalized=False)"
    i2_issuance._finalize_issuance(
        token="tok-10", config_dir=tmp_path, settings_sha256="a" * 64, models_sha256="b" * 64
    )
    finalized_record = i2_issuance._lookup_issuance(token="tok-10", config_dir=tmp_path)
    assert (
        repr(finalized_record)
        == "IssuanceRecord(provider_id='prov-a', model_id='model-a', finalized=True)"
    )


def test_issuance_record_dataclass_fields_declare_token_and_path_repr_false(tmp_path):
    i2_issuance._register_issuance(
        token="tok-11", config_dir=tmp_path, provider_id="prov-a", model_id="model-a"
    )
    record = i2_issuance._lookup_issuance(token="tok-11", config_dir=tmp_path)
    field_by_name = {f.name: f for f in dataclasses.fields(record)}
    assert field_by_name["token"].repr is False
    assert field_by_name["canonical_config_dir"].repr is False


# -- discard -------------------------------------------------------------


def test_discard_removes_the_record(tmp_path):
    i2_issuance._register_issuance(
        token="tok-12", config_dir=tmp_path, provider_id="prov-a", model_id="model-a"
    )
    i2_issuance._discard_issuance(token="tok-12", config_dir=tmp_path)
    assert i2_issuance._lookup_issuance(token="tok-12", config_dir=tmp_path) is None


def test_discard_of_never_registered_token_is_a_silent_no_op(tmp_path):
    i2_issuance._discard_issuance(token="never-was-here", config_dir=tmp_path)  # must not raise


def test_discard_with_wrong_path_does_not_remove_the_record(tmp_path):
    i2_issuance._register_issuance(
        token="tok-13", config_dir=tmp_path, provider_id="prov-a", model_id="model-a"
    )
    other_dir = tmp_path / "wrong_discard_path"
    other_dir.mkdir()
    i2_issuance._discard_issuance(token="tok-13", config_dir=other_dir)
    assert i2_issuance._lookup_issuance(token="tok-13", config_dir=tmp_path) is not None


def test_error_message_never_echoes_token_or_path(tmp_path):
    hostile_token = "token-with-a-secret-looking-value-sk-synthetic"
    with pytest.raises(i2_issuance.IssuanceError) as excinfo:
        i2_issuance._finalize_issuance(
            token=hostile_token,
            config_dir=tmp_path,
            settings_sha256="a" * 64,
            models_sha256="b" * 64,
        )
    message = str(excinfo.value)
    assert hostile_token not in message
    assert str(tmp_path) not in message


def test_registry_is_keyed_by_resolved_path_not_raw_string(tmp_path):
    # Two different (but equivalent-once-resolved) string spellings of the
    # same directory must hit the SAME registry entry.
    i2_issuance._register_issuance(
        token="tok-14", config_dir=str(tmp_path), provider_id="prov-a", model_id="model-a"
    )
    nested = tmp_path / ".." / tmp_path.name
    record = i2_issuance._lookup_issuance(token="tok-14", config_dir=nested)
    assert record is not None
    assert record.provider_id == "prov-a"
