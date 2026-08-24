/*
 * Phase 5F3A-AR2 offline TypeScript harness. TEST ONLY.
 *
 * Drives the REAL extension sources -- `index.ts`, `tools.ts`, `ipc.ts` -- against
 * a stub named-pipe server implemented here in Node. No model, no network, no Pi
 * process, and no Python broker: this file tests only that the extension is the
 * dumb serializer it claims to be.
 *
 * Emits one JSON object on stdout. The Python test asserts against it.
 */

import { createServer } from "node:net";
import { argv, exit } from "node:process";

const extensionDir = argv[2];
const pipeName = argv[3];

const results = {};
const inFlight = { current: 0, maxObserved: 0 };
const receivedFrames = [];

/** The stub broker. It authorizes nothing; it records and replies. */
const server = createServer((socket) => {
  let buffer = "";
  socket.on("data", (chunk) => {
    buffer += chunk.toString("utf-8");
    for (;;) {
      const index = buffer.indexOf("\n");
      if (index < 0) break;
      const line = buffer.slice(0, index);
      buffer = buffer.slice(index + 1);
      if (!line) continue;
      const frame = JSON.parse(line);
      receivedFrames.push(frame);
      inFlight.current += 1;
      inFlight.maxObserved = Math.max(inFlight.maxObserved, inFlight.current);
      const reply =
        frame.path_candidate === "REFUSE_ME"
          ? { v: 1, id: frame.id, ok: false, error: { code: "refused", detail: "operation_not_permitted" } }
          : frame.path_candidate === "MALFORMED_RESPONSE"
            ? { v: 1, id: frame.id, ok: true }
            : frame.op === "read_file"
            ? {
                v: 1,
                id: frame.id,
                ok: true,
                result: {
                  text: "stub content\n",
                  encoding: "utf-8",
                  bytes: 13,
                  sha256: "a".repeat(64),
                  contains_crlf: false,
                },
              }
            : { v: 1, id: frame.id, ok: true, result: { applied: true, bytes_after: 5, sha256_after: "b".repeat(64) } };
      setTimeout(() => {
        inFlight.current -= 1;
        socket.write(JSON.stringify(reply) + "\n");
      }, 40);
    }
  });
});

await new Promise((resolve) => server.listen(pipeName, resolve));

const tools = await import(`file:///${extensionDir.replace(/\\/g, "/")}/tools.ts`);
const extension = await import(`file:///${extensionDir.replace(/\\/g, "/")}/index.ts`);

// -- tool names ---------------------------------------------------------------
results.exportedToolNames = [...tools.AIDO_TOOL_NAMES];
results.sentinelCommandName = tools.AIDO_SENTINEL_COMMAND;

// -- registration through the real index.ts default export --------------------
const registeredTools = [];
const registeredCommands = [];
const fakePi = {
  registerTool: (definition) => registeredTools.push(definition),
  registerCommand: (name) => registeredCommands.push(name),
};
extension.default(fakePi);
results.registeredToolNames = registeredTools.map((d) => d.name);
results.registeredCommandNames = registeredCommands;
results.registeredToolCount = registeredTools.length;
results.everyToolHasParameters = registeredTools.every(
  (d) => typeof d.parameters === "object" && d.parameters !== null,
);
results.everyToolHasExecute = registeredTools.every((d) => typeof d.execute === "function");

const readTool = registeredTools.find((d) => d.name === "aido_read");
const editTool = registeredTools.find((d) => d.name === "aido_edit");

// -- the candidate is sent VERBATIM, with no normalization --------------------
const untrustedCandidates = [
  "calc.py",
  "..\\..\\escape.py",
  "C:\\dev\\mis_project\\secret.py",
  "  spaced.py  ",
  "sub/./dir/../file.py",
  "@calc.py",
  "calc.py:stream",
];
results.verbatimCandidates = [];
for (const candidate of untrustedCandidates) {
  await readTool.execute("c", { path: candidate });
  const sent = receivedFrames[receivedFrames.length - 1];
  results.verbatimCandidates.push({ given: candidate, sent: sent.path_candidate });
}

// -- single flight ------------------------------------------------------------
await Promise.all([
  readTool.execute("p1", { path: "a.py" }),
  readTool.execute("p2", { path: "b.py" }),
  readTool.execute("p3", { path: "c.py" }),
  editTool.execute("p4", {
    path: "d.py",
    base_sha256: "c".repeat(64),
    old_text: "x",
    new_text: "y",
  }),
]);
results.maxConcurrentBrokerRequests = inFlight.maxObserved;

// -- request shape ------------------------------------------------------------
const readFrame = receivedFrames.find((f) => f.op === "read_file");
const editFrame = receivedFrames.find((f) => f.op === "edit_file");
results.readFrameKeys = Object.keys(readFrame).sort();
results.editFrameKeys = Object.keys(editFrame).sort();
results.protocolVersions = [...new Set(receivedFrames.map((f) => f.v))];
results.distinctRequestIds = new Set(receivedFrames.map((f) => f.id)).size;
results.totalFrames = receivedFrames.length;
results.operationsSeen = [...new Set(receivedFrames.map((f) => f.op))].sort();

// -- a broker refusal becomes a thrown tool error -----------------------------
try {
  await readTool.execute("r", { path: "REFUSE_ME" });
  results.refusalThrew = false;
} catch (error) {
  results.refusalThrew = true;
  results.refusalErrorName = error.name;
  results.refusalMessage = error.message;
}

// -- a successful read surfaces the sha256 the model must echo back -----------
const readResult = await readTool.execute("s", { path: "ok.py" });
results.readResultText = readResult.content[0].text;

// -- optional hardening: a malformed broker response fails closed -------------
// MUST run last -- a malformed response is terminal for the whole channel
// (matching the existing non-JSON-line / uncorrelated-id precedent), so no
// further call on this channel would succeed afterward.
try {
  await readTool.execute("m", { path: "MALFORMED_RESPONSE" });
  results.malformedResponseThrew = false;
} catch (error) {
  results.malformedResponseThrew = true;
  results.malformedResponseErrorName = error.name;
}

server.close();
process.stdout.write(JSON.stringify(results, null, 2) + "\n");
exit(0);
