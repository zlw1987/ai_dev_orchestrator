# Phase 5F3A-AR0-FU1 — Pi External Runtime Filesystem Confinement Decision

> ## STATUS — read this first
>
> **This is a design-only follow-up. Nothing here is implemented.**
>
> - No production code was modified. No test was added or changed.
> - **No model call, no network call, no prompt sent to Pi, no Pi agent session.**
>   No contact with B300 or Qwen3.6.
> - No container was built or run. No isolation feature was installed or enabled.
> - `CLAUDE.md` was **not** modified. `README.md` was **not** modified.
>   `docs/PHASE_5F3A_AR0_PI_EXTERNAL_RUNTIME_BOUNDARY_DESIGN.md` was **not**
>   modified — §16 lists the AR0 statements that need a later annotation, and
>   performs none of them.
> - Windows CMD only was used for capability probing (`cmd /c ...`). No
>   PowerShell.
>
> **What this document changes.** AR0's §17.2 decision — *"A — proceed to a
> Pi-specific AR1 PoC"* — is superseded. The corrected decision is **Decision B:
> proceed only after a practical confinement boundary is chosen**, and this
> document chooses one.

Evidence markers are used exactly as AR0 used them: **(V)** verified locally in
this slice against the installed artifacts, **(D)** documented by the installed
version but not locally proven, **(U)** unknown and deferred.

---

## 1. The exact AR0 blocker being corrected

AR0 §4.2 proved, from shipped source, that Pi's built-in filesystem tools resolve
a model-supplied path as approximately:

```text
path.resolve(cwd, model_supplied_path)
```

with **no root containment check, no traversal rejection, and no canonical-root
comparison**. AR0 stated the consequence correctly: *"`cwd` is a starting point,
not a jail."*

AR0 then recorded this as **BLOCKER B1** and proposed to mitigate it by
**observing** an `orchestrator_observed_containment_breach` after the run.

**That mitigation does not hold, and it is the one thing AR0 got wrong.** AIDO's
post-run observation instrument is the fixed Git operation set applied to the
*disposable repository*. That instrument can prove things about paths **inside**
that repository. It cannot enumerate, hash, or diff arbitrary host paths outside
it, and AIDO has no baseline snapshot of the host filesystem to compare against.
So the class of event the observation was supposed to catch is exactly the class
it structurally cannot see:

```text
Pi write to  <disposable_root>\calc.py        ->  observable  (git status/diff)
Pi write to  C:\dev\ai_dev_orchestrator\...   ->  NOT observable by that instrument
Pi read  of  C:\Users\...\some_secret         ->  NOT observable by ANY AIDO instrument
```

The read case is strictly worse than the write case: a read leaves no filesystem
trace at all, and its effect — the file's contents entering model context and
leaving the machine over the provider route — is irreversible by the time
anything could be observed.

The only residual signal is the runtime's own `tool_execution_start` events
carrying the model-supplied `args`. **AR0 §10.1 already forbids treating those as
authority**, and correctly: they are the untrusted runtime's account of itself. A
design cannot simultaneously rule runtime reports non-authoritative and rest its
containment claim on them.

So AR0's B1 mitigation reduces to *"the disposable workspace has nothing valuable
nearby"* — which is false on this machine, where the Pi process would run as the
same user that owns `C:\dev`, `C:\Users\LEVIN-Z\.pi\agent\auth.json`, and every
sibling project `CLAUDE.md` forbids AIDO itself from reading.

**Corrected position.** Confidentiality and integrity outside the disposable
repository must be established **before** the run — by restricting what the model
can name, or by an OS boundary — never after the run by inspection. AR0's
`containment_breach` classification remains useful as a *defense-in-depth
detector for the in-repo case*; it is **not** a confinement mechanism and must
never again be presented as one.

---

## 2. Local isolation capabilities actually found (V)

Probed read-only via `cmd /c` in this slice. Presence/version checks only —
nothing was installed, enabled, started, or configured.

| Facility | Probe | Result |
|---|---|---|
| Docker / Docker Desktop | `docker --version`, `where docker` | **Absent.** `'docker' is not recognized`; `where` found no file. |
| Podman | `where podman` | **Absent.** |
| WSL | `wsl --version`, `where wsl` | `C:\Windows\System32\wsl.exe` exists, but reports **"The Windows Subsystem for Linux is not installed."** The stub is the in-box installer shim, not a runtime. |
| Windows Sandbox | `%SystemRoot%\System32\WindowsSandbox.exe`, `WindowsSandboxClient.exe`, `where WindowsSandbox` | **Absent** — the `Containers-DisposableClientVM` optional feature is not enabled. |
| Restricted-user / ACL tooling | `where icacls`, `where runas` | **Present** (`icacls.exe`, `runas.exe`) — in-box on every Windows install. |
| Host OS | `wmic os get Caption,Version` | Windows 11 **Enterprise**, 10.0.26200. |
| Current token | `whoami /groups` | `BUILTIN\Administrators` present but **"Group used for deny only"**; integrity `S-1-16-8192` (**Medium**). The session is **not elevated**. |
| Node | `node -v`, `where node` | v24.14.1 at `C:\Program Files\nodejs\node.exe`; a second, older `v17.1.0` under `AppData\Roaming\nvm`. |
| Git | `where git` | `C:\Program Files\Git\cmd\git.exe` — so Pi's Windows `bash` lookup *would* succeed if `bash` were enabled. AR1 does not enable it. |
| Pi | `where pi` | `AppData\Roaming\npm\pi` / `pi.cmd`, package 0.84.2 (unchanged from AR0). |

**The decisive fact: every OS-level isolation candidate is absent, and every one
of them requires an elevated installation or an elevated optional-feature
enablement plus a reboot.** The account can elevate through UAC, but that is a
host-configuration change — not something AIDO may perform or assume, and this
session is deliberately unelevated.

Two secondary observations AR0 did not record, both relevant later:

- **`nvm` is present with two Node versions**, reachable in different order
  depending on shell. AR1's launch must pin an absolute Node executable (AR0 U-1
  already leaned this way); the ambiguity is now concrete rather than
  hypothetical.
- **Pi downloads binaries at tool-call time.** `dist/utils/tools-manager.js`
  `ensureTool()` **downloads `rg` / `fd`** when the `grep` / `find` tools are used
  and the binary is missing — unless `isOfflineModeEnabled()`. This is a
  previously unstated, concrete reason AR0's `PI_OFFLINE=1` is load-bearing
  rather than cosmetic, and a reason `grep`/`find` are not free tools. (V)

---

## 3. OPTION A — OS / container isolation

### 3.1 The shape being evaluated

```text
AIDO host (Python)
  -> isolated execution environment
       -> Pi RPC (stdio)
            -> disposable repo exposed read/write
                 -> provider route / model
```

Correct in principle: this is the only option that yields a boundary AIDO does
not have to argue for. It is also the option Pi's own `docs/containerization.md`
recommends first (V), listing three patterns — Gondolin micro-VM tool routing,
plain Docker, and NVIDIA OpenShell.

### 3.2 Candidate by candidate

**A1 — Docker Desktop / Linux container. NOT AVAILABLE.**

| Criterion | Finding |
|---|---|
| Filesystem visibility | Container sees only its image plus explicit mounts — the correct property. |
| Bind-mount semantics | `-v host:guest` gives exactly one writable path; everything else is unreachable. |
| Read/write confinement | Enforced by the kernel/VM boundary, not by AIDO argument. **Strongest of all candidates.** |
| Host profile inaccessible | Yes, unless deliberately mounted. `~/.pi/agent` never appears. |
| Network for direct vLLM | Reachable, but the container must route to the colleague-hosted endpoint; NAT plus a host-only/internal endpoint is a real risk. |
| Process lifecycle | Excellent — `docker stop` / `--rm` is a genuine kill, unlike AR0 §9.7's honest non-claim about descendants. |
| Windows path translation | Host `C:\...` ↔ guest `/workspace`. AIDO's canonical guard runs host-side, and the two path namespaces must be kept apart in every record. Real but manageable. |
| Pi inside or outside? | **Inside.** The image must `npm install -g @earendil-works/pi-coding-agent`, so the pinned 0.84.2 identity moves from a verified local install to an image build AIDO must pin and prove. |
| Reproducibility | High, once an image exists. |
| Dependency / operational burden | **Blocking.** Not installed; admin install; requires WSL2 or Hyper-V, **both absent**; Docker Desktop licensing on a corporate Enterprise host is not AIDO's decision. |
| Generalizes to Codex/other runtimes? | **Yes — best of any option.** The boundary is runtime-agnostic. |

**A2 — WSL-based runtime. NOT AVAILABLE.** WSL is not installed; `wsl --install`
needs elevation, feature enablement and a reboot. Even installed, plain WSL is
**not** a filesystem boundary: `/mnt/c` exposes the whole host drive read/write to
the same user. WSL alone would reproduce the exact defect being fixed; it is a
substrate for A1, not a confinement answer.

**A3 — Windows Sandbox. NOT AVAILABLE, and structurally wrong for RPC.** Absent
(feature not enabled) and needs elevation plus reboot. Even enabled, it fails on
the interface, not just availability:

- it is an **ephemeral desktop VM launched from a `.wsb` XML file**, with no
  supported mechanism to attach a parent process's **stdin/stdout pipes** to a
  process inside it. AR0's supervision design is a **stdio JSONL RPC channel**
  (§3.2) whose graceful-shutdown lever is **closing Pi's stdin** (§3.7). Windows
  Sandbox offers neither;
- state does not persist, so **Node, Git and Pi would be installed on every run** —
  over the network, on a machine AR1 otherwise wants offline;
- mapped folders are the only host channel, and a writable mapped folder is a host
  write path by design;
- startup is measured in tens of seconds per run.

Windows Sandbox is a good tool for *interactive* untrusted-binary triage. It is a
poor tool for a supervised stdio-RPC experiment.

**A4 — restricted Windows user / ACL boundary. AVAILABLE IN PRINCIPLE, REJECTED.**
The only Option-A candidate needing no missing feature, so it gets the fullest
rejection:

- **Creating the sandbox account requires elevation** (`net user` /
  `New-LocalUser`), and so does giving it a profile.
- **Default ACLs are permissive in the wrong direction.** A fresh local user joins
  `Users`, which by default carries **read** access to `C:\`, `C:\Program Files`,
  and — critically — typically to a hand-created tree such as `C:\dev` through
  inheritance. Confidentiality would therefore require **explicit deny ACEs on the
  host's real project trees**, i.e. AIDO mutating the ACLs of
  `C:\dev\ai_dev_orchestrator` and of directories `CLAUDE.md` forbids it from
  touching at all. That is a host-wide, hard-to-audit, hard-to-reverse change made
  in service of an experiment.
- **`runas /trustlevel:0x20000` is not filesystem isolation.** A restricted token
  drops privileges but keeps the user's own SID, so it still reaches everything
  that user reaches. Same category as a Job Object.
- **stdio redirection breaks.** `runas.exe` cannot take a password
  non-interactively and does not hand the parent redirected pipes. Doing it
  properly means `CreateProcessWithLogonW` / `LogonUser` + `CreateProcessAsUser`
  via `pywin32` — a new native dependency, a **stored second-account password**
  (a new credential in a project whose rule is *secrets only from environment
  variables*), and privilege requirements of its own.
- **The disposable repo must be writable by the sandbox account and readable by
  AIDO afterwards**, so AIDO's post-run Git inspection would run as a different
  principal than the writer — a new class of failure.

The cost is a permanent, elevated, credential-bearing host change; the benefit is
a boundary only as good as a hand-written deny-ACE list. **Rejected for AR1.**

**A5 — Gondolin (Pi's own micro-VM extension). NOT AVAILABLE.** Pi ships the
example at `examples/extensions/gondolin/` (V). It requires
`@earendil-works/gondolin` **plus QEMU installed via a package manager**, and it
is a *Linux* micro-VM — not a Windows-local option today. It is, however,
extremely informative: see §4.1.

**A6 — OpenShell.** Requires an OpenShell gateway backed by Docker, Podman or a VM
runtime (D, from `containerization.md`). Every backing runtime is absent.

### 3.3 Option A verdict

**Architecturally the right long-term answer; unavailable on this machine today,
and its prerequisite is an elevated host change outside AIDO's mandate and
outside this experiment's reversibility budget.**

Recorded explicitly, per instruction: **a Windows Job Object is not filesystem
isolation.** Process-tree containment bounds *lifetime and process membership*,
not *which paths a handle may open*. It is not offered here as a mitigation for
B1, and must never be.

---

## 4. OPTION B — AIDO-controlled path-confined Pi tools

### 4.1 What the installed Pi 0.84.2 actually supports (V, from shipped source)

This is not speculation about an extension API. Pi ships a first-class,
**documented** pattern for exactly this, and the evidence is in the package.

**(a) `docs/containerization.md` names the pattern.** Its option 2 is *"run `pi`
on the host and route tool execution into an isolated environment"*, implemented
by an extension that **overrides** the built-in tools. The Gondolin example
"overrides `read`, `write`, `edit`, `bash`, `grep`, `find`, and `ls`."

**(b) Overriding is done by registering a tool with the built-in's name.**
`examples/extensions/gondolin/index.ts` builds the local built-in definitions
(`createReadTool(localCwd)`, …) and re-registers each with a replaced `execute`:

```ts
pi.registerTool({
  ...localWrite,                       // keeps name/description/schema/prompt text
  async execute(id, params, signal, onUpdate, ctx) { /* routed into the VM */ },
});
```

**(c) The registry genuinely lets extension tools win.**
`dist/core/agent-session.js::_refreshToolRegistry` builds the registry from
built-ins first, then does `toolRegistry.set(tool.name, tool)` for every extension
tool — so a same-named extension tool **replaces** the built-in in both the
definition registry and the callable registry. (V)

**(d) Every filesystem touch of `read` / `write` / `edit` / `ls` / `find` sits
behind a documented, exported operations seam that receives an already-resolved
absolute path.** From the shipped `.d.ts` files (V):

```ts
interface WriteOperations { writeFile(absolutePath, content); mkdir(dir); }
interface ReadOperations  { readFile(absolutePath); access(absolutePath); detectImageMimeType?(absolutePath); }
interface EditOperations  { readFile(absolutePath); writeFile(absolutePath, content); access(absolutePath); }
interface LsOperations    { exists(absolutePath); stat(absolutePath); readdir(absolutePath); }
interface FindOperations  { exists(absolutePath); glob(pattern, cwd, {ignore, limit}); }
```

**`absolutePath` is precisely the value AR0 proved is unconfined** — and it is
handed to code the extension supplies. That is the exact, minimal place a
containment predicate belongs.

**(e) `--tools` is a real registry filter, not merely an active-set filter.** In
`_refreshToolRegistry`, `isAllowedTool(name)` — derived from `--tools` and
`--exclude-tools` — filters `_baseToolDefinitions`, the extension tools, **and**
the wrapped registry. `setActiveToolsByName` can only enable names *present in the
registry* ("Only tools in the registry can be enabled"). So AR0 §3.8's claim that
`--tools` is the one form a loaded extension cannot widen is **confirmed in
source**, not merely documented. (V)

**(f) …but `--no-builtin-tools` is NOT a registry filter, and AR0 over-credits
it.** In `dist/core/sdk.js`:

```js
const allowedToolNames = options.tools ?? (options.noTools === "all" ? [] : undefined);
```

`--no-builtin-tools` maps to `noTools: "builtin"`, leaving `allowedToolNames`
**undefined** — the built-ins stay in the registry and are merely inactive, so an
extension calling `pi.setActiveTools([...])` could re-activate them. **Only
`--tools <allowlist>` (or `--no-tools`) removes them from the registry.** (V)

**(g) `--no-extensions` still loads explicit `-e` paths.**
`dist/core/resource-loader.js`: `extensionPaths = this.noExtensions ?
cliEnabledExtensions : merge(...)`. AR0's assumption is confirmed in source. (V)

**(h) A failed extension load does NOT abort the session.**
`dist/core/extensions/loader.js::loadExtensionsInternal` collects
`errors.push({path, error})` and `continue`s. **This is Option B's central
fail-open hazard**, and §4.3 turns it into a fail-closed design.

**(i) `grep` cannot be confined through its operations seam.**
`dist/core/tools/grep.js` `spawn`s ripgrep for the search itself; `GrepOperations`
covers only `isDirectory` and `readFile` for context lines. Gondolin accordingly
replaced grep's whole `execute` rather than its ops. `find` is better: it uses
`ops.glob()` when supplied and only falls back to spawning `fd`. (V)

**(j) There is no RPC command that enumerates the active tool set.** The complete
command list in `docs/rpc.md` has no `get_tools`; `get_state` returns model,
thinking level, streaming/compaction flags, session identity and message counts —
**not tools**. So AIDO cannot ask "which tools are live?" before prompting. (V)

**(k) …but `get_commands` DOES enumerate extension-registered commands**, with
`source: "extension"` and the extension `path` (V). An extension that registers a
sentinel command therefore gives AIDO a **positive, in-protocol, pre-prompt proof
that this exact extension loaded.** That closes (j) well enough to be usable.

### 4.2 What a confining tool must reject — and the three sub-shapes

A general confinement predicate must reject:

- absolute paths outside the canonical root (`C:\...`, `\\server\share`, `\\?\`,
  `\\.\`);
- `..` traversal, including traversal that only escapes after symlink resolution;
- symlinks, junctions and other reparse points anywhere on the path;
- Windows colon forms — drive-relative `C:file`, alternate data streams
  `file.txt:stream:$DATA`;
- 8.3 short-name components (`PROGRA~1`) aliasing a longer real name;
- reserved device names (`CON`, `NUL`, `COM1`, …);
- components with trailing dots or spaces;
- case and Unicode aliasing (Pi's `read` resolver additionally probes NFD,
  curly-quote and narrow-no-break-space variants of the resolved path, so naive
  string equality is not enough);
- and it must fail closed on any canonicalization error rather than falling back
  to the lexical form.

`src/ai_dev_orchestrator/workspace/canonical.py` already implements exactly that
list, in 914 lines, with a tested lexical precheck that runs *before* any
filesystem call. **That is the measure of the duplication Option B invites: a
faithful general port would be a second security-critical implementation in a
second language, with a second test suite, and it would be the only part of AIDO's
trust boundary not written in the language the rest of the boundary is written
in.**

**B-general — port the canonical guard to TypeScript.** Highest fidelity, highest
cost, highest duplication, and it puts the authoritative path predicate outside
Python. **Rejected for AR1.**

**B-rpc — the extension is a dumb proxy; AIDO decides every path in Python.**
Keeps one authority, but requires AIDO to serve a second IPC channel (named pipe
or loopback socket) concurrently with the stdio RPC supervision — new concurrency,
a new listener, a new protocol, a new class of failure — all to answer a question
about a three-file synthetic fixture. Disproportionate. **Rejected for AR1;
genuinely attractive later** if confined tools ever operate on a real repository.

**B-fixed — the AR1 shape. The confinement predicate is an exact allowlist of
paths AIDO itself created.** AR1's fixture is one seeded bug in one small file
(AR0 §15.1/§15.2), and AR0 already declares the expected change set to be exactly
`{calc.py}`. So the tool need not *canonicalize an arbitrary path* — it needs to
*accept a fixed, tiny set of targets and reject everything else*:

```text
AIDO (Python, existing canonical guard)
  canonicalizes <disposable_root>                         ONCE
  computes the exact absolute path of each fixture file    ONCE
  writes them into the disposable extension's generated config
        |
        v
AIDO-authored extension (TypeScript; no path parsing of its own)
  ALLOWED_WRITE = { "<root>\calc.py" }
  ALLOWED_READ  = ALLOWED_WRITE + { "<root>\test_calc.py", "<root>\README.md" }

  ops.writeFile(absolutePath, content):
      normalize(absolutePath) must be an EXACT member of ALLOWED_WRITE
      AND realpathSync.native(absolutePath) must equal that same member
      -> otherwise throw; no repair, no fallback, no partial write
```

This is a **whitelist of concrete targets**, not a blacklist of dangerous forms.
Every hazard listed above — traversal, UNC, ADS, short names, device names,
Unicode variants — fails the exact-membership test automatically, because none of
them *is* the one allowed string. It is a few dozen reviewable lines, it has no
clever parsing to get wrong, and its correctness argument is a single sentence.

**Answering the specific Option B questions asked:**

| Question | Answer |
|---|---|
| Does explicit extension loading still work with discovery disabled? | **Yes** (V, §4.1g). `--no-extensions` restricts to `-e` paths. |
| Can `--tools` strictly expose only the trusted custom tools? | **Yes** (V, §4.1e) — it filters the registry, and `setActiveTools` cannot exceed the registry. |
| Does any built-in filesystem tool remain reachable? | **Not if `--tools` names only AIDO's tool names.** But `--no-builtin-tools` alone leaves them reachable (V, §4.1f) — AR0's phrasing needs annotating. |
| Can model/provider code bypass tools and touch files itself? | The **model** cannot: it can only emit tool calls, and the provider route is HTTP. **Pi itself** still reads files on its own account — context files (`--no-context-files`), skills/prompts/themes (disabled), its config dir (redirected), `ensureTool` downloads (`PI_OFFLINE=1`). Those are Pi-driven, not model-driven, and each has a verified off switch. **An extension bug, a Pi bug, or a future Pi version adding an unconfined path is not covered.** |
| How much new code? | **B-fixed:** one generated `settings.json` + `models.json` (already in AR0's plan), one small TypeScript extension registering 2–3 tools plus a sentinel command, and a Python module generating them from an already-canonicalized root. Small. **B-general:** a TS port of a 914-line security module. **B-rpc:** a second IPC server inside AIDO. |
| Does it duplicate a coding-agent harness? | **B-fixed: no.** It supplies *operations*, not a harness — Pi keeps the agent loop, tool dispatch, schemas, prompt contributions and streaming. **B-general: yes, in the part that matters most.** |
| Can AIDO's canonical/path-policy logic be reused directly? | **Directly, on the Python side, for establishing the root and the allowed absolute paths — yes** (the job `canonicalize_existing_path_under_workspace` already does). **Inside the extension — no**, which is precisely why AR1 must not need it there. |
| Would a thin RPC back into AIDO be safer or overkill? | **Safer in principle, overkill for AR1** (B-rpc above). Revisit only if confined tools face a non-synthetic repository. |

### 4.3 Making Option B fail closed

Three properties, each answering a specific verified hazard:

1. **Distinct tool names, not overrides.** Register `aido_read`, `aido_edit`,
   `aido_write` — **not** `read`/`edit`/`write` — and pass
   `--tools aido_read,aido_edit,aido_write`. Gondolin overrides by name because it
   wants the built-in prompt text; AIDO wants the opposite property. Given §4.1h
   (a failed extension load does not abort the session), name-overriding is
   **fail-open**: the built-in `write` would survive under the allowed name. With
   distinct names, a failed load leaves the registry with **zero** matching tools —
   the model gets no filesystem capability at all, and the run degrades to "no
   change observed", which AIDO classifies safely.
2. **A sentinel command as a positive load proof.** The extension registers
   `pi.registerCommand("aido_confinement_active", …)`. Before sending the one
   prompt, AIDO issues `{"type":"get_commands"}` and requires an entry with that
   name and `source: "extension"`. Absent → abort before prompting, exactly like
   AR0 §9.5's model-identity handshake. This is the closest available substitute
   for the missing tool-enumeration command (§4.1j).
3. **`--tools` is mandatory and exhaustive; `--no-builtin-tools` is decorative.**
   Both are passed, but the acceptance criterion is `--tools`. No `grep`, no
   `find`, no `ls`, no `bash` in AR1 — grep is unconfinable through its seam
   (§4.1i), find/ls add surface for no experimental gain, and both can trigger a
   binary download when not offline (§2).

### 4.4 What Option B does and does not prove

Required wording, and it must survive into any AR1 record:

> **B-fixed is capability restriction at the tool layer, enforced inside the
> runtime's own process. It is not OS-level isolation.** It proves that the model
> was offered no tool capable of naming a path outside the allowlist, and that
> AIDO's own code decided every filesystem operation those tools performed. It
> does **not** prove that no host file outside the disposable repository was read
> or written: the extension runs inside Pi's Node process with the launching
> user's full permissions, and a Pi defect, a dependency defect, or a future Pi
> version could bypass the seam. **Never write "sandboxed", "isolated", "confined
> at the OS level", or "no host file outside the repo was touched".**

---

## 5. OPTION C — no confinement, disposable repo only

**Rejected.**

**Disposable is not isolated.** "Disposable" is a property of the *fixture*: it
says the repository may be deleted afterwards without loss. It says nothing about
what the process could reach *while it ran*. The two properties are independent,
and AR0's design conflated them at exactly one point — B1's mitigation.

The reason AIDO cannot truthfully claim *"no host file outside the disposable repo
was read or written"* from post-run inspection is structural, not a matter of
instrument quality:

- **The instrument's domain is wrong.** `status_porcelain` and `diff_one_path`
  answer questions about paths Git tracks in one repository. A write to
  `C:\dev\ai_dev_orchestrator\src\...` is invisible to them, and AIDO is forbidden
  to scan the host for changes even if it wanted to.
- **There is no baseline.** Detecting an arbitrary change requires a before-image
  of everything it could have changed. AIDO has one for the fixture and for
  nothing else.
- **Reads leave no trace.** Even an unlimited filesystem scan could not detect a
  read after the fact. The harm — file contents entering model context and leaving
  over the provider route — completes before any inspection could run.
- **The only remaining witness is the suspect.** `tool_execution_start.args` is the
  runtime's self-report, which AR0 §10.1 correctly rules non-authoritative. Absence
  of a suspicious arg is not evidence of absence.

The only conditions under which Option C would be acceptable do not hold here: a
machine with nothing sensitive on it, or a user account owning nothing but the
fixture. This machine holds `C:\dev` with sibling projects `CLAUDE.md` forbids AIDO
from even reading, and `~/.pi/agent/auth.json` with real provider credentials
(V, AR0 §3.13).

Option C is retained for exactly one purpose: **AR0's `containment_breach`
classification stays**, as an in-repo defense-in-depth detector and as a negative
control. It is not a boundary.

---

## 6. Primary confinement recommendation

> ## DECISION: **B — AIDO-controlled path-confined Pi tools, in the narrowest form (B-fixed).**

One recommendation, stated once. **Option A is not co-primary.** It is recorded as
the **deferred escalation**: the boundary to adopt *before* any confined Pi run
ever faces a repository that is not a synthetic fixture AIDO created itself, and
the boundary a future Codex/other-runtime slice should reach for first. It is not
part of AR1, it is not a fallback within AR1, and AR1 must not be designed to
"fall back to A" at runtime.

Why B and not A: A is unavailable (§2, §3.2), and making it available means an
elevated, rebooting, license-implicating host change plus — for the only in-box
candidate — a stored second-account credential and ACL mutations on directories
AIDO is forbidden to touch.

Why B and not C: §5.

Why B-fixed and not B-general or B-rpc: §4.2. AR1's question is about the
*runtime boundary*, and B-fixed answers it with the least new security-critical
code of any option that answers it at all.

Why not "C — no practical boundary exists yet": because one does, and Pi ships the
mechanism, documents it, and exports the seams (§4.1).

---

## 7. Why this fits AIDO's control-plane positioning

AIDO's accepted architecture is a **control plane that authorizes narrow
capabilities and derives authority independently**. B-fixed is the same rule
applied one layer further out:

| Accepted AIDO capability | The rule it embodies | B-fixed analogue |
|---|---|---|
| 5F2C writer: one file, `modify` only, pinned by SHA-256 | The set of writable targets is decided by AIDO **before** the operation, not validated after | The tool's allowlist is exactly the fixture paths AIDO canonicalized before launch |
| 5F2D verifier: argv is `[configured_executable, *configured_args]`, `shell=False`, no PATH search | AIDO supplies the concrete operation; nothing downstream may synthesize a new one | The extension supplies `ops.writeFile`; Pi may not reach the filesystem another way |
| 5F2E reviewer: model output is data, never a path/command/file selection | **No model output may select a path, a command, an executable, or a file to change** | The model selects *content*; the *path set* was fixed by AIDO before the model existed in the run |
| Everywhere: fail-closed refusal beats generalization | Rejecting an input is a legitimate answer | A non-allowlisted path is refused, never repaired, never resolved "helpfully" |

The last row is the strongest argument. `CLAUDE.md`'s standing rule — *no model
output may ever select a path, a command, an executable, or a file to change* — is
**violated in spirit by AR0's unconfined built-in tools**, where the model's chosen
path string becomes a real filesystem target. B-fixed restores the rule: the model
proposes content for a path AIDO already chose.

It also preserves AR0's genuinely correct core (§10): **authority still comes from
AIDO's independent post-run observation, never from the runtime's report.**
B-fixed does not replace that rule — it removes the one blind spot the rule could
not cover.

---

## 8. Revised trust-boundary diagram

```text
 +---------------------------------------------------------------------------+
 | AIDO CONTROL PLANE  (Python, trusted, authoritative)                       |
 |   experiment gate . canonical path guard . fixed Git adapter               |
 |   bounded process supervision . verification runner . human-facing output  |
 +------+------------------+-------------------------+-----------------------+
        |(1) launch        |(2) GENERATE the         |(5) INDEPENDENT
        |    minimal env   |    disposable extension |    OBSERVATION
        |    JSONL RPC     |    + the EXACT allowed  |    (fixed Git ops,
        |    --tools aido_*|    absolute path list   |     canonical guard,
        v                  v                         |     byte hashes)
 ###############################################     |
 #  ///  PROCESS TRUST BOUNDARY  ///           #     |
 #  everything below runs untrusted            #     |
 #  (but not everything below is unconfined)   #     |
 #######+#######################################     |
        v                                            |
 +----------------------------------------------+    |
 | pi -> node   (RPC mode, ONE prompt)          |    |
 |   agent loop . tool dispatch . compaction    |    |
 |   EMITS: events --> observational ONLY       |    |
 |                                              |    |
 |   +--------------------------------------+   |    |
 |   | AIDO-AUTHORED EXTENSION              |   |    |
 |   |  aido_read / aido_edit / aido_write   |  |    |
 |   |  ops.*(absolutePath) must be an EXACT |  |    |
 |   |  member of the allowlist              |  |    |
 |   |  ELSE throw -- no repair, no write    |  |    |
 |   |                                       |  |    |
 |   |  << AIDO's code, inside Pi's process, |  |    |
 |   |     with Pi's permissions >>          |  |    |
 |   +------------------+--------------------+   |   |
 |                      |                        |   |
 |   built-in read/write/edit/bash/grep/find/ls  |   |
 |   NOT IN THE REGISTRY  (--tools filter)       |   |
 +----------------------+------------------------+   |
                        | (3) confined FS ops   | (4) provider route
                        v                       v
        +-------------------------+   +--------------------------+
        | DISPOSABLE SYNTH REPO   |   | qwen36-direct-vllm       |
        | exactly the allowlisted |   | Qwen3.6-27B-131K         |
        | fixture paths           |   +--------------------------+
        |                         |
        | *** THE ONLY AUTHORITATIVE ARTEFACT *** ----------------> (5)
        +-------------------------+
```

Two properties are load-bearing, and one differs from AR0:

1. **The arrow that produces truth (5) still does not pass through the runtime.**
   Unchanged from AR0, and still correct.
2. **The arrow that reaches the filesystem (3) now passes through AIDO-authored
   code.** That is the new property, and it is what retires blocker B1 as a
   *pre-run* control rather than a *post-run* hope.

The boundary around the extension is deliberately drawn **inside** the untrusted
process box. It is AIDO's code running with Pi's permissions — a capability
restriction, not a privilege boundary (§4.4).

---

## 9. Revised AR1 tool / runtime topology

```text
launch (shell=False, pinned absolute node + dist/cli.js -- AR0 U-1 unchanged)

  node <pi>/dist/cli.js
      --mode rpc                     # JSONL over stdio; AIDO's supervision channel
      --no-session                   # ephemeral
      --no-extensions                # discovery off ...
      -e <disposable_ext_dir>        # ... but THIS one loads (V)
      --tools aido_read,aido_edit,aido_write     # REGISTRY filter (V) -- the real control
      --no-builtin-tools             # belt-and-braces only; NOT the control (V, 4.1f)
      --no-skills --no-prompt-templates --no-themes
      --no-context-files             # the only stopper for AGENTS.md/CLAUDE.md (V)
      --no-approve
      --offline
      --provider <disposable models.json provider id>
      --model <Qwen3.6 id>

  env (explicit dict, never an os.environ copy):
      PI_CODING_AGENT_DIR   = <disposable config dir>     # exclusion by redirection
      PI_OFFLINE=1  PI_SKIP_VERSION_CHECK=1  PI_TELEMETRY=0
      exactly ONE provider credential variable, referenced as $NAME in models.json
      + the minimal Windows process set (AR0 §11.2; U-2/U-3/U-4 unchanged)

  cwd = canonical disposable root

handshake, BEFORE the one prompt, both mandatory:
      {"type":"get_commands"}  -> requires  aido_confinement_active (source=extension)
      {"type":"get_state"}     -> requires  the exact expected provider/model
      either mismatch -> abort before prompting; no prompt is ever sent

one prompt -> stream to agent_settled (never agent_end) under AIDO's own monotonic
deadline -> close stdin -> termination ladder (AR0 §9.6 unchanged)

post-run: AIDO independent observation -> classification -> (if permitted) the
          existing verification runner -> one run record -> HUMAN IS TERMINAL
```

**The tool surface, exactly:**

| Tool | In AR1? | Why |
|---|---|---|
| `aido_read` | **Yes** | Reading `calc.py` and `test_calc.py` is required to find the seeded bug. Allowlist = the three fixture files. |
| `aido_edit` | **Yes** | Find/replace is the natural fix shape. Allowlist = `calc.py` only. |
| `aido_write` | **Optional** | Include only if AR1 wants to observe whole-file rewrite behavior. Allowlist = `calc.py` only. |
| `read` / `edit` / `write` (built-in) | **No** | Unconfined (AR0 §4.2). Removed from the registry by `--tools`. |
| `grep` | **No** | Not confinable through its ops seam (V, §4.1i), and can trigger an `rg` download. |
| `find`, `ls` | **No** | Confinable in principle (`ops.glob` / `LsOperations`), but a three-file flat fixture needs neither, and `find` can trigger an `fd` download. |
| `bash` | **No** | Unchanged from AR0 §15.3, and now doubly so: a shell bypasses every tool-layer control in this design at once. |

**Negative controls (revised from AR0 §14.4):** N3 (`--no-tools`) stays. Add
**N4 — the confinement negative control**: with the same extension loaded, the
prompt asks the model to read one file **outside** the fixture. Expected: the tool
throws, the refusal surfaces as an `isError` tool result, and no such access
occurs through AIDO's tools. N4 turns §4.4's claim into a demonstrated property
rather than a source-reading argument.

---

## 10. Should AR1 remain experiment-only? — **Yes.**

AR0 §17.2 authorized AR1 to add a production `ProjectConfig.external_runtime`
block and a shipped CLI command. **That is withdrawn.**

The reasoning is reversibility, and it is stronger now than when AR0 wrote it:

- **AR1's confinement design is zero experiments old.** B-fixed's allowlist *is*
  the fixture. Nothing about that shape is ready to be a product surface, and a
  shipped `external_runtime` gate implies a supported capability behind it.
- **A shipped config field is a compatibility commitment.** Every accepted gate
  block here (`workspace_write`, `controlled_verification`, `controlled_review`)
  was added for a capability already designed to completion. AR1 is designed to
  *discover* whether the capability is viable.
- **`CLAUDE.md` would immediately become stale** — AR0 §17.4 already flagged the
  "exactly two subprocess capabilities exist" sentence. Keeping AR1 out of `src/`
  keeps that sentence true and defers the documentation question to the point
  where the answer is known. (This document performs no `CLAUDE.md` edit.)
- **Deleting an experiment directory is free. Removing a shipped gate is not.**

**Placement:**

```text
experiments/pi_external_runtime_ar1/
    README.md                 # what this is, what it is not, how to destroy it
    run_ar1.py                # the harness entry point (NOT a CLI command)
    fixture/                  # generator for the disposable synthetic repo
    pi_config/                # generator for the disposable PI_CODING_AGENT_DIR
    extension/                # the AIDO-authored confining extension (TypeScript)
    results/                  # run records, JSONL evidence, classifications
```

Consistent with the existing untracked `experiments/b300_reviewer_benchmark*`
precedent: script-based, self-contained, outside `src/` and `tests/`.

**The harness MAY import accepted AIDO primitives** — `workspace.canonical`,
`workspace.git_adapter`, `verification.runner`, `redaction`, the ASCII-safe emit
helper. **It MUST NOT** add a `ProjectConfig` field, add or modify a CLI command,
modify anything under `src/`, claim production Pi support, or write outside its own
directory and the scratch/temp disposable root.

**Gating without a production gate.** The experiment still must not run by
accident: two explicit harness flags (mirroring the accepted two-flag pattern) plus
a required, explicitly-named experiment config file that ships absent. Absent file
→ refuse. Same fail-closed discipline, no shipped surface.

**Promotion criterion — write it down now.** Production `external_runtime` config
and a CLI command become the right answer only after: AR1 ran, the confinement held
under N4, the observation classified correctly, and a *second* slice exercised
something other than a fixture AIDO wrote. Not before.

---

## 11. Token-policy correction

AR0 §12's recording rule contained a truthfulness defect, corrected here.

**The defect.** AR0 said that if AIDO's generated `models.json` states a
`maxTokens` for the route model, the record shows `runtime_native_max_tokens: <n>`
with `aido_requested_max_output_tokens: null`. **That is false labelling.** A value
AIDO wrote into a file AIDO generated is **AIDO-configured**, whatever field it
lands in. Calling it "runtime native" would hide an AIDO ceiling inside a field
reserved for the runtime's own behavior — the precise class of error RS1's
`requested_max_output_tokens: null` rule exists to prevent.

**The corrected rule for AR1 — binding:**

> **AIDO's generated `models.json` MUST OMIT `maxTokens` entirely.**

Then, and only then, the record is truthful as:

```json
{
  "aido_requested_max_output_tokens": null,
  "runtime_native_max_tokens": "pi_catalog_default"
}
```

where `null` means exactly *AIDO did not request an output-token cap* — never `0`,
never `-1`, never `"unlimited"` — and `"pi_catalog_default"` means exactly *AIDO
stated no value and Pi applied whatever its own catalog logic applies*.

**No numeric AIDO token ceiling is added, recommended, or reserved.** AIDO's
standing default remains: **no AIDO-imposed model output-token ceiling.**

**Two supporting facts from the installed source, recorded because they make the
label defensible rather than merely cautious:**

- `dist/core/provider-composer.js`: `maxTokens: definition.maxTokens ?? 16384`. So
  a custom `models.json` entry with no `maxTokens` yields an internal
  `model.maxTokens` of 16384. That number is **Pi's**, and it is why
  `"pi_catalog_default"` is the honest token rather than `null` in that field. (V)
- `pi-ai/dist/api/openai-completions.js`: `if (options?.maxTokens) { params.max_tokens = … }`
  — the OpenAI-completions request carries `max_tokens` only when the **caller
  passes a request option**, and `agent-session.js` passes none for the main agent
  stream. (The Anthropic path differs: `options?.maxTokens ?? model.maxTokens`.) So
  on the vLLM route, Pi's catalog default appears to influence Pi's internal
  compaction and length-recovery arithmetic rather than the wire request. (V from
  source; **U** in practice — AIDO does not see the wire, Pi makes the call, and
  AR1 must not claim otherwise.)

**If a future slice ever needs a cap**, it is an explicit operator-requested value
recorded as `aido_requested_max_output_tokens: <n>` in the AIDO-owned field, and
unset must always continue to mean *no AIDO ceiling*.

---

## 12. Git-observation conclusion

**No new fixed Git operation is required, and none should be added.**

AR0 §1.3.1 recorded "no whole-repository diff" as a real gap, and U-10 asked how
much widening reconstruction would need. With the one-file fixture and fail-closed
classification, **the gap dissolves — it was an artifact of assuming AIDO must diff
whatever it finds.** It must not: it must *refuse* whatever it did not expect.

The sufficient procedure, using only the existing set:

```text
ordered_preflight_operations()      # config gate BEFORE any content read (unchanged)
  rev_parse_show_toplevel           # top level is exactly the canonical disposable root
  rev_parse_head                    # HEAD_after; must equal HEAD_before EXACTLY
  config_list_local                 # repository-poisoning gate
  config_list_scoped                # inherited-scope poisoning gate
  ls_files_stage                    # no gitlink, no symlink index mode
  ls_files_verbose                  # no assume-unchanged, no skip-worktree
  status_porcelain                  # AUTHORITATIVE changed-path enumeration
                                    # (-z, --untracked-files=all, --ignore-submodules=none)

then, ONLY for the expected shape:
  if status is exactly { " M calc.py" } plus the pre-declared tolerated untracked set:
        diff_one_path("calc.py")    # the one diff AIDO needs
  else:
        classify workspace UNTRUSTED and STOP -- do not diff, do not repair
```

Everything else is a **classification outcome, not a diffing problem**:

| Observed state | AR1 outcome |
|---|---|
| Staged index entry of any kind | untrusted → stop (and note: with no `bash`, nothing in AR1's tool set can stage) |
| Any tracked file other than `calc.py` modified | `unexpected_change` → stop |
| Any delete (`D`) or rename (`R`) | untrusted → stop |
| Unmerged (`U`) entries | untrusted → stop |
| HEAD moved | untrusted → stop |
| Untracked paths beyond the pre-declared tolerated set | `unexpected_untracked` → enumerate, canonicalize, report; **never auto-delete before evidence capture** |
| Config gate refusal | `config_poisoned` → stop (a genuine existing strength, AR0 §1.3.2) |

`diff_one_path` is `git diff -- <path>` (worktree vs index), exactly right for the
single-unstaged-modification case, and it is *only* invoked in that case.

**Explicitly not proposed:** `diff --stat`, `diff HEAD`, `diff --name-status`,
whole-tree diff, `show`, `log`, or any operation that would widen a deliberately
closed set. Widening `FIXED_GIT_OPERATIONS` is a reviewable production change to a
security-relevant constant; it must never be done to make an experiment's
reporting prettier. **AR0's U-10 is answered: zero widening.**

---

## 13. Reviewer-adapter conclusion

**Primary recommendation: the reviewer stage is OUT of AR1. Defer it to a later
slice, and design the observed-diff adapter there.**

AR0 §7.5 was right that fabricating an `ApprovedDiffProposalArtifact` would launder
provenance and is prohibited. This slice found the problem is **deeper than the
type signature**, which is why deferral — not an adapter — is the AR1
recommendation:

- `ReviewContext`'s field is literally named `approved_unified_diff`, and both
  prompt builders consume it (`review/request.py`);
- the **shipped reviewer system prompt says**: *"Your ONLY job is to REVIEW one
  already-applied, human-approved single-file change"*, and the user message
  describes the diff as one *"a human approved and that has already been applied"*;
- `run_supervised_review(context: ReviewContext, …)` builds both requests
  internally, so RS1's supervision policy cannot be reused without that prompt
  text.

The three available routes each cost something AR1 should not pay:

| Route | Cost |
|---|---|
| Reuse `build_review_context` with an observed diff | **Sends a false statement to the model** about human approval. Prohibited on the same grounds AR0 used to prohibit fabricating the artifact — the lie merely moves from the type into the prompt. |
| Duplicate RS1's attempt loop inside the experiment | Duplicates *safety-critical supervision* (`max_retries=0`, the two-attempt cap, the terminal stall, AIDO's own deadline) in unreviewed experiment code. Worse than duplicating path logic. |
| Refactor `run_supervised_review` to accept prebuilt requests | A production change to accepted 5F2E/RS1 code, made to serve an experiment — the opposite of experiment-only. |

**Deferring costs AR1 nothing**, because the reviewer stage answers none of AR1's
questions. AR1 asks whether AIDO can launch an external runtime, confine its
filesystem capability, bound it, and independently reconstruct what it did. The
existing verification runner already supplies the authoritative quality signal
(AR0 §15.3: a test result AIDO produced beats one Pi reports). The reviewer is
accepted, working, downstream machinery that can be attached later without
re-running the architecture question.

**If a later slice does attach it**, the shape is an **experiment-only adapter**,
and its constraints are fixed now:

- **no change to `review-packet.v4`**, to `review/request.py`, to
  `review/packet.py`, or to any production reviewer semantic;
- an experiment-local context type and prompt builder whose text states the truth —
  *runtime-produced, AIDO-observed, **not** human-pre-approved* — and never the
  word "approved" about the diff;
- reuse, unchanged, of: `redaction.py` / `_Redactor`, the strict
  `parse_model_review_response` (**never** relaxed — the 5F2E-V2 rule is absolute),
  `build_review_response_format()`'s generated JSON schema, `LLMClient`, and RS1's
  supervision semantics;
- the verdict stays advisory and terminal at a human: no fixer, no review/fix loop,
  no second reviewer, no promotion.

---

## 14. Remaining risks

**Not retired by this decision (carried forward from AR0, unchanged):**

- **B2 — ambient global config/credentials.** `~/.pi/agent` with `auth.json`,
  `settings.json`, `models.json` exists on this machine. Mitigation remains
  `PI_CODING_AGENT_DIR` redirection + `--no-*` flags + credential withholding;
  redirection completeness remains **U-3**.
- **B3 — context files load regardless of trust.** `--no-context-files` plus a
  fixture containing no `AGENTS.md` / `AGENTS.override.md` / `CLAUDE.md`.
- **B4 — Pi's environment is the model's shell environment.** Mitigated further by
  having **no `bash` tool at all**, but the explicit minimal environment remains
  mandatory: it is also what a defective or future-widened tool would inherit.
- **M2** (`.git` config poisoning), **M4** (reasoning leakage — drop at the
  parser), **M5** (untracked-file blindness), **M6** (non-ASCII console output),
  **M7** (protocol desynchronization). All unchanged.

**New or newly sharpened by Option B:**

| # | Risk | Severity | Mitigation / status |
|---|---|---|---|
| **N1** | **A failed extension load does not abort the session** (V, §4.1h). Name-overriding tools would fail **open** to the unconfined built-in. | **Blocker if designed wrong** | Distinct `aido_*` names + `--tools` naming only those + the `get_commands` sentinel handshake. Fails closed to *zero* tools. |
| **N2** | **`--no-builtin-tools` is not a registry filter** (V, §4.1f); an extension could `setActiveTools` a built-in back. | Major | `--tools` is the mandatory control; AR1 asserts it, not `-nbt`. AR0 §3.8 wording needs annotation (§16). |
| **N3** | **The confining code runs inside the untrusted process**, with the launching user's full permissions. A Pi/dependency defect bypasses it. | Major, **unmitigable at this layer** | State it (§4.4). This is exactly what Option A would fix, and why A is the deferred escalation. |
| **N4** | **No RPC command enumerates active tools** (V, §4.1j), so AIDO cannot directly verify registry contents before prompting. | Major | The `get_commands` sentinel proves *extension load*, not *registry contents*. Record the difference honestly; consider a first-turn probe tool call in a later slice. |
| **N5** | **Path resolution probes the filesystem outside the ops seam.** `read`'s resolver (`dist/core/tools/path-utils.js`) calls `accessSync`/`access` on Unicode/NFD/curly-quote/screenshot variants of the resolved path *before* ops are consulted. | Minor | Existence probing only — no content read, nothing written. AIDO must not claim "no path outside the allowlist was touched in any sense"; the accurate claim covers *reads and writes*, not *stat calls*. |
| **N6** | **A Pi upgrade could change or remove the operations seam**, silently converting a confined tool into an unconfined one. | Major | Pin the Pi version, assert `pi --version` at launch, and treat any version change as requiring a fresh source review of §4.1. |
| **N7** | **`ensureTool` downloads `rg`/`fd` at tool-call time** when not offline (V, §2). | Minor in AR1 | `grep`/`find` excluded and `PI_OFFLINE=1`. Becomes real again if a later slice enables either. |
| **N8** | **TypeScript/extension dependency resolution is unproven.** `pi.registerTool` parameters are typebox schemas; whether a dependency-free plain-object schema is accepted, and how a disposable extension directory resolves `typebox` / `@earendil-works/pi-coding-agent`, is untested. | Minor, **new unknown U-12** | Try dependency-free first; fall back to a small `package.json` + local `node_modules` beside the extension (documented as supported). Record the minimum that works. |
| **N9** | **Confinement narrows what the experiment observes.** With a fixed allowlist, AR1 cannot learn how the model behaves when it *can* roam. | Accepted | Deliberate. N4-the-negative-control recovers the interesting part safely: it observes what the model *attempts* and confirms the refusal path, without granting the capability. |

---

## 15. Revised AR1 GO / NO-GO

> ## **GO — conditional on Option B-fixed being implemented first.**

AR0's Decision A ("no prerequisite blocks the experiment") is **withdrawn**. There
was a prerequisite; §1 is it. With B-fixed there is a practical confinement
boundary, so the answer is GO — but AR1 is now **gated on the confinement, not
merely accompanied by it**.

**The revised minimal AR1, in full.**

Preserved from AR0, unchanged:

- Pi-specific. **No** generic `AgentRuntime` interface (AR0 §17.3 stands, and this
  slice adds a reason: B-fixed is Pi-seam-specific and would generalize badly).
- **One** real semantic run: one launch, one prompt, one observation. No AIDO
  relaunch, no fallback runtime, no fallback model, no second provider route.
- Qwen3.6 direct vLLM first, via the disposable `models.json` (`$ENV` form only,
  never `!command`).
- Synthetic disposable repository only, under a scratch/temp root — never under
  `C:\dev\ai_dev_orchestrator`, never a real target project.
- **No `bash`.** No promotion, branch, commit, push, or PR. No fixer, no review/fix
  loop. No `AIRoleConfig` wiring. No process-tree framework. No token ceiling.
- `agent_settled` (not `agent_end`) is the completion signal; AIDO-owned monotonic
  deadline; stdin-close termination ladder; reasoning deltas dropped at the parser;
  strict LF-only JSONL framing; a non-JSON stdout line is terminal.
- Post-run authority is AIDO's own observation, never the runtime's report;
  `runtime_reported_*` and `orchestrator_observed_*` stay disjoint namespaces.
- Tests use synthetic repos under pytest `tmp_path` and a **fake Pi process** (a
  synthetic JSONL-emitting script under `tmp_path`). **No real model call and no
  socket in the test suite.**

Changed by this follow-up:

1. **The model's filesystem capability is AIDO-authored and allowlisted**
   (`aido_read` / `aido_edit` / optional `aido_write`), loaded via `-e` with
   `--no-extensions`, and `--tools` names **only** those tools. No built-in
   filesystem tool is in the registry.
2. **Two mandatory pre-prompt handshakes:** `get_commands` must show the
   extension's sentinel command, and `get_state` must show the expected
   provider/model. Either mismatch aborts **before** any prompt is sent.
3. **AR1 lives in `experiments/pi_external_runtime_ar1/`.** No
   `ProjectConfig.external_runtime`, no shipped CLI command, no `src/` change, no
   production Pi support claim.
4. **The generated `models.json` omits `maxTokens`**, and the run record uses
   `aido_requested_max_output_tokens: null` +
   `runtime_native_max_tokens: "pi_catalog_default"`.
5. **No new fixed Git operation.** `status_porcelain` enumerates; `diff_one_path`
   runs only for the single expected tracked modification; every other shape
   classifies the workspace untrusted and stops.
6. **The reviewer stage is out of scope.** AR1 ends at: observation →
   classification → (if permitted) the existing verification runner → one run
   record → human.
7. **New negative control N4** (attempt an out-of-fixture path; expect a tool error
   and no such access) turns the confinement claim into a demonstrated property.

**NO-GO conditions — any one means AR1 does not run:**

- the confining extension is not loaded and proven by the `get_commands` handshake;
- `--tools` does not resolve to exactly AIDO's tool names;
- the baseline observation of the fixture is not `clean_expected`;
- the `get_state` provider/model assertion does not match exactly;
- `pi --version` is not the pinned 0.84.2 (N6);
- any part of AR1 would touch a real project workspace.

---

## 16. AR0 statements that need a later FU annotation

Listed, **not edited** — this slice modified no AR0 text.

| # | AR0 location | Statement | Required annotation |
|---|---|---|---|
| 1 | §17.2 | *"Post-AR0 decision: A — proceed to a Pi-specific AR1 PoC… no prerequisite blocks the experiment"* | **Superseded.** A prerequisite did block it (§1). Replace with Decision B plus a pointer here. |
| 2 | §16 B1 | *"Mitigation: … AIDO **observes** containment (`containment_breach`) rather than assuming it"* | **Corrected.** Post-run Git inspection of the disposable repo cannot observe out-of-repo access; the classification survives only as an in-repo defense-in-depth detector (§1, §5). |
| 3 | §3.8 | *"`--tools` is the right primitive … the one form that a loaded extension cannot widen"* | **Confirmed in source, with a caveat:** true for `--tools` (and `setActiveToolsByName` cannot exceed the registry) — but `--no-builtin-tools` does **not** filter the registry (§4.1e/f). |
| 4 | §12 | The recording rule permitting `runtime_native_max_tokens: <n>` for an AIDO-written `models.json` value | **Corrected.** AIDO must omit `maxTokens`; a value AIDO writes is AIDO-configured (§11). |
| 5 | §15.3 | *"Recommended for AR1: Option 2 — `read, grep, find, ls, edit, write`. No `bash`."* | **Superseded.** Built-in filesystem tools are excluded entirely; the surface is `aido_read` / `aido_edit` / optional `aido_write`. `grep` additionally is not confinable via its ops seam (§4.1i). |
| 6 | §17.2 items 1–2 | Authorization to add a `ProjectConfig.external_runtime` block and one shipped CLI command | **Withdrawn.** AR1 is experiment-only (§10). |
| 7 | §17.2 item 8 + §7.5 | Reuse of the existing supervised reviewer with an observed-diff adapter | **Deferred out of AR1.** The blocker is the shipped prompt text asserting human approval, not only the artifact type (§13). |
| 8 | §1.3.1 + §18 U-10 | *"`FIXED_GIT_OPERATIONS` has no whole-repository diff … a real gap for AR1"* | **Answered: not a gap.** Zero widening required (§12). |
| 9 | §5 | The trust-boundary diagram | **Superseded** by §8, which routes filesystem access through AIDO-authored code. |
| 10 | §11.3 | *"Environment minimization is not filesystem isolation"* | **Still correct — reinforce, do not weaken.** Add that tool-layer confinement is not filesystem isolation either (§4.4). |
| 11 | §14.4 | The negative-control list | **Extend** with N4, the confinement negative control (§9). |
| 12 | §17.4 | *"`CLAUDE.md`'s 'exactly two subprocess capabilities exist' becomes stale if AR1 ships"* | **Deferred further.** With AR1 experiment-only, the sentence stays true; revisit at promotion (§10). |

New unknowns to fold into AR0 §18 later:

- **U-12** — does `pi.registerTool` accept a dependency-free plain-object schema,
  and how does a disposable extension directory resolve its imports? (N8)
- **U-13** — does the confining extension load correctly in `--mode rpc`
  specifically, where there is no TUI (`ctx.ui` must not be used)?
- **U-14** — does Pi's OpenAI-completions request to the vLLM route in fact carry
  no `max_tokens` for the main agent stream? (§11; source-derived, and not
  AIDO-observable.)

---

## 17. Deliverable summary

This follow-up delivers: the precise statement of AR0's one blocking contradiction
(§1); a verified local isolation-capability inventory (§2); the Option A analysis
and its unavailability (§3); the Option B analysis with source-level Pi evidence
and a fail-closed design (§4); the Option C rejection (§5); **the decision — B, in
its narrowest B-fixed form, with A as the deferred escalation** (§6); the
control-plane fit (§7); a revised trust boundary (§8); the revised AR1 topology
(§9); the experiment-only placement decision (§10); the token-policy correction
(§11); the Git-observation conclusion (§12); the reviewer-adapter conclusion (§13);
the remaining risks (§14); the revised conditional GO (§15); and the AR0 statements
needing later annotation (§16).

**Nothing was implemented. No model was called. The next slice is AR1, scoped
exactly by §15, and gated on §6.**
