/*
 * Phase 5F3A-AR2 cross-language probe. TEST ONLY.
 *
 * Drives the REAL `tools.ts` / `ipc.ts` against the REAL Python broker over a
 * real local Windows named pipe. This is the one seam neither the Python-only
 * nor the Node-only offline test can cover on its own, and covering it here
 * means the live run is not the first time the two halves meet.
 *
 * No model, no network, no Pi process.
 *
 * Emits one JSON object on stdout.
 */

import { argv, exit } from "node:process";

const extensionDir = argv[2];
const base = `file:///${extensionDir.replace(/\\/g, "/")}`;
const tools = await import(`${base}/tools.ts`);

const readTool = tools.buildReadToolDefinition();
const editTool = tools.buildEditToolDefinition();
const results = {};

async function attempt(label, fn) {
  try {
    const value = await fn();
    results[label] = { ok: true, text: value.content[0].text, details: value.details };
  } catch (error) {
    results[label] = { ok: false, name: error.name, message: error.message };
  }
}

// 1. An allowed read.
await attempt("readAllowed", () => readTool.execute("c1", { path: "calc.py" }));

// 2. A refused read: not in the mint-time manifest.
await attempt("readUntracked", () => readTool.execute("c2", { path: "nope.py" }));

// 3. A refused read: forbidden pattern.
await attempt("readForbidden", () => readTool.execute("c3", { path: ".git/config" }));

// 4. A refused edit: the protected verification witness.
const witness = results.readAllowed.ok
  ? await readTool.execute("c4", { path: "test_calc.py" }).catch((e) => e)
  : null;
const witnessSha =
  witness && witness.details ? String(witness.details.sha256) : "0".repeat(64);
await attempt("editWitness", () =>
  editTool.execute("c5", {
    path: "test_calc.py",
    base_sha256: witnessSha,
    old_text: "assert within_limit(10, 10) is True",
    new_text: "assert within_limit(10, 10) is False",
  }),
);

// 5. An allowed edit, using the sha256 the read reported.
const sha = String(results.readAllowed.details.sha256);
await attempt("editAllowed", () =>
  editTool.execute("c6", {
    path: "calc.py",
    base_sha256: sha,
    old_text: "return value < limit",
    new_text: "return value <= limit",
  }),
);

// 6. A stale base hash on the file just edited.
await attempt("editStale", () =>
  editTool.execute("c7", {
    path: "calc.py",
    base_sha256: sha,
    old_text: "return value <= limit",
    new_text: "return value <= int(limit)",
  }),
);

process.stdout.write(JSON.stringify(results, null, 2) + "\n");
exit(0);
