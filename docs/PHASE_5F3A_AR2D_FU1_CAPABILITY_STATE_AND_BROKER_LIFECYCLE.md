# Phase 5F3A-AR2D-FU1 — Capability State and Broker Lifecycle Correction

> **DESIGN ONLY.** Nothing was implemented. No model was called, no network
> request was made, no Pi process was launched, no agent mode was entered, no
> production source under `src/` was modified, nothing was committed or pushed,
> and no real project workspace was read, listed, stat'ed, resolved, or touched.
> No historical result JSON was modified. The only files changed by this slice
> are named in §12.
>
> **The Win32 measurements in §6 came from throwaway probe scripts run in the
> session scratchpad against local named pipes only.** They are local IPC on this
> host: no socket, no network, no model, no repository file, no sibling project.
> The probes are deliberately **not** committed (§12.4).

**Authority read for this slice**

- `docs/PHASE_5F3A_AR2D_DELEGATED_WORKSPACE_AUTHORITY_DESIGN.md` (AR2D)
- `docs/PHASE_5F3A_AR0_PI_EXTERNAL_RUNTIME_BOUNDARY_DESIGN.md` (AR0) — §9.6
  termination ladder, for the claim vocabulary reused here
- `docs/PHASE_5F3A_AR0_FU1_PI_RUNTIME_CONFINEMENT_DESIGN.md` (AR0-FU1)
- `experiments/pi_external_runtime_ar1/` — supervisor bounds, protocol
  discipline, and the sanitized result records

**Scope.** This follow-up corrects **exactly two** defects independent review
found in AR2D, and nothing else. AR2D's primary architecture —

```text
Pi -> thin TypeScript aido_* tools -> local IPC -> AIDO-owned Python broker
   -> existing Python path/canonical authority -> disposable synthetic repository
```

— is **accepted and not reopened**. Windows named pipe remains the preferred IPC
mechanism (§9). No other AR2D decision is revisited.

---

## 1. The two defects, stated

**D1 — Static eligibility versus write-after-read.** AR2D asserts all three of
"the capability is monotonically shrinking", "nothing a runtime does can make a
previously-illegal candidate legal", and "`edit_file` requires a successful prior
read of that file". The first two are false at the **operational authorization**
level given the third, and the design must not paper over it.

**D2 — Broker thread lifecycle.** AR2D proposes one blocking daemon thread doing
synchronous named-pipe I/O with no cancellation, and treats "if AIDO abandons the
runtime, the broker thread is abandoned with it" as the intended path. That is not
an acceptable **normal** lifecycle for a newly-created AIDO-owned trusted
capability server that holds pipe handles, per-run capability state and
filesystem authority.

Both are corrected below. Neither correction weakens a boundary; D1's correction
is purely a truthfulness/terminology correction, and D2's correction makes the
broker **more** bounded than AR2D proposed.

---

## 2. D1 — the contradiction, exactly

AR2D §6.1 makes a successful broker read a **necessary condition** for
`edit_file`. AR2D §4.3 property 2 and §6.4 then say the capability only ever
shrinks and that a path never becomes writable during a run. Play the sequence:

```text
t0  mint: foo.py is in the write domain (tracked, not protected, not a witness)
t0  edit(foo.py)  -> REFUSED   (no read receipt for foo.py exists yet)
t1  read(foo.py)  -> permitted, AIDO records base_sha256
t2  edit(foo.py)  -> AUTHORIZED
```

The set of `(operation, path)` pairs AIDO will authorize **grew** between `t0` and
`t2`. AR2D's §6.4 sentence "the legal write set for the whole run is a function of
the mint, not of the run's history" is therefore false as written: the *eligible*
set is a function of the mint; the *authorizable-now* set is a function of the
mint **and** the AIDO-owned run state.

Two things AR2D collapsed into one word must be separated:

```text
"the path entered the capability"          <- NEVER happens. The domain is minted.
"the operation's fixed preconditions are   <- happens routinely, and is the whole
 now satisfied"                               point of write-after-read.
```

AR2D §6.3's closing sentence — *"It is a **precondition on an operation**, not a
widening of the domain"* — already had the right idea. The defect is that §4.3,
§6.2 and §6.4 do not speak that way, and the document's headline vocabulary
("monotonically shrinking", "availability only ever decreases", "a path never
becomes writable during a run") contradicts it.

---

## 3. D1 corrected — the two-layer capability state model

### 3.1 The canonical sentence

> **The static read/write eligibility domains are immutable after mint and never
> expand. Runtime events may satisfy fixed operation preconditions, such as the
> write-after-read precondition, while consumption budgets can only reduce
> remaining authority. No runtime request can add a new path, operation class,
> exclusion exception, cap, root, or privilege to the minted capability.**

That sentence replaces "monotonically shrinking" everywhere it is used as a
description of the capability as a whole. Use it verbatim.

### 3.2 Layer 1 — STATIC ELIGIBILITY DOMAIN (SED)

Fixed at mint, before the runtime launches. **Immutable for the run: it never
expands and it never contracts.**

```text
SED = ( canonical_root,
        root_class = "disposable_synthetic",
        operation_classes  = {read_file, edit_file},
        read_eligibility   predicate + mint-time ls_files_stage manifest,
        write_eligibility  predicate, a PROPER SUBSET of read_eligibility,
        exclusions         forbidden > outside-domain > protected,
        cap_definitions    the numbers themselves, not the remaining balances,
        lifetime           one runtime process )
```

`path ∈ SED(op)` is decided **only** from mint-time facts plus the filesystem
kind/form checks that must be re-run per request (AR2D §12.2 L1). It is not a
function of anything the runtime did.

**AR2D §5.1's condition (g) — "within the run's remaining aggregate caps" — is
NOT a static eligibility condition.** It is a dynamic precondition and belongs in
Layer 2. The same applies to AR2D §6.1's "has already been successfully read
through the broker in this run" and "the caps for changed files / bytes still
allow it". Everything else in §5.1 and §6.1 is static eligibility.

### 3.3 Layer 2 — RUN STATE (RS) and FIXED OPERATION PRECONDITIONS

`RS` is **AIDO-owned, AIDO-authored, and mutable**. Nothing in it is supplied,
named or negotiated by the runtime; the runtime can only cause AIDO to update it
by performing an operation AIDO already decided to authorize.

```text
RS = ( read_receipts      : relative_path -> latest AIDO-recorded sha256
       consumed_budgets   : read_ops, read_bytes, edit_ops, write_bytes,
                            changed_files
       in_flight          : the single-flight slot (AR2D SS 9.4)
       terminal_flags     : protocol_terminal | unauthorized | shutdown_requested
       lifecycle_state    : SS 7.1 )
```

The **preconditions themselves are fixed at mint** and are never added to,
removed, or reweighted during the run. Only their *satisfaction* varies:

| Operation | Fixed preconditions evaluated against RS |
|---|---|
| `read_file` | remaining read-op count > 0; remaining aggregate read bytes ≥ this file; no terminal flag set; single-flight slot free |
| `edit_file` | a read receipt exists for this path **and** the presented `base_sha256` equals the latest recorded receipt; remaining edit-op count > 0; remaining write bytes ≥ post-image delta; changed-file count still allows this path; no terminal flag set; single-flight slot free |

### 3.4 The three monotonicity facts, stated correctly

```text
SED                  IMMUTABLE            never expands, never contracts
remaining budgets    NON-INCREASING       consumption only; never refilled
terminal flags       MONOTONE             once terminal, terminal for the run
OPERATIONALLY-       NOT MONOTONE         may become satisfiable (a read receipt
INVOCABLE SET                             appears) and may become unsatisfiable
                                          (a budget is exhausted)
```

Define it once, and name it, so nobody has to guess which one a sentence means:

```text
OIS(t) = { (op, path) : path in SED(op)
                        AND every fixed precondition of op is satisfied by RS(t) }
```

**`OIS` is not monotone. `SED` is immutable. Remaining authority is
non-increasing.** All three are true simultaneously, and no sentence in AR2 may
assert monotonic shrinkage of the capability as a whole.

### 3.5 Why the after-the-fact analyzability argument survives

AR2D §6.4 justified its wording with analyzability. That justification is intact
under the corrected model, with one word changed:

> The run is analyzable because `SED` is fixed at mint and `RS` is **AIDO-authored
> and fully recorded**. Replaying the recorded request sequence against the
> recorded `RS` transitions reproduces every verdict AIDO issued. The *eligible*
> write set for the whole run is a function of the mint alone; the *invocable* set
> at any instant is a function of the mint and of AIDO's own run state. Neither is
> a function of anything the runtime chose.

### 3.6 One precondition question AR2D left open, answered here

After a successful `edit_file`, AIDO **replaces** that path's read receipt with
the post-image `sha256` it just computed, so a second edit to the same file needs
no second read.

- It is not domain growth: the path was already in the write eligibility domain
  and already had a receipt.
- It is not a blind write: the runtime observed the pre-image and authored the
  exact splice, and AIDO — not the runtime — computed the new hash.
- It does not refill a budget: the edit-op, write-byte and changed-file counters
  are consumed normally.

The alternative (invalidate the receipt and force a re-read) was considered and
rejected: it burns read budget to re-learn a fact AIDO itself just derived, and it
buys no property the `base_sha256` precondition does not already give.

### 3.7 Terminology that must not survive into AR2

| Do not write | Write instead |
|---|---|
| "the capability is monotonically shrinking" | "the eligibility domain is immutable; remaining authority is non-increasing" |
| "nothing a runtime does can make a previously-illegal candidate legal" | "no runtime request can add a path, operation class, exclusion exception, cap, root, or privilege to the minted capability" |
| "a path never becomes writable during a run" | "a path never **enters** the write domain during a run; a path already in it becomes **invocable** for `edit_file` only once the fixed preconditions are satisfied" |
| "availability only ever decreases" | "remaining authority only ever decreases; operational invocability may change in both directions **within** the fixed domain" |
| "the legal write set for the whole run is a function of the mint" | "the **eligible** write set is a function of the mint; the **invocable** set is a function of the mint and of AIDO's own run state" |

---

## 4. Does write-after-read remain? — **YES.**

Retained unchanged as an AR2 control. The analysis does **not** show it unsound;
it shows AR2D described it with the wrong vocabulary.

All three of AR2D §6.3's benefits stand under the corrected model:

1. **No blind writes** — the runtime cannot mutate a file whose content it never
   observed, so every mutation has an inspectable rationale.
2. **AIDO owns a before-image it produced itself**, which is the `base_sha256`
   edit precondition and the stale-read defence (AR2D §15.1).
3. **Read caps gate write caps transitively.**

And it does not widen anything: a read receipt cannot put a path into the write
domain, cannot lift an exclusion, cannot raise a cap, and cannot make a protected
path or a verification witness writable. Those are all `SED` facts, and `SED` is
sealed at mint. **Deleting write-after-read to rescue the old wording is refused;
the wording is what was wrong.**

The write domain remains a proper subset of the read domain, asserted as a
property test (AR2D §6.1), and that assertion is about `SED` only.

---

## 5. D2 — the broker lifecycle defect, stated

AR2D §9.3 and §9.4 propose:

- one blocking daemon thread, synchronous named-pipe I/O;
- no cancellation, on the reasoning that "the outer supervisor already owns the
  deadlines";
- and, if the runtime is abandoned at a deadline, the broker thread is abandoned
  with it, by analogy with RS1's abandoned reviewer worker.

Why that is not acceptable here:

1. **The broker is a trusted capability server, not a client.** It holds a pipe
   handle, the per-run capability, the read receipts and consumed budgets, and it
   is the thing that performs filesystem operations. An abandoned reviewer worker
   holds an outbound HTTP request; an abandoned broker holds **authority**.
2. **RS1's residual is a truthful record of an unavoidable limit, not a design
   pattern.** RS1 abandons a worker because AIDO cannot cancel an in-flight
   provider request. That is a statement about a remote backend AIDO does not
   own. AIDO **does** own the broker, its handles and its I/O, so "abandon it" is
   a choice, and it is the wrong one.
3. **The measured behaviour of the proposed mechanism is worse than AR2D
   assumed** (§6): with *synchronous* pipe I/O, the obvious controller-side
   teardown lever — closing the handle — **blocks the controller too**. That turns
   one blocked broker thread into a blocked orchestrator.
4. **A successful AR2 run must not return while the broker is known to be blocked
   indefinitely.** A run record that says `clean_expected` while an AIDO thread
   still holds live filesystem authority over the workspace that was just
   classified is not an honest record.

---

## 6. Windows evidence

### 6.1 How this evidence was obtained, and its limits

Host: Windows 11 Enterprise 10.0.26200. Interpreter: CPython 3.14.7 (`_winapi`
built in), the same interpreter that would run the broker. Method: small probe
scripts in the session scratchpad, each scenario in its **own** subprocess under a
20–25 s bound so that one hang could not mask the rest. Local named pipes only.

**What this evidence is:** observed behaviour of the exact API surface AR2 would
use, on the exact host and interpreter AR2 would run on.

**What this evidence is not:** it is not a reading of the CPython C source for
`_winapi.Overlapped.cancel` (not available on this host), so *"cancel calls
`CancelIoEx`"* is an **inference**, not an established fact. What is established
is the observable behaviour. Every design decision in §7 depends only on observed
behaviour, and where behaviour was not observed the design **fails closed** (§7.5)
rather than assuming cancellation worked.

Corroborating offline stdlib source, read directly:

- `Lib/multiprocessing/connection.py` — `PipeConnection` is documented as
  requiring `FILE_FLAG_OVERLAPPED`; `_close()` calls `ov.cancel()` with the
  comment *"Interrupt `WaitForMultipleObjects()` in `_send_bytes()`"*, and
  `_send_bytes` treats `ERROR_OPERATION_ABORTED` as *"`close()` was called by
  another thread"*. **CPython itself relies on cross-thread overlapped
  cancellation of named-pipe I/O.**
- `Lib/asyncio/windows_events.py` — `IocpProactor.close()` cancels every
  registered overlapped and then **loops until all cancelled overlapped
  complete**, with the comment *"don't exit with running overlapped to prevent a
  crash"*. This is the source of §7.5's fail-closed rule.

### 6.2 API surface actually available

| Name | In `_winapi`? | Consequence for AR2 |
|---|---|---|
| `CreateNamedPipe`, `ConnectNamedPipe`, `ReadFile`, `WriteFile`, `CloseHandle` | yes | no ctypes binding needed for the pipe itself |
| `Overlapped` with `.event`, `.cancel()`, `.GetOverlappedResult()`, `.getbuffer()` | yes | overlapped I/O and cancellation are reachable from the stdlib |
| `CreateEventW`, `SetEvent`, `ResetEvent`, `WaitForMultipleObjects` | yes | the shutdown event and the multi-object bounded wait are reachable |
| `FILE_FLAG_OVERLAPPED`, `FILE_FLAG_FIRST_PIPE_INSTANCE` | yes | both required flags are constants already |
| `PIPE_REJECT_REMOTE_CLIENTS`, `PIPE_TYPE_BYTE`, `PIPE_READMODE_BYTE` | **no** | pass the literals `0x8`, `0x0`, `0x0` in `pipe_mode`. Values only; no behaviour change |
| `DisconnectNamedPipe` | **no** | **AR2D §9.3's `DisconnectNamedPipe + CloseHandle` close step is not available as written.** `CloseHandle` alone is sufficient and is what AR2 uses (see P7) |
| `CancelIoEx`, `CancelSynchronousIo` | **no** | reachable only through `ctypes`; `Overlapped.cancel()` removes the need for the first |

### 6.3 Measured scenarios

| # | Scenario | Result |
|---|---|---|
| **P1** | `CreateNamedPipe` with a real `SECURITY_ATTRIBUTES` pointer (`ctypes.addressof`), SD built by `advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW` | **Accepted.** The §10 user-scoped DACL is reachable **without** replacing `_winapi` with a full ctypes binding — so the DACL and `Overlapped.cancel()` can both be had |
| **P2** | Second `CreateNamedPipe` on the same name with `FILE_FLAG_FIRST_PIPE_INSTANCE` | Refused, `WinError 231 ERROR_PIPE_BUSY`. AR2D §9.2's squatting claim holds on this host |
| **S1b** | **Synchronous** `ConnectNamedPipe` pending on thread B; `CloseHandle(h)` called from thread A | **`CloseHandle` never returned** (process killed at the 20 s bound, ~19 s inside the call). A 0.4 s heartbeat thread kept printing throughout, so the interpreter was **not** frozen and the GIL was **not** held — the block is `CloseHandle` itself waiting for the pending synchronous I/O. **This is the decisive finding against AR2D's synchronous design** |
| **S2** | Synchronous `ConnectNamedPipe` pending on thread B; `CancelSynchronousIo(OpenThread(B))` from thread A | Worked: `rc=1`, thread B raised `WinError 995 ERROR_OPERATION_ABORTED`, joined within the 3 s window. Technically viable — but see §7.6 |
| **S3b** | **Overlapped** `ConnectNamedPipe`; `WaitForMultipleObjects([ov.event, shutdown], False, 700)` | Returned `258 WAIT_TIMEOUT` at 0.710 s. After `SetEvent(shutdown)` from another thread, a second wait returned index `1` at 0.313 s. Then `ov.cancel()` 0.0000 s → `GetOverlappedResult(True)` → `err=995` in 0.0000 s → `CloseHandle` 0.0000 s |
| **S4** | Overlapped `ConnectNamedPipe` pending; `ov.cancel()` from a **different** thread than the waiter | Waiter woke immediately, reap returned `err=995`. Cross-thread cancellation of a pending connect confirmed |
| **S5b** | Overlapped `ReadFile` pending with a connected but silent client; `rov.cancel()` from another thread | Waiter woke immediately, reap `err=995`, `CloseHandle` 0.0000 s. Cross-thread cancellation of a pending read confirmed |
| **W1** | Overlapped `WriteFile` of 1 MiB stalled by a client that never reads (`err=997 ERROR_IO_PENDING`); 700 ms wait timed out; cancel + reap | `err=995`, `CloseHandle` 0.0000 s. Cross-thread-safe cancellation of a pending write confirmed |
| **W2** | Client closes its handle while a server overlapped `ReadFile` is pending | Server's wait returned at once; reap gave `WinError 109 ERROR_BROKEN_PIPE`. **Pi's exit unblocks the broker by itself** |
| **W3** | `cancel()` → bounded `WaitForMultipleObjects([ov.event], …, 2000)` → `GetOverlappedResult` | Event signalled in 0.0000 s, result `err=995`. The **bounded** reap sequence works; the reap need not be an unbounded `GetOverlappedResult(True)` gamble |
| **W4** | One real LF-framed round trip: client writes 18 bytes, server overlapped-reads | Server received exactly `{"v":1,"id":"r1"}\n`. AR1's framing discipline transfers unchanged |
| **S7** | `cancel()` on an **already completed** overlapped operation | Returned without raising. Teardown is safe to run unconditionally / idempotently |
| **S8** | Dropping the `Overlapped` object while its operation is still pending | Did not crash **in this one observation**. **Explicitly not treated as evidence of safety** — CPython's own proactor waits for cancelled overlapped to complete "to prevent a crash". See §7.5 |
| **S9** | Client `CreateFile` on the pipe name after the server closed its handle | `WinError 2 ERROR_FILE_NOT_FOUND` — the name is gone. AR2D §9.1's "no stale endpoint" claim holds, and `CloseHandle` alone is a sufficient close |

### 6.4 What the evidence settles

Which pending operation can be unblocked, by what, from where:

| Pending operation | Synchronous mode | Overlapped mode |
|---|---|---|
| `ConnectNamedPipe` | only `CancelSynchronousIo` on the blocked thread's handle (S2). `CloseHandle` from another thread **hangs the caller** (S1b) | `Overlapped.cancel()` from **any** thread (S4); also `SetEvent` on a co-waited shutdown event to end the *wait* (S3b) |
| `ReadFile` | not measured; same class as above, same hazard | `Overlapped.cancel()` from **any** thread (S5b); also ends by itself when the client dies (W2) |
| `WriteFile` | not measured; same class as above, same hazard | `Overlapped.cancel()` from **any** thread (W1) |

**Conclusion: overlapped named-pipe I/O gives AR2 a bounded, observable teardown
for all three pending operations, measured in microseconds. Synchronous I/O does
not, and its most obvious teardown lever can block the orchestrator.** AR2D's
premise — that blocking mode is fine because the outer supervisor owns the
deadlines — does not survive contact with `CloseHandle`.

---

## 7. D2 corrected — the broker lifecycle

### 7.1 Explicit states

```text
CREATED  -> READY -> SERVING -> DRAINING -> CLOSED
                                        \-> TEARDOWN_INCOMPLETE   (terminal, honest)
```

| State | Meaning |
|---|---|
| `CREATED` | pipe instance and shutdown event exist; no thread started |
| `READY` | broker thread started and has issued its first overlapped `ConnectNamedPipe`; **Pi has not been launched yet** |
| `SERVING` | client connected; single-flight request/response cycles |
| `DRAINING` | shutdown requested; the broker is cancelling and reaping its own pending operation and closing its handles |
| `CLOSED` | every started overlapped operation reaped, handles closed, **broker thread termination observed** |
| `TEARDOWN_INCOMPLETE` | a bounded teardown step did not complete; recorded truthfully, run classified untrusted for teardown purposes (§7.7, §11) |

### 7.2 Ordering with the runtime

```text
broker create -> READY -> Pi launch -> serve
  -> settle | Pi exit | protocol failure | runtime deadline | AIDO teardown
  -> shutdown requested -> pending IPC unblocked -> handles closed
  -> broker worker termination observed  OR  bounded failure truthfully recorded
```

Two ordering rules:

1. **The broker reaches `READY` before Pi is launched.** A tool call that arrives
   before the server exists must be impossible, not merely unlikely.
2. **The broker is torn down after the Pi termination ladder (AR0 §9.6), and its
   teardown does not depend on Pi being proven stopped.** If AIDO abandoned Pi at
   a deadline, Pi may still be running; closing the pipe simply means a later Pi
   tool call fails at connect (S9: `ERROR_FILE_NOT_FOUND`) and surfaces as an
   `isError` tool result. That is the correct fail-closed direction: capability
   withdrawn first, and never a bypass.

### 7.3 Serve loop — no unbounded wait anywhere

Every wait is a `WaitForMultipleObjects([<op>.event, shutdown_event], False,
slice_ms)`:

- **Idle wait** (between requests, while the model is thinking) is waited in
  slices of `broker_idle_wait_slice_ms` (250 ms). The broker invents **no**
  semantic deadline of its own; idle time is bounded by the existing outer runtime
  deadline, which the controller enforces by signalling shutdown.
- **Frame wait** — from the first byte of a request frame to a complete
  LF-terminated frame — is bounded by `ipc_frame_deadline_seconds` (30 s). This is
  a protocol-integrity bound against a half-sent frame; exceeding it is a
  **terminal** `protocol_error` (AR1's framing discipline: a malformed frame is
  terminal), not a retry.
- **Response write** is bounded the same way. Note W1: a client that stops reading
  can stall a write once the 64 KiB pipe buffer fills, and AR2D's 512 KiB response
  cap exceeds that buffer, so this is a real case, not a theoretical one.
- The single-flight rule (AR2D §9.4) is unchanged, and remains the reason there is
  **at most one** pending overlapped operation at any instant.

### 7.4 Exact shutdown sequence

Ownership rule, stated first because it is what makes the sequence safe:

> **The broker thread owns its handles. The controller signals; it does not
> close.** The controller never calls `CloseHandle` on the pipe (S1b), and never
> touches a file descriptor, a handle or a buffer the broker thread may be inside.
> Its one escalation lever is `Overlapped.cancel()`, which the evidence shows is
> safe to call cross-thread (S4, S5b, W1) and safe to call on an already-completed
> operation (S7).

```text
B0  controller records shutdown_trigger
      in {runtime_settled, pi_exited, runtime_deadline_expired,
          protocol_terminal, unauthorized_frame, aido_teardown}
B1  controller: SetEvent(shutdown_event)                       [measured 0.313 s wake, S3b]
B2  controller: wait broker_shutdown_ack_grace_seconds (2.0)
      broker thread, on waking:
        b1  stop accepting new requests; refuse any in-flight decision
        b2  cancel its own pending overlapped operation, if any
        b3  reap it: bounded wait on ov.event, then GetOverlappedResult
            -> expected err = 995 ERROR_OPERATION_ABORTED           [S3b, S5b, W1, W3]
        b4  CloseHandle(pipe)   -- no DisconnectNamedPipe; not in _winapi, and
                                   CloseHandle alone retires the name       [S9]
        b5  CloseHandle(shutdown_event); publish closed=True; return
B3  ONLY IF the ack grace expires and an overlapped operation is still recorded
    as pending: controller calls Overlapped.cancel() on that recorded operation
      -- cross-thread, proved (S4, S5b, W1); idempotent on a completed op (S7)
      -- the controller still does NOT close any handle
B4  controller: thread.join(broker_teardown_deadline_seconds)  (5.0)
B5  if not thread.is_alive():  state = CLOSED
    else:                      state = TEARDOWN_INCOMPLETE, record the residual
```

There is **no** rung that kills a thread, calls `TerminateThread`, closes a handle
from the controller, calls `CancelSynchronousIo`, sleeps and guesses, retries, or
re-enters the model.

### 7.5 The fail-closed rule where the evidence stops

Cancellation is a **request**. Every measurement showed completion in under a
millisecond, but AIDO must verify the reap rather than assume it. If the reap does
not complete within its bounded wait:

> **Do not close the handle and do not release the `Overlapped` object.** Record
> `TEARDOWN_INCOMPLETE` with `pending_operations_unreaped >= 1` and deliberately
> leak the handle for the life of the process.

The reason is in CPython's own proactor: it cancels and then **waits for every
cancelled overlapped to complete**, explicitly "to prevent a crash". A kernel
write into a released buffer is a strictly worse outcome than a leaked handle in a
short-lived experiment process. S8 observed no crash in one trial; that is **not**
evidence of safety and is not relied on.

### 7.6 Options considered, and why the chosen one wins

| Option | Verdict |
|---|---|
| **A. Synchronous I/O + a controller-thread close/cancel lever** | **Rejected on measured evidence.** `CloseHandle` from the controller did not return in ~19 s while a synchronous `ConnectNamedPipe` was pending (S1b): the lever blocks the orchestrator |
| **B. `CancelSynchronousIo` / `CancelIoEx` via ctypes** | **Rejected, though it works.** S2 shows `CancelSynchronousIo` does unblock a synchronous connect. But it needs a `ctypes` binding plus an `OpenThread` handle for the broker thread, it cancels only *one* pending synchronous operation, and it has a documented race: if it arrives before the thread has entered the blocking call it cancels nothing, so it needs a retry loop with no observable success signal. That is more machinery and less certainty than C, for a strictly worse teardown story |
| **C. Overlapped I/O + an explicit shutdown event** | **CHOSEN.** All three pending operations proved cancellable cross-thread; the wait is interruptible by a `SetEvent` from the controller; the reap is bounded and observable; handle close is instant; the client's death unblocks the read by itself (W2); and the whole path is stdlib-only. `_winapi` supplies every primitive, including the `SECURITY_ATTRIBUTES` pointer needed for the §10 DACL (P1) |
| **D. AIDO-owned broker child process** | **Rejected — §8** |
| **E. Something else** | No candidate improved on C |

### 7.7 Bounded-failure honesty

`TEARDOWN_INCOMPLETE` is a real, recordable outcome, not a bug to hide. It is
recorded with the rung reached, and it makes the run's teardown untrusted (§11).
It must never be reported as a successful teardown, and a run that reaches it must
not print or record a clean broker-lifecycle summary.

---

## 8. Thread versus process — the comparison, and the choice

| Criterion | In-process broker thread | AIDO-owned broker child process |
|---|---|---|
| **Termination observability** | `join(deadline)` + `is_alive()`. With overlapped I/O there is no unbounded blocking call left, so the normal path *observes* termination. A wedged thread cannot be forced | Strictly better: exit status, plus the accepted 5F2D-style terminate/reap-grace/kill ladder |
| **Blocked I/O** | Solved by §7.4: cancel + reap, both measured | Solved by process death |
| **Handle cleanup** | Explicit `CloseHandle` after reap; a leaked handle is possible in the `TEARDOWN_INCOMPLETE` path | Process exit closes everything unconditionally |
| **State transfer** | **None.** Capability, manifest, receipts and budgets are plain in-process objects | The whole `SED` (root, manifest of up to 200 entries, exclusions, caps) plus the per-run token must be serialized across a process boundary and re-validated on the far side |
| **Access to existing Python path authority** | Direct import of `workspace/canonical.py`, the exclusion classifier and `git_adapter`. **This is AR2D §8.2's single strongest argument for B-rpc** and it costs nothing | Requires a second entry point that imports the same modules — workable, but the authority now lives in a process AIDO launches by argv, which is exactly the shape AR2D is trying to keep out of |
| **Secret / token handling** | The per-run token never leaves AIDO's address space; §10.2's "never logged, never persisted, scrub-denylisted" is trivially satisfiable | The token must reach the child by argv (visible in the process list), environment (which AR2D §18 forbids widening), or a stdin handshake. All three are new exposure surfaces for the one value §10.2 says must not travel |
| **Additional subprocess complexity** | None | AIDO would supervise **two** children (Pi and the broker) with two independent deadline ladders that must be correlated, plus a new launch gate, a new environment policy, and a new startup-readiness handshake |
| **Windows semantics** | Overlapped cancellation proved on this host (§6) | Fine, but does not remove the need for correct pipe I/O — it relocates it |
| **Does it become a new general execution capability?** | **No.** No new process is launched | **This is the disqualifier.** A broker child is a third AIDO-launched executable with AIDO-built argv, holding filesystem authority. `CLAUDE.md`'s "exactly two subprocess capabilities exist" and AR2D §28.4's plan to keep that sentence true both break, and the increment is precisely the "general command executor by increments" AR2D §17.2 rejects |
| **Environment boundary** | AR2D §18 unchanged: "the broker runs inside AIDO's own process — it inherits nothing new" | §18 must be rewritten and a whole new child-environment policy justified |

> ## CHOICE: **in-process broker thread, overlapped named-pipe I/O, explicit shutdown event.** One shape, fixed now. AR2 implementation does not get to choose.

The child-process option's one genuine advantage — forcible termination — was the
reason to consider it, and the §6 evidence removes the need for it: with
overlapped I/O the broker thread has no unbounded blocking call to be stuck in, so
`join` normally succeeds. Its disadvantages are structural and permanent. Do
**not** introduce a broker child process, a broker executable, a broker service, a
second supervised child, or a `--broker` entry point in AR2.

---

## 9. Named pipe remains preferred

**Yes — unchanged.** The lifecycle analysis strengthens rather than weakens it:
the corrected teardown is stdlib-only, needs no new dependency, and every step was
measured on this host. Nothing in §6 or §7 argues for loopback TCP (still
connectable by every local process), for a stdio channel (still collides with
AIDO's RPC supervision channel), or for a file drop box.

Verdict **C** — *"named-pipe lifecycle cannot yet be made honest/bounded"* — is
specifically refuted by S3b, S4, S5b, W1, W2 and W3.

### 9.1 Security properties: not reopened

Carried forward from AR2D §9.3 and §10, unchanged: per-run random pipe identity;
`FILE_FLAG_FIRST_PIPE_INSTANCE` (P2 confirms it refuses a squatted name);
`PIPE_REJECT_REMOTE_CLIENTS` (as the literal `0x8`); `nMaxInstances=1`;
current-user DACL (P1 confirms it is reachable through `_winapi`); the per-run
256-bit capability token; strict bounded LF-framed JSONL.

The one truthfulness rule stands verbatim:

> These are **integrity and attribution controls, not OS isolation against a
> same-user adversary.** Never write "the broker is authenticated" without the
> qualifier, and never cite the token as evidence of isolation. Against a same-user
> adversary the broker adds nothing, because that adversary does not need the
> broker.

The lifecycle change touches none of them. It adds `FILE_FLAG_OVERLAPPED` to the
create flags and replaces the close step; the security flags, the DACL, the
instance limit and the token are unaffected.

---

## 10. Deadlines — three, kept separate

| Deadline | Bounds | Owner | Existing? |
|---|---|---|---|
| **Runtime / semantic-turn deadline** (`turn_deadline_seconds`, `startup_deadline_seconds`, `shutdown_deadline_seconds`, `direct_child_reap_grace_seconds`) | AIDO's wait for **Pi**: startup, the one semantic turn, and the AR0 §9.6 termination ladder | AR1 supervisor | **Yes — unchanged** |
| **IPC frame deadline** (`ipc_frame_deadline_seconds`, 30 s) | One partially-received request frame or one response write **inside** the broker | Broker thread | New |
| **Broker teardown deadlines** (`broker_shutdown_ack_grace_seconds` 2.0, `broker_teardown_deadline_seconds` 5.0) | AIDO's wait for **its own broker thread** to acknowledge shutdown and terminate | Controller | New |

Rules, load-bearing:

- **The broker teardown deadline is not a model deadline.** It authorizes **no**
  additional model attempt, no additional prompt, no additional semantic turn, no
  retry of anything, and it does not extend the runtime deadline.
- **It does not change token policy.** `aido_requested_max_output_tokens` remains
  `null`; AIDO imposes **no** model output-token ceiling by default, and the
  generated `models.json` still omits `maxTokens`.
- **Expiry of the runtime deadline is a shutdown *trigger* for the broker, not the
  broker's own deadline.** The two are recorded separately, and a run may have a
  bounded, successful broker teardown after an expired runtime deadline. That
  combination must be reported exactly, never merged into one "timeout".
- The broker never derives a deadline from a model, a prompt, a response, or the
  runtime's behaviour.

---

## 11. What AIDO may and may not claim

### 11.1 After an observed successful teardown (`CLOSED`)

Permitted, because each was observed:

- the broker thread was **observed to terminate** — `join` returned and
  `is_alive()` was false;
- every overlapped operation the broker started was **reaped** — completed, or
  completed as `ERROR_OPERATION_ABORTED` — before its handle was closed; the
  started and reaped counts are recorded and are equal;
- the pipe handle and the shutdown-event handle were closed, and after the close
  the pipe name no longer resolves for a new client (S9), so no further request
  could be accepted through **that** endpoint;
- AIDO performed **no further filesystem operation on the delegated root on the
  runtime's behalf** after teardown;
- the broker-recorded mutated-path set is final and may be cross-checked against
  the independent Git observation (AR2D §15.4).

Forbidden even here — the accepted honesty rules are unchanged:

- **nothing about Pi, Node, the model, the provider, or GPU occupancy.** AIDO's
  broker closing is not Pi stopping;
- not "the workspace was untouched", "no host file outside the workspace was
  touched", "sandboxed", "isolated", or "OS-confined" — AR2D §8.4 stands: the
  broker is a capability boundary for operations **AIDO performs on the runtime's
  behalf**, and a Pi defect, a dependency defect or an out-of-seam path bypasses
  it entirely;
- not "no process holds a handle to the pipe" — the client's handle is the
  client's;
- the broker log remains `broker_recorded_*`: **AIDO-authored and diagnostic
  only**, never repository truth. `orchestrator_observed_*` remains the sole
  authoritative namespace (AR2D §19).

### 11.2 After a teardown timeout or failure (`TEARDOWN_INCOMPLETE`)

**Must not be claimed:**

- that the broker was terminated, stopped, killed, cancelled, cleaned up, or
  finished — Python cannot kill a thread, and none of those were observed;
- that handles were released, that the pipe is closed, or that the pipe name is
  retired;
- that no further broker-mediated read or write can occur — a cancel that had not
  taken effect leaves an operation that may still complete;
- that a file the broker was mid-writing is in either state. Record only the
  pre-image hash AIDO already had and the fact that completion was **not
  observed**;
- that the capability was revoked. It was **requested** to be withdrawn;
- `clean_expected`, or any clean classification resting on a teardown that did not
  complete.

**Must be recorded:** the rung reached, the shutdown trigger, the counts of
started versus reaped overlapped operations, `pending_operations_unreaped`,
whether the controller-side `Overlapped.cancel()` escalation was used, the elapsed
teardown time, and the honest residual sentence:

> AIDO stopped waiting for its broker thread at its own deadline. AIDO did not
> observe the thread terminate. The thread may still hold the pipe handle and the
> per-run capability state, and a pending overlapped operation may still complete.
> The handle was deliberately **not** closed and the `Overlapped` object was
> deliberately **not** released, because completing a cancelled operation into a
> released buffer is worse than leaking a handle.

Restating the chain in broker terms, in the accepted RS1/AR0 shape:

```text
AIDO wait ended  !=  broker thread stopped  !=  pending I/O completed
                 !=  handle released        !=  capability provably withdrawn
```

### 11.3 Record fields

Under the existing `broker_recorded_*` namespace — no new trust namespace is
introduced, and these are facts about **AIDO's own thread and handles**, not about
the repository and not about the runtime:

```text
broker_recorded_lifecycle = {
  state_reached                    CREATED|READY|SERVING|DRAINING|CLOSED|
                                   TEARDOWN_INCOMPLETE
  shutdown_trigger                 runtime_settled | pi_exited |
                                   runtime_deadline_expired | protocol_terminal |
                                   unauthorized_frame | aido_teardown
  rung_reached                     B1..B5
  controller_cancel_escalation_used bool
  overlapped_operations_started    int
  overlapped_operations_reaped     int
  pending_operations_unreaped      int
  handles_closed                   bool
  worker_termination_observed      bool
  teardown_elapsed_seconds         float
  teardown_outcome                 closed_observed | teardown_incomplete
}
```

---

## 12. Files changed

### 12.1 New

| File | Change |
|---|---|
| `docs/PHASE_5F3A_AR2D_FU1_CAPABILITY_STATE_AND_BROKER_LIFECYCLE.md` | **New** — this document |

### 12.2 Minimum targeted edits to AR2D (listed exactly)

Made only where AR2D would otherwise actively contradict this follow-up. Every
edit is documentation-only; no result JSON, no code, no `src/` file was touched.

| # | Location | Edit |
|---|---|---|
| **E1** | top matter, after the DESIGN ONLY banner | Added a "Superseded in part by 5F3A-AR2D-FU1" note naming the two defects and the sections affected |
| **E2** | §4.3 property 2 | Replaced the "Monotonically shrinking" bullet with the immutable-domain / non-increasing-budget / non-monotone-invocability formulation, pointing to FU1 §3 |
| **E3** | §5.1 | Added one sentence marking condition (g) (remaining aggregate caps) as a **dynamic precondition**, not a static eligibility condition |
| **E4** | §6.1 | Added one sentence separating the static eligibility clauses from the two dynamic precondition clauses (prior successful read; remaining caps) |
| **E5** | §6.2 table, row "Path becomes writable dynamically" | Reworded to "A path never **enters** the write domain during a run", with the precondition distinction |
| **E6** | §6.4 | Retitled and rewritten: a path never enters the write domain; preconditions may become satisfied; the eligible-versus-invocable distinction replaces "the legal write set … is a function of the mint" |
| **E7** | §9.1 table, rows "Lifecycle / shutdown" and "Cancellation" | Corrected to the explicit bounded lifecycle and to overlapped cancellation, pointing to FU1 §7 |
| **E8** | §9.3 | `serve` changed to an **overlapped** single-flight thread with a shutdown event; `create` gains `FILE_FLAG_OVERLAPPED`; `close` corrected (no `DisconnectNamedPipe` — it is absent from `_winapi`); the "blocking mode … the broker thread is abandoned with it" paragraph replaced |
| **E9** | §9.4 | The "there is no cancellation" paragraph replaced with the corrected statement: no cancellation in the *wire protocol*, and an explicit AIDO-owned teardown that cancels and reaps pending overlapped operations |
| **E10** | §29.1 table, IPC row | Added `FILE_FLAG_OVERLAPPED`, the bounded observed teardown, and "no broker child process" |
| **E12** | §9.2, the implementation-cost paragraph | Corrected the claim that the named pipe needs full `ctypes` bindings: `_winapi` supplies every pipe call and the `Overlapped` type; `ctypes` is needed only for the `SECURITY_ATTRIBUTES`, and `DisconnectNamedPipe` is absent and unused |

### 12.3 One truthfulness edit outside AR2D

| # | Location | Edit |
|---|---|---|
| **E11** | `experiments/pi_external_runtime_ar1/README.md` "Gating" note | The uncommitted note said the operator-local `experiment_config.json` "is tracked today". A separate operator action (`30d54b7`) has since untracked it, so the sentence is now false. Corrected to record that it **was** committed in `331174d` and untracked in `30d54b7`, and that the remaining step — the experiment-local `.gitignore` — is still the operator's. **No git operation was performed by this slice.** |

**This is not a security incident.** The file carried no credential and no
endpoint value; AR2D §2.3's assessment is unchanged and is not re-litigated here.

### 12.4 Deliberately not created

The §6 probe scripts stay in the session scratchpad and are **not** committed:
they are throwaway feasibility probes, not experiment code, and AR2D §27.2's
retention policy excludes reproducible scratch output. Every scenario in §6.3 is
described precisely enough to be re-derived in a few lines.

Nothing under `src/`, `tests/`, `projects/`, `CLAUDE.md` or the root `README.md`
was modified. AR0 and AR0-FU1 were not rewritten. Nothing was committed and
nothing was pushed.

---

## 13. Guidance files — one narrow clarification, no widening

AR2's guidance-file capability is **not** broadened by this follow-up.

- Automatic / ambient guidance loading stays **disabled** (AR0-FU1's mechanisms,
  unchanged).
- **AR2 forbids broker reads of guidance files** — `AGENTS.md`,
  `AGENTS.override.md`, `CLAUDE.md`, `.cursorrules`,
  `.github/copilot-instructions.md` — and the reason remains AR2D §5.2's:
  an **injection** rule, not a confidentiality rule. Content read through the
  broker is data to AIDO and reads as *instructions* to the model.
- **The one clarification:** this exclusion is a decision about **AR2's broker
  read channel**. It does **not** establish that a future AIDO external runtime can
  never receive intentionally selected, human-approved repository guidance through
  a separate, AIDO-controlled channel. That question is open, and open is not the
  same as decided either way.
- **That channel is not designed here**, not sketched, not named, not
  config-shaped, and not a prerequisite for anything in AR2. Do not build it.

---

## 14. Roadmap note — `google/gemma-4-26B-A4B-it`

One note, recorded once. AR2D lists **no** future-implementer candidate pool, so
nothing is inserted into AR2D for this.

- B300 now also exposes `google/gemma-4-26B-A4B-it`. It is recorded as a candidate
  for the **later Pi implementer qualification** pool (AR2D §24's corpus), and for
  nothing else.
- **Not benchmarked, not smoke-tested, not called.** No reviewer qualification is
  reopened; the accepted reviewer arrangement is untouched.
- **AR2's broker/runtime validation continues on the already-proven Qwen3.6 direct
  path.** The architecture experiment must not change the broker, the provider
  route and the model at the same time, or a failure cannot be attributed —
  exactly the reasoning that makes AR2D §24.1's R1 control mandatory.

---

## 15. Verdict

> # A. AR2 may proceed with a corrected in-process named-pipe broker lifecycle.

One shape, not several: an **in-process** broker thread using **overlapped**
Windows named-pipe I/O with an explicit shutdown event, the §7.4 shutdown
sequence, the §10 separated deadlines, and the §11 claim rules. Option D (a broker
child process) is rejected on §8. Option C (another IPC) is refuted by the §6
evidence. Option B (blocked) does not apply: both defects are correctable, and are
corrected here.

**AR2 implementation is GO**, under AR2D's authority boundary as corrected by this
document, and under every unchanged AR2D constraint: exactly two operations, no
`aido_verify`, no shell, no create/delete/rename, no search or listing, no second
runtime, no generic runtime abstraction, no reviewer integration, no promotion, no
production config field, no CLI command, no `review-packet` change, and no access
to a real project workspace.
