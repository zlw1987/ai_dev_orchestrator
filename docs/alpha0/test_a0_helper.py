"""Synthetic regression tests for docs/alpha0/a0_helper.py (ALPHA0-FU1).

Not part of the AIDO suite (it lives beside the helper, outside ``tests/`` and
``testpaths``). Run it explicitly:

    .venv/Scripts/python.exe -m pytest docs/alpha0/test_a0_helper.py -q

Everything here uses synthetic Git repositories and run directories under pytest
``tmp_path``. No model call, no verification program, no network, no GitHub, no
real workspace. The only environment values used are obviously fake sentinels,
and a test asserts that they never reach any output or any file.
"""

from __future__ import annotations

import difflib
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

import pytest

HELPER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "a0_helper.py")
SENTINEL = "FAKE-SENTINEL-NOT-A-CREDENTIAL-7731"

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Alpha-0 is Windows-only")


def _load_helper():
    spec = importlib.util.spec_from_file_location("a0_helper_under_test", HELPER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


H = _load_helper()

TARGET = "src/app.txt"
PLAN_SENTENCE = "I approve this L1 plan for L2 implementation"
DIFF_SENTENCE = "I approve this diff proposal for workspace file editing"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_git(cwd, *args):
    env = {k: os.environ[k] for k in ("PATH", "SystemRoot", "TEMP", "TMP") if k in os.environ}
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull})
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "core.autocrlf=false", *args],
        cwd=cwd, env=env, check=True, capture_output=True, stdin=subprocess.DEVNULL,
    )


def make_repo(root, files: dict[str, bytes]):
    os.makedirs(root)
    run_git(root, "init", "-q")
    run_git(root, "config", "--local", "core.autocrlf", "false")
    for rel, data in files.items():
        full = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as handle:
            handle.write(data)
    run_git(root, "add", "-A")
    run_git(root, "commit", "-q", "-m", "init")


@pytest.fixture(autouse=True)
def clean_reviewer_env(monkeypatch):
    # Names only; values are never read or printed.
    for name in [n for n in os.environ if n.upper().startswith(("AIDO_LITELLM_", "AIDO_VLLM_"))]:
        monkeypatch.delenv(name, raising=False)


class Run:
    """One synthetic Alpha-0 run: workspace, AIDO repo, config, run dir."""

    def __init__(self, base: str, ending: str):
        self.ending = ending
        nl = "\r\n" if ending == "crlf" else "\n"
        self.nl = nl
        self.ws = os.path.join(base, "ws")
        self.aido = os.path.join(base, "aido")
        self.run = os.path.join(base, "run")
        self.cfg = os.path.join(base, "run", "config", "alpha0_project.yaml")
        self.pre = nl.join(["one", "two", "three"]) + nl
        self.post = nl.join(["one", "TWO", "three"]) + nl
        make_repo(self.ws, {TARGET: self.pre.encode(), "README.md": b"hello\n"})
        make_repo(self.aido, {"src/mod.py": b"x = 1\n", "pyproject.toml": b"[project]\n"})
        for d in ("config", "inputs", "artifacts", "review", "logs", "state", "helpers"):
            os.makedirs(os.path.join(self.run, d))
        with open(self.cfg, "w", encoding="utf-8", newline="\n") as handle:
            handle.write('project_id: p\nrepo:\n  workspace_path: "' + self.ws.replace("\\", "/") + '"\n'
                         "workspace_write:\n  enabled: false\n")
        self.verified = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.aido, capture_output=True,
                                       text=True).stdout.strip()

    def p(self, *parts):
        return os.path.join(self.run, *parts)

    def a0(self, capsys, *argv):
        capsys.readouterr()
        try:
            H.main(list(argv))
            rc = 0
        except SystemExit as exc:
            rc = exc.code if isinstance(exc.code, int) else 1
        out = capsys.readouterr()
        return rc, out.out + out.err

    def preflight(self, capsys):
        return self.a0(capsys, "preflight", "--run-dir", self.run, "--workspace", self.ws, "--target", TARGET,
                       "--config", self.cfg, "--aido-repo", self.aido, "--verified-commit", self.verified)

    def state(self):
        with open(self.p("state", "a0_state.json"), encoding="utf-8") as handle:
            return json.load(handle)

    def ledger_text(self):
        with open(self.p("logs", "a0_ledger.jsonl"), "rb") as handle:
            return handle.read()

    def ws_snapshot(self):
        names = []
        for root, dirs, files in os.walk(self.ws):
            dirs[:] = [d for d in dirs if d != ".git"]
            names += [os.path.join(root, f) for f in files]
        return sorted(names)


@pytest.fixture(params=["lf", "crlf"])
def r(request, tmp_path, capsys):
    run = Run(os.path.realpath(str(tmp_path)), request.param)
    rc, out = run.preflight(capsys)
    assert rc == 0, out
    assert "PREFLIGHT_PASS" in out
    return run


def write_plan_generated(run: Run) -> str:
    plan = {
        "issue_number": 1, "repo": "o/r", "title": "t", "summary": "s", "scope_summary": "sc",
        "non_goals": [], "proposed_steps": ["a"], "files_likely_to_change": [TARGET],
        "files_forbidden_or_out_of_scope": [], "required_verification": ["prose"], "risks": [],
        "open_questions": [], "automation_level": "L1", "requires_human_approval": True,
        "notice": "n",
    }
    path = run.p("artifacts", "02_plan_generated.json")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(plan, handle)
    return path


def fill(draft_path: str, approved_path: str, sentence: str, **override):
    with open(draft_path, encoding="utf-8") as handle:
        doc = json.load(handle)
    doc["approval"] = {"approved_by": "tester", "approved_at": "2026-10-13T14:05:00+08:00",
                       "approval_text": sentence, "source": "manual", **override}
    with open(approved_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(doc, handle, indent=2)


def assemble_proposed(run: Run, capsys, content: str | None = None):
    final = run.p("inputs", "04_final_content.txt")
    with open(final, "wb") as handle:
        handle.write((content if content is not None else run.post).encode())
    with open(run.p("inputs", "04_rationale.txt"), "w", encoding="utf-8") as handle:
        handle.write("because")
    rc, out = run.a0(capsys, "proposed-assemble", "--run-dir", run.run, "--final-file", final,
                     "--rationale-file", run.p("inputs", "04_rationale.txt"),
                     "--out", run.p("inputs", "04_proposed_content.json"))
    assert rc == 0, out
    return run.a0(capsys, "proposed-check", "--run-dir", run.run, "--proposed",
                  run.p("inputs", "04_proposed_content.json"))


def write_diff_proposal(run: Run) -> str:
    pre, post = run.pre.encode(), run.post.encode()
    diff = "".join(difflib.unified_diff(run.pre.splitlines(True), run.post.splitlines(True), "a/" + TARGET, "b/" + TARGET))
    proposal = {
        "schema_version": "diff-proposal.v2",
        "changes": [{"path": TARGET, "change_type": "modify", "pre_image_sha256": sha(pre),
                     "post_image_sha256": sha(post), "unified_diff": diff}],
        "omitted_paths": [],
        "provenance": {"project_id": "p", "repo": "o/r", "issue_number": 1, "title": "t"},
    }
    path = run.p("artifacts", "05_diff_proposal.json")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(proposal, handle)
    return path


# --------------------------------------------------------------------------
# 1. Output-path boundaries
# --------------------------------------------------------------------------

def escape_targets(run: Run, subdir: str):
    return {
        "inside_workspace": os.path.join(run.ws, "stolen.json"),
        "inside_workspace_target_dir": os.path.join(run.ws, "src", "stolen.json"),
        "run_dir_root": run.p("stolen.json"),
        "wrong_run_subdir": run.p("logs" if subdir != "logs" else "state", "stolen.json"),
        "nested_below_subdir": run.p(subdir, "deeper", "stolen.json"),
        "parent_traversal": run.p(subdir, "..", "..", "outside_stolen.json"),
        "relative_path": "stolen.json",
        "blank": " ",
        "alternate_data_stream": run.p(subdir, "ok.json:stream"),
    }


@pytest.mark.parametrize("case", [
    "inside_workspace", "inside_workspace_target_dir", "run_dir_root", "wrong_run_subdir",
    "nested_below_subdir", "parent_traversal", "relative_path", "blank", "alternate_data_stream"])
def test_plan_draft_output_escape_refused(r, capsys, case):
    gen = write_plan_generated(r)
    before = r.ws_snapshot()
    out_path = escape_targets(r, "artifacts")[case]
    rc, out = r.a0(capsys, "plan-draft", "--run-dir", r.run, "--generated", gen, "--project-id", "p", "--out", out_path)
    assert rc == 1 and "A0 RESULT: STOP" in out
    assert r.ws_snapshot() == before
    assert not os.path.exists(os.path.join(os.path.dirname(r.run), "outside_stolen.json"))
    assert not os.path.exists(r.p("stolen.json"))


@pytest.mark.parametrize("case", ["inside_workspace", "run_dir_root", "wrong_run_subdir", "nested_below_subdir",
                                  "parent_traversal", "relative_path"])
def test_proposed_assemble_output_escape_refused(r, capsys, case):
    final = r.p("inputs", "f.txt")
    with open(final, "wb") as handle:
        handle.write(r.post.encode())
    with open(r.p("inputs", "rat.txt"), "w") as handle:
        handle.write("because")
    before = r.ws_snapshot()
    rc, out = r.a0(capsys, "proposed-assemble", "--run-dir", r.run, "--final-file", final,
                   "--rationale-file", r.p("inputs", "rat.txt"), "--out", escape_targets(r, "inputs")[case])
    assert rc == 1 and "A0 RESULT: STOP" in out
    assert r.ws_snapshot() == before
    assert not os.path.exists(os.path.join(os.path.dirname(r.run), "outside_stolen.json"))


@pytest.mark.parametrize("which", ["diff_out", "out"])
@pytest.mark.parametrize("case", ["inside_workspace", "run_dir_root", "wrong_run_subdir", "parent_traversal"])
def test_diff_draft_output_escape_refused(r, capsys, which, case):
    rc, out = assemble_proposed(r, capsys)
    assert rc == 0, out
    proposal = write_diff_proposal(r)
    good = {"diff_out": r.p("review", "06_proposed.diff"), "out": r.p("artifacts", "06_draft.json")}
    bad = dict(good)
    bad[which] = escape_targets(r, "review" if which == "diff_out" else "artifacts")[case]
    before = r.ws_snapshot()
    rc, out = r.a0(capsys, "diff-draft", "--run-dir", r.run, "--proposal", proposal,
                   "--diff-out", bad["diff_out"], "--out", bad["out"])
    assert rc == 1 and "A0 RESULT: STOP" in out
    assert r.ws_snapshot() == before
    # A refusal of either output must not leave the other one behind.
    assert not os.path.exists(good["diff_out"]) and not os.path.exists(good["out"])


def test_output_refuses_overwrite_and_swapped_subdirs(r, capsys):
    gen = write_plan_generated(r)
    out_path = r.p("artifacts", "02_plan.DRAFT.json")
    rc, out = r.a0(capsys, "plan-draft", "--run-dir", r.run, "--generated", gen, "--project-id", "p", "--out", out_path)
    assert rc == 0, out
    rc, out = r.a0(capsys, "plan-draft", "--run-dir", r.run, "--generated", gen, "--project-id", "p", "--out", out_path)
    assert rc == 1 and "overwrite" in out
    assert assemble_proposed(r, capsys)[0] == 0
    rc, out = r.a0(capsys, "diff-draft", "--run-dir", r.run, "--proposal", write_diff_proposal(r),
                   "--diff-out", r.p("artifacts", "x.diff"), "--out", r.p("review", "x.json"))
    assert rc == 1


@pytest.mark.skipif(sys.platform != "win32", reason="junction test is Windows-only")
def test_output_through_a_junction_is_refused(r, capsys, tmp_path):
    elsewhere = os.path.join(os.path.realpath(str(tmp_path)), "elsewhere")
    os.makedirs(elsewhere)
    link = r.p("artifacts", "linked")
    made = subprocess.run(["cmd", "/c", "mklink", "/J", link, elsewhere], capture_output=True)
    if made.returncode != 0:
        pytest.skip("cannot create a junction here")
    gen = write_plan_generated(r)
    rc, out = r.a0(capsys, "plan-draft", "--run-dir", r.run, "--generated", gen, "--project-id", "p",
                   "--out", os.path.join(link, "x.json"))
    assert rc == 1 and os.listdir(elsewhere) == []


def test_state_belonging_to_another_run_dir_is_refused(r, capsys, tmp_path):
    other = os.path.join(os.path.realpath(str(tmp_path)), "other_run")
    os.makedirs(os.path.join(other, "state"))
    with open(r.p("state", "a0_state.json"), "rb") as handle:
        data = handle.read()
    with open(os.path.join(other, "state", "a0_state.json"), "wb") as handle:
        handle.write(data)
    rc, out = r.a0(capsys, "snapshot", "--run-dir", other, "--step", "s", "--rc", "0", "--expect", "baseline")
    assert rc == 1 and "does not belong" in out


# --------------------------------------------------------------------------
# 2. No mid-run config amendment
# --------------------------------------------------------------------------

def test_config_amend_subcommand_no_longer_exists(r, capsys):
    rc, out = r.a0(capsys, "config-amend", "--run-dir", r.run, "--reason", "x")
    assert rc == 2
    assert "CONFIG_REPINNED" not in out


@pytest.mark.parametrize("edit", [
    ("enabled: false", "enabled: true"),       # a non-reviewer authority flag (workspace_write)
    ("project_id: p", "project_id: other"),    # identity
])
def test_changed_config_cannot_be_accepted_mid_run(r, capsys, edit):
    with open(r.cfg, "r", encoding="utf-8") as handle:
        text = handle.read()
    assert edit[0] in text
    with open(r.cfg, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text.replace(*edit))
    rc, out = r.a0(capsys, "snapshot", "--run-dir", r.run, "--step", "s", "--rc", "0", "--expect", "baseline")
    assert rc == 1
    assert "STOP_STATE_MISMATCH" in out and "'config' changed" in out
    assert "SNAPSHOT_OK" not in out
    # And there is no way to re-pin it.
    state = r.state()
    with pytest.raises(H.Stop):
        H.pin(state, "config", r.cfg)
    with pytest.raises(H.Stop):
        H.pin(state, "helper", HELPER_PATH)


# --------------------------------------------------------------------------
# 3. Inventory integrity
# --------------------------------------------------------------------------

def test_final_inventory_matches_final_files_and_closes_the_run(r, capsys):
    rc, out = r.a0(capsys, "snapshot", "--run-dir", r.run, "--step", "02-end", "--rc", "0", "--expect", "baseline")
    assert rc == 0 and "SNAPSHOT_OK" in out
    rc, out = r.a0(capsys, "inventory", "--run-dir", r.run)
    assert rc == 0 and "INVENTORY_WRITTEN" in out
    with open(r.p("logs", "99_inventory.json"), encoding="utf-8") as handle:
        inv = json.load(handle)
    assert inv["final_state"] == "LAST_SNAPSHOT_OK"
    actual = {}
    for root, _d, names in os.walk(r.run):
        for name in names:
            path = os.path.join(root, name)
            if os.path.normcase(path) == os.path.normcase(r.p("logs", "99_inventory.json")):
                continue
            with open(path, "rb") as handle:
                actual[os.path.relpath(path, r.run).replace(os.sep, "/")] = sha(handle.read())
    assert inv["files"] == actual
    assert inv["files"]["logs/a0_ledger.jsonl"] == sha(r.ledger_text())  # the ledger as it is NOW
    last = json.loads(r.ledger_text().splitlines()[-1])
    assert last["step"] == "99-inventory" and last["result"] == "CLOSING"


def test_nothing_changes_the_ledger_after_the_inventory(r, capsys):
    assert r.a0(capsys, "inventory", "--run-dir", r.run)[0] == 0
    frozen = r.ledger_text()
    for argv in (
        ("inventory", "--run-dir", r.run),
        ("snapshot", "--run-dir", r.run, "--step", "late", "--rc", "0", "--expect", "baseline"),
        ("packet-check", "--run-dir", r.run, "--packet", r.p("nope.json")),
    ):
        rc, out = r.a0(capsys, *argv)
        assert rc == 1 and "closed" in out
    assert r.ledger_text() == frozen


# --------------------------------------------------------------------------
# 4. Unknown state cannot produce a success verdict
# --------------------------------------------------------------------------

def test_snapshot_expect_none_is_never_success_and_halts_the_run(r, capsys):
    rc, out = r.a0(capsys, "snapshot", "--run-dir", r.run, "--step", "07-end", "--rc", "3", "--expect", "none")
    assert rc == 1
    assert "STOP_STATE_UNPROVEN" in out and "UNPROVEN" in out
    assert "SNAPSHOT_OK" not in out
    assert r.state()["halted"]["step"] == "07-end"
    # The halt cannot be cleared by a later "good-looking" snapshot...
    rc, out = r.a0(capsys, "snapshot", "--run-dir", r.run, "--step", "07-x", "--rc", "0", "--expect", "baseline")
    assert rc == 1 and "SNAPSHOT_OK" not in out and "halted" in out
    # ...and no other workflow step is authorized.
    gen = write_plan_generated(r)
    rc, out = r.a0(capsys, "plan-draft", "--run-dir", r.run, "--generated", gen, "--project-id", "p",
                   "--out", r.p("artifacts", "d.json"))
    assert rc == 1 and "halted" in out and not os.path.exists(r.p("artifacts", "d.json"))
    # The ledger recorded the unproven state, and the run can still be closed as a record.
    assert any(json.loads(l)["result"] == "STOP_STATE_UNPROVEN" for l in r.ledger_text().splitlines()
               if json.loads(l).get("step") == "07-end")
    rc, out = r.a0(capsys, "inventory", "--run-dir", r.run)
    assert rc == 0
    with open(r.p("logs", "99_inventory.json"), encoding="utf-8") as handle:
        assert json.load(handle)["final_state"] == "UNPROVEN_HALTED"


# --------------------------------------------------------------------------
# 5. Existing behavior still works (LF and CRLF via the `r` fixture)
# --------------------------------------------------------------------------

def test_happy_path_artifacts_and_approvals(r, capsys):
    gen = write_plan_generated(r)
    draft = r.p("artifacts", "02_approved_plan.DRAFT.json")
    rc, out = r.a0(capsys, "plan-draft", "--run-dir", r.run, "--generated", gen, "--project-id", "p", "--out", draft)
    assert rc == 0 and "PLAN_DRAFT_READY" in out
    with open(draft, encoding="utf-8") as handle:
        stub = json.load(handle)["approval"]
    assert stub == {"approved_by": "", "approved_at": "", "approval_text": "", "source": ""}

    approved = r.p("artifacts", "02_approved_plan.json")
    fill(draft, approved, PLAN_SENTENCE)
    rc, out = r.a0(capsys, "approval-check", "--run-dir", r.run, "--kind", "plan", "--draft", draft, "--approved", approved)
    assert rc == 0 and "APPROVAL_CONSISTENT kind=plan" in out

    rc, out = assemble_proposed(r, capsys)
    assert rc == 0 and "PROPOSED_CONTENT_OK" in out
    proposal = write_diff_proposal(r)
    ddraft, dapproved = r.p("artifacts", "06_draft.json"), r.p("artifacts", "06_approved.json")
    rc, out = r.a0(capsys, "diff-draft", "--run-dir", r.run, "--proposal", proposal,
                   "--diff-out", r.p("review", "06_proposed.diff"), "--out", ddraft)
    assert rc == 0 and "DIFF_DRAFT_READY" in out
    fill(ddraft, dapproved, DIFF_SENTENCE)
    rc, out = r.a0(capsys, "approval-check", "--run-dir", r.run, "--kind", "diff", "--draft", ddraft, "--approved", dapproved)
    assert rc == 0 and "APPROVAL_CONSISTENT kind=diff" in out

    rc, out = r.a0(capsys, "snapshot", "--run-dir", r.run, "--step", "06-end", "--rc", "0", "--expect", "baseline")
    assert rc == 0 and "SNAPSHOT_OK" in out
    # Simulate the (synthetic) write, then check the written and restored snapshots.
    full = os.path.join(r.ws, "src", "app.txt")
    with open(full, "wb") as handle:
        handle.write(r.post.encode())
    rc, out = r.a0(capsys, "snapshot", "--run-dir", r.run, "--step", "07-end", "--rc", "0", "--expect", "written")
    assert rc == 0 and "SNAPSHOT_OK" in out
    run_git(r.ws, "restore", "--source=HEAD", "--worktree", "--", TARGET)
    rc, out = r.a0(capsys, "snapshot", "--run-dir", r.run, "--step", "10-end", "--rc", "0", "--expect", "restored")
    assert rc == 0 and "SNAPSHOT_OK" in out
    # Round-trip: a closed, fully-populated run has an exact inventory.
    assert r.a0(capsys, "inventory", "--run-dir", r.run)[0] == 0


def test_wrong_sentence_and_changed_artifact_are_refused(r, capsys):
    gen = write_plan_generated(r)
    draft = r.p("artifacts", "02_approved_plan.DRAFT.json")
    assert r.a0(capsys, "plan-draft", "--run-dir", r.run, "--generated", gen, "--project-id", "p", "--out", draft)[0] == 0
    approved = r.p("artifacts", "02_approved_plan.json")
    fill(draft, approved, DIFF_SENTENCE)
    rc, out = r.a0(capsys, "approval-check", "--run-dir", r.run, "--kind", "plan", "--draft", draft, "--approved", approved)
    assert rc == 1 and "exact required sentence" in out
    os.remove(approved)
    fill(draft, approved, PLAN_SENTENCE, source="auto")
    assert r.a0(capsys, "approval-check", "--run-dir", r.run, "--kind", "plan", "--draft", draft, "--approved", approved)[0] == 1


def test_bom_and_mixed_line_endings_are_refused(r, capsys):
    gen = write_plan_generated(r)
    draft = r.p("artifacts", "02_approved_plan.DRAFT.json")
    assert r.a0(capsys, "plan-draft", "--run-dir", r.run, "--generated", gen, "--project-id", "p", "--out", draft)[0] == 0
    approved = r.p("artifacts", "02_approved_plan.json")
    fill(draft, approved, PLAN_SENTENCE)
    with open(approved, "rb") as handle:
        data = handle.read()
    with open(approved, "wb") as handle:
        handle.write(b"\xef\xbb\xbf" + data)
    rc, out = r.a0(capsys, "approval-check", "--run-dir", r.run, "--kind", "plan", "--draft", draft, "--approved", approved)
    assert rc == 1 and "byte-order mark" in out
    mixed = "one\r\ntwo\nthree\n" if r.ending == "crlf" else "one\r\ntwo\nthree\r\n"
    rc, out = assemble_proposed(r, capsys, content=mixed)
    assert rc == 1


def test_opposite_line_ending_proposal_is_refused(r, capsys):
    other = "\n" if r.ending == "crlf" else "\r\n"
    rc, out = assemble_proposed(r, capsys, content=other.join(["one", "TWO", "three"]) + other)
    assert rc == 1 and "the writer would refuse" in out


# --------------------------------------------------------------------------
# 5b. ALPHA-1A: review result classification (v4 and v5 only)
# --------------------------------------------------------------------------

def review_packet(version="review-packet.v5", **override):
    packet = {
        "schema_version": version,
        "verification": {"outcome": "verified"},
        "target": {"path": TARGET},
        "human_decision_required": True,
        "review": {"verdict": "approve"},
    }
    packet.update(override)
    return packet


def report_result(r, capsys, name, kind, rc, stdout_obj=None, stderr_text=""):
    """Run helper `report` on synthetic stdout/stderr files; return (rc, output, class)."""
    out_path = r.p("artifacts", name + ".json")
    err_path = r.p("logs", name + ".stderr.txt")
    with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
        if stdout_obj is not None:
            handle.write(json.dumps(stdout_obj))
    with open(err_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(stderr_text)
    code, text = r.a0(capsys, "report", "--run-dir", r.run, "--step", name, "--kind", kind, "--rc", str(rc),
                      "--stdout", out_path, "--stderr", err_path)
    cls = next((line.split()[2] for line in text.splitlines() if line.startswith("A0 RESULT:")), None)
    return code, text, cls


def test_review_packet_schema_constant_is_exactly_v4_and_v5():
    assert H.REVIEW_PACKET_SCHEMAS == ("review-packet.v4", "review-packet.v5")


@pytest.mark.parametrize("version", ["review-packet.v4", "review-packet.v5"])
def test_valid_v4_and_v5_review_packets_are_reviewed(r, capsys, version):
    code, text, cls = report_result(r, capsys, "09a", "review", 0, review_packet(version))
    assert code == 0 and cls == "REVIEWED" and "verdict=approve" in text


@pytest.mark.parametrize("verdict", ["approve", "changes_requested", "needs_human_review"])
def test_reviewed_verdict_detail_is_unchanged(r, capsys, verdict):
    packet = review_packet(review={"verdict": verdict})
    code, text, cls = report_result(r, capsys, "09a", "review", 0, packet)
    assert code == 0 and cls == "REVIEWED" and f"verdict={verdict}" in text


@pytest.mark.parametrize("version", [
    "review-packet.v3", "review-packet.v6", "review-packet.v45", "review-packet.v", "review-packet.V5",
    "review-packet.v5 ", " review-packet.v5", "review-packet.v5.1", "review-packet.v4.0", "",
    None, 5, ["review-packet.v5"], {"v": "review-packet.v5"},
])
def test_unknown_or_spoofed_versions_are_unexpected_stop(r, capsys, version):
    code, text, cls = report_result(r, capsys, "09a", "review", 0, review_packet(version))
    assert code == 1 and cls == "UNEXPECTED_STOP" and "REVIEWED" not in text


def test_missing_schema_version_is_unexpected_stop(r, capsys):
    packet = review_packet()
    del packet["schema_version"]
    code, text, cls = report_result(r, capsys, "09a", "review", 0, packet)
    assert code == 1 and cls == "UNEXPECTED_STOP"


@pytest.mark.parametrize("version", ["review-packet.v4", "review-packet.v5"])
@pytest.mark.parametrize("case", [
    "verification_not_verified", "verification_missing_outcome", "wrong_target", "target_missing_path",
    "human_decision_false", "human_decision_missing", "human_decision_truthy_string",
])
def test_review_packet_with_a_failed_success_condition_is_unexpected_stop(r, capsys, version, case):
    packet = review_packet(version)
    if case == "verification_not_verified":
        packet["verification"] = {"outcome": "verification-failed"}
    elif case == "verification_missing_outcome":
        packet["verification"] = {}
    elif case == "wrong_target":
        packet["target"] = {"path": "src/other.txt"}
    elif case == "target_missing_path":
        packet["target"] = {}
    elif case == "human_decision_false":
        packet["human_decision_required"] = False
    elif case == "human_decision_missing":
        del packet["human_decision_required"]
    elif case == "human_decision_truthy_string":
        packet["human_decision_required"] = "true"
    code, text, cls = report_result(r, capsys, "09a", "review", 0, packet)
    assert code == 1 and cls == "UNEXPECTED_STOP" and "REVIEWED" not in text


@pytest.mark.parametrize("version", ["review-packet.v4", "review-packet.v5"])
def test_a_valid_packet_with_a_nonzero_rc_is_never_reviewed(r, capsys, version):
    for rc in (1, 2, 3, 4):
        code, text, cls = report_result(r, capsys, f"09r{rc}", "review", rc, review_packet(version))
        assert code == 1 and cls != "REVIEWED"


def test_empty_or_unparseable_review_stdout_never_reads_as_reviewed(r, capsys):
    code, _t, cls = report_result(r, capsys, "09e", "review", 0, None)
    assert code == 1 and cls == "UNEXPECTED_STOP"
    out_path = r.p("artifacts", "09u.json")
    with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("not json")
    err_path = r.p("logs", "09u.stderr.txt")
    with open(err_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("")
    code, text = r.a0(capsys, "report", "--run-dir", r.run, "--step", "09u", "--kind", "review", "--rc", "0",
                      "--stdout", out_path, "--stderr", err_path)
    assert code == 1 and "REVIEWED" not in text and "UNEXPECTED_STOP" in text


def test_existing_review_failure_classes_are_unchanged(r, capsys):
    failed = {"outcome": "verification-failed"}
    untrusted = {"outcome": "workspace-state-untrusted"}
    assert report_result(r, capsys, "a", "review", 2, failed)[2] == "VERIFICATION_FAILED"
    assert report_result(r, capsys, "b", "review", 3, untrusted)[2] == "WORKSPACE_UNTRUSTED_STOP"
    assert report_result(r, capsys, "c", "review", 1, None)[2] == "REFUSED_BEFORE_EXECUTION"
    assert report_result(r, capsys, "d", "review", 4, None)[2] == "REVIEWER_STAGE_FAILED"
    assert report_result(r, capsys, "e", "review", 2, None, "Usage: x\nNo such option: --y")[2] == "USAGE_ERROR"
    for step, rc in (("a", 2), ("b", 3), ("c", 1), ("d", 4)):
        # every non-success class still exits 1 (different step names: the ledger is append-only)
        assert report_result(r, capsys, step + "x", "review", rc, None if rc in (1, 4) else
                             (failed if rc == 2 else untrusted))[0] == 1


def test_existing_write_and_verify_classes_are_unchanged(r, capsys):
    target = r.state()["target"]
    write_ok = {"schema_version": "workspace-write-result.v1", "outcome": "written-and-verified",
                "files_edited": 1, "target": {"path": target}, "git": {"dirty_paths_after_write": [target]}}
    code, _t, cls = report_result(r, capsys, "w1", "write", 0, write_ok)
    assert code == 0 and cls == "WRITTEN"
    assert report_result(r, capsys, "w2", "write", 0, dict(write_ok, files_edited=2))[2] == "UNEXPECTED_STOP"
    assert report_result(r, capsys, "w3", "write", 1, None)[2] == "WRITE_REFUSED"
    assert report_result(r, capsys, "w4", "write", 3, None)[2] == "WRITE_INDETERMINATE_STOP"
    verify_ok = {"outcome": "verified", "target": {"path": target},
                 "workspace_postcondition": {"head_unchanged": True, "only_approved_target_git_dirty": True}}
    code, _t, cls = report_result(r, capsys, "v1", "verify", 0, verify_ok)
    assert code == 0 and cls == "VERIFIED"
    bad = dict(verify_ok, workspace_postcondition={"head_unchanged": False, "only_approved_target_git_dirty": True})
    assert report_result(r, capsys, "v2", "verify", 0, bad)[2] == "UNEXPECTED_STOP"
    assert report_result(r, capsys, "v3", "verify", 2, {"outcome": "verification-failed"})[2] == "VERIFICATION_FAILED"
    # A review-shaped packet reported under the verify kind is not a verification success.
    assert report_result(r, capsys, "v4", "verify", 0, review_packet("review-packet.v5"))[2] == "UNEXPECTED_STOP"


# --------------------------------------------------------------------------
# 6. No credential value is printed, stored or written
# --------------------------------------------------------------------------

def test_credential_values_never_reach_output_or_files(tmp_path, capsys, monkeypatch):
    run = Run(os.path.realpath(str(tmp_path)), "lf")
    monkeypatch.setenv("AIDO_VLLM_API_KEY", SENTINEL)
    monkeypatch.setenv("AIDO_LITELLM_API_KEY", SENTINEL)
    rc, out = run.preflight(capsys)
    assert rc == 1 and "AIDO_VLLM_API_KEY" in out  # names are reported
    assert SENTINEL not in out
    monkeypatch.delenv("AIDO_VLLM_API_KEY")
    monkeypatch.delenv("AIDO_LITELLM_API_KEY")
    rc, out = run.preflight(capsys)
    assert rc == 0 and SENTINEL not in out
    run.a0(capsys, "inventory", "--run-dir", run.run)
    needle = SENTINEL.encode()
    for base in (run.run, run.ws):
        for root, dirs, names in os.walk(base):
            dirs[:] = [d for d in dirs if d != ".git"]
            for name in names:
                with open(os.path.join(root, name), "rb") as handle:
                    assert needle not in handle.read()
