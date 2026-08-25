"""Prompt/manifest shape: no file naming in the task text, caps respected,
no absolute path or broker secret in the composed prompt.

Uses AR2's own unmodified ``ar2.manifest.build_prompt_manifest`` /
``ar2.manifest.compose_prompt`` -- O1 supplies no override.
"""

from __future__ import annotations

from ar2.broker import BrokerBinding
from ar2.manifest import (
    MAX_MANIFEST_ENTRIES,
    MAX_MANIFEST_TEXT_BYTES,
    build_prompt_manifest,
    compose_prompt,
)

from conftest import mint_for_o1
from o1.fixture import EXPECTED_CHANGED_PATHS, FILES, O1_CASE


def _basenames(paths) -> list[str]:
    return [p.rsplit("/", 1)[-1] for p in paths]


def test_case_prompt_does_not_name_either_expected_implementation_file():
    lowered = O1_CASE.prompt.lower()
    for basename in _basenames(EXPECTED_CHANGED_PATHS):
        assert basename.lower() not in lowered, basename
        assert basename.lower().replace(".py", "") not in lowered, basename


def test_case_prompt_does_not_instruct_which_files_to_edit():
    lowered = O1_CASE.prompt.lower()
    assert "edit normalize" not in lowered
    assert "edit rates" not in lowered
    assert "the file" not in lowered  # no singular-file steer, unlike R1/R3


def test_names_the_implementation_file_flag_is_false():
    assert O1_CASE.names_the_implementation_file is False


def test_manifest_lists_every_editable_file_undifferentiated(o1_repo, git_executable):
    sed = mint_for_o1(git_executable, o1_repo)
    manifest = build_prompt_manifest(sed)
    for path in FILES:
        if path in O1_CASE.verification_witness_paths:
            continue
        assert path in manifest.text, path


def test_manifest_stays_within_ar2_caps(o1_repo, git_executable):
    sed = mint_for_o1(git_executable, o1_repo)
    manifest = build_prompt_manifest(sed)
    assert manifest.readable_entry_count <= MAX_MANIFEST_ENTRIES
    assert manifest.text_bytes <= MAX_MANIFEST_TEXT_BYTES


def test_composed_prompt_has_no_absolute_path_or_pipe_endpoint(o1_repo, git_executable):
    sed = mint_for_o1(git_executable, o1_repo)
    manifest = build_prompt_manifest(sed)
    composed = compose_prompt(O1_CASE.prompt, manifest)
    assert o1_repo.repo_root not in composed
    assert o1_repo.experiment_root not in composed
    assert "\\\\.\\pipe\\" not in composed
    assert sed.capability_id not in composed


def test_composed_prompt_never_carries_a_broker_binding(o1_repo, git_executable):
    sed = mint_for_o1(git_executable, o1_repo)
    manifest = build_prompt_manifest(sed)
    binding = BrokerBinding.mint(sed.capability_id)
    composed = compose_prompt(O1_CASE.prompt, manifest)
    assert binding.token not in composed
    assert binding.capability_id not in composed
