/**
 * CFG1 T-3 -- offline Pi request-shape conformance, under total interception.
 *
 * Runs the INSTALLED Pi 0.85.1 request builder against each arm and reports
 * the exact request payload it produces. Nothing here launches a Pi model
 * session, contacts a provider, or reads a real credential or endpoint.
 *
 * ORDERING IS THE WHOLE POINT. Every network and DNS entry point is replaced
 * with a refusing stub BEFORE the first `await import()` of any installed Pi
 * module. ESM `import` statements hoist, so the Pi modules are loaded
 * dynamically, strictly after interception is installed. Any attempted real
 * network or DNS operation is recorded and reported as a failure -- never
 * swallowed.
 *
 * Reads one JSON config path from argv[2]; writes one JSON report to stdout.
 */

import net from "node:net";
import tls from "node:tls";
import http from "node:http";
import https from "node:https";
import dns from "node:dns";
import { readFileSync } from "node:fs";
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
    holder[key] = refuse(label);
    if (holder[key].name !== undefined) {
      installed.push(label);
      return;
    }
    installed.push(label);
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

const context = {
  systemPrompt: config.systemPrompt,
  messages: [{ role: "user", content: [{ type: "text", text: config.userPrompt }] }],
  tools: config.tools,
};

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
  const serializedModel = JSON.parse(JSON.stringify(model));

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
    params: capturedParams,
    fetchCallsForThisArm: fetchCalls.length - before,
  };
}

report.fetchCalls = fetchCalls;
process.stdout.write(JSON.stringify(report, null, 2));
