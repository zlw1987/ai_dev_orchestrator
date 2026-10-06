/**
 * CFG1 T-3 -- offline Pi request-shape conformance, under total interception.
 *
 * Runs the INSTALLED Pi request builder against each arm and reports the exact
 * request payload it produces. Nothing here launches a Pi model session,
 * contacts a provider, or reads a real credential or endpoint. It never imports
 * the CLI, the main entry, RPC mode or extension loading: the only installed
 * modules it loads are the four named by the config (the model-config loader,
 * the provider composer, the transcript normalizer and the openai-completions
 * request builder).
 *
 * ORDERING IS THE WHOLE POINT. Every network and DNS entry point is replaced
 * with a refusing stub BEFORE the first `await import()` of any installed Pi
 * module; the harness ABORTS if any of those replacements could not be verified
 * (the assigned function read back by identity); and the Node engine
 * prerequisite is checked after that and BEFORE any installed import too. ESM
 * `import` statements hoist, so the Pi modules are loaded dynamically, strictly
 * after interception is installed and the engine is validated. Any attempted
 * real network or DNS operation is recorded and reported as a failure -- never
 * swallowed.
 *
 * The harness carries NO identity claim about the installed Pi: which payload
 * this ran against is established by the Python caller's own observations, not
 * by anything reported here.
 *
 * Reads one JSON config path from argv[2]; writes one JSON report to stdout.
 */

import net from "node:net";
import tls from "node:tls";
import http from "node:http";
import https from "node:https";
import dns from "node:dns";
import { readFileSync, writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

// ---------------------------------------------------------------------------
// 1. Interception, installed FIRST
// ---------------------------------------------------------------------------

const violations = [];
const installed = [];
const failedToInstall = [];

function refuse(name) {
  return (...args) => {
    violations.push(name);
    throw new Error(`CFG1-T3 refused a real network/DNS operation: ${name}`);
  };
}

function install(holder, key, label) {
  try {
    const refusing = refuse(label);
    holder[key] = refusing;
    // Read the property BACK and require the very function assigned: a setter that
    // swallows the write, or a property that keeps its old value, is a failure.
    if (holder[key] === refusing) {
      installed.push(label);
      return;
    }
    failedToInstall.push(label);
  } catch (error) {
    failedToInstall.push(label);
  }
}

install(globalThis, "fetch", "globalThis.fetch");
install(net, "connect", "net.connect");
install(net, "createConnection", "net.createConnection");
install(tls, "connect", "tls.connect");
install(http, "request", "http.request");
install(https, "request", "https.request");
install(dns, "lookup", "dns.lookup");
for (const key of Object.keys(dns)) {
  if (key.startsWith("resolve")) install(dns, key, `dns.${key}`);
}
if (dns.promises) {
  install(dns.promises, "lookup", "dns.promises.lookup");
  for (const key of Object.keys(dns.promises)) {
    if (key.startsWith("resolve")) install(dns.promises, key, `dns.promises.${key}`);
  }
}

// ---------------------------------------------------------------------------
// 1b. Interception must have FULLY succeeded -- or nothing installed ever loads
// ---------------------------------------------------------------------------
//
// This abort runs after EVERY interception attempt above and before the Node
// version check, before the config is consumed, and before the first installed
// Pi import. A failed or unverified interception therefore makes installed-Pi
// execution unreachable; it is never merely recorded for a caller to notice later.

if (
  failedToInstall.length > 0 ||
  !installed.includes("globalThis.fetch") ||
  !installed.includes("net.connect") ||
  !installed.includes("net.createConnection") ||
  !installed.includes("tls.connect") ||
  !installed.includes("http.request") ||
  !installed.includes("https.request") ||
  !installed.includes("dns.lookup") ||
  !installed.some((label) => label.startsWith("dns.resolve"))
) {
  throw new Error(
    `CFG1-T3 refused: network/DNS interception was not fully installed (failed: ${failedToInstall.join(", ")})`,
  );
}

// ---------------------------------------------------------------------------
// 1c. Node engine prerequisite, checked BEFORE any installed Pi module loads
// ---------------------------------------------------------------------------
//
// The candidate manifest declares `engines.node >= 22.19.0`. This is checked
// here, inside the one authorized Node process, from the version Node reports
// about itself -- not by a pre-launch `--version` probe. The text must FIRST be
// exactly three non-empty ASCII-decimal components; only then are the components
// parsed and compared, as an integer tuple, against 22.19.0. Anything else fails
// closed, including a missing, extra, empty or non-numeric component.

const nodeVersion = process.versions.node;
const nodeVersionParts = typeof nodeVersion === "string" ? nodeVersion.split(".") : [];
const nodeVersionIsExact =
  nodeVersionParts.length === 3 &&
  nodeVersionParts.every((part) => part.length > 0 && [...part].every((char) => "0123456789".includes(char)));
if (!nodeVersionIsExact) {
  throw new Error("CFG1-T3 refused: the reported Node version is not exactly major.minor.patch decimal digits");
}
const nodeTuple = nodeVersionParts.map(Number);
const nodeFloor = [22, 19, 0];
let nodeBelowFloor = false;
for (let position = 0; position < 3; position += 1) {
  if (nodeTuple[position] !== nodeFloor[position]) {
    nodeBelowFloor = nodeTuple[position] < nodeFloor[position];
    break;
  }
}
if (nodeBelowFloor) {
  throw new Error(
    `CFG1-T3 refused: Node 22.19.0 or later is required before any installed Pi import (found ${nodeVersion})`,
  );
}

// ---------------------------------------------------------------------------
// 2. The one injected transport, passed explicitly through request options
// ---------------------------------------------------------------------------

const fetchCalls = [];

function fakeFetch(url, init) {
  fetchCalls.push(String(url));
  const body =
    'data: {"id":"cfg1","object":"chat.completion.chunk","created":0,' +
    '"model":"synthetic","choices":[{"index":0,"delta":{"content":"ok"},' +
    '"finish_reason":"stop"}]}\n\n' +
    "data: [DONE]\n\n";
  return Promise.resolve(
    new Response(body, {
      status: 200,
      headers: { "content-type": "text/event-stream" },
    }),
  );
}

// ---------------------------------------------------------------------------
// 3. The arms, driven through the installed composer and request builder
// ---------------------------------------------------------------------------

const config = JSON.parse(readFileSync(process.argv[2], "utf-8"));

const { ModelConfig } = await import(
  pathToFileURL(config.modelConfigModule).href
);
const { composeModelProvider } = await import(
  pathToFileURL(config.providerComposerModule).href
);
const { streamSimple } = await import(
  pathToFileURL(config.openaiCompletionsModule).href
);
const { normalizeContext } = await import(
  pathToFileURL(config.transcriptModule).href
);

// The installed request builder consumes a TRANSCRIPT, not the raw
// `{systemPrompt, messages, tools}` shape: `normalizeContext` is the installed
// package's own public entry point that folds the system prompt and tools into
// the leading system message, exactly as its own `streamSimple` wrapper does
// before handing a context to a provider. Nothing is hand-assembled here.
const context = normalizeContext({
  systemPrompt: config.systemPrompt,
  messages: [{ role: "user", content: [{ type: "text", text: config.userPrompt }], timestamp: 0 }],
  tools: config.tools,
});

const report = { arms: {}, violations, installed, failedToInstall, fetchCalls: [] };

for (const arm of config.arms) {
  const modelConfig = await ModelConfig.load(arm.modelsJsonPath);
  const loadError = modelConfig.getError();
  if (loadError) {
    report.arms[arm.armId] = { error: `models.json refused: ${loadError}` };
    continue;
  }

  const provider = composeModelProvider(
    config.providerId,
    undefined,
    modelConfig,
    undefined,
  );
  const models = provider.getModels();
  const model = models.find((entry) => entry.id === config.modelId);
  if (!model) {
    report.arms[arm.armId] = { error: "the composed provider served no such model" };
    continue;
  }

  // Sec. 2.5: `get_state` serializes the COMPOSED model object with plain
  // JSON.stringify, so this is exactly the shape a live runtime would report.
  // CFG1-L16-FU2 R-37: the exact serialized TEXT is written to a TEST-LOCAL
  // file beside this arm's models.json -- never into the report, which stays
  // free of the provider id -- so the Python side can wrap it verbatim in a
  // synthetic `get_state` frame and send it through the REAL AR2 receive
  // boundary.
  const serializedModelJson = JSON.stringify(model);
  const serializedModelPath = `${arm.modelsJsonPath}.composed-model.json`;
  writeFileSync(serializedModelPath, serializedModelJson, "utf-8");
  const serializedModel = JSON.parse(serializedModelJson);

  let capturedParams = null;
  const before = fetchCalls.length;
  try {
    const stream = streamSimple(model, context, {
      apiKey: config.apiKey,
      fetch: fakeFetch,
      reasoning: "medium",
      maxRetries: 0,
      onPayload: (params) => {
        capturedParams = JSON.parse(JSON.stringify(params));
        return undefined;
      },
    });
    // Drain, so the injected transport is genuinely exercised rather than
    // merely supplied.
    for await (const _event of stream) {
      // discarded: T-3 asserts the REQUEST shape, never the response content
    }
  } catch (error) {
    report.arms[arm.armId] = {
      ...(report.arms[arm.armId] ?? {}),
      streamError: String(error && error.message ? error.message : error),
    };
  }

  report.arms[arm.armId] = {
    ...(report.arms[arm.armId] ?? {}),
    serializedModelHasCompatKey: Object.prototype.hasOwnProperty.call(
      serializedModel,
      "compat",
    ),
    serializedCompat: serializedModel.compat ?? null,
    serializedModelReasoning: serializedModel.reasoning,
    serializedModelPath,
    params: capturedParams,
    fetchCallsForThisArm: fetchCalls.length - before,
  };
}

report.fetchCalls = fetchCalls;
process.stdout.write(JSON.stringify(report, null, 2));
