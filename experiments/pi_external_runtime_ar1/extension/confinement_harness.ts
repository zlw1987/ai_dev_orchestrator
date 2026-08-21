/*
 * Phase 5F3A-AR1 - OFFLINE confinement harness.
 *
 * Runs the AIDO-authored tool layer with the REAL Pi 0.84.2 tool factories,
 * loaded from an absolute path, with NO model, NO network, NO Pi process and
 * NO API key. It executes the tools' own `execute()` entry points, so what is
 * tested is the same code path a model tool call would take.
 *
 * Usage:
 *   node confinement_harness.ts <pi-dist-index.js> <topology.json>
 *
 * The topology JSON is written by the Python harness and names:
 *   { cwd, repoDir, calcPath, testPath, outsideCanaryPath }
 *
 * It prints ONE JSON object (ASCII-only) on stdout describing every case.
 * A non-zero exit means the harness itself failed, not that a case failed.
 */

import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

import { createAudit, type RawFileSystem } from "./confinement.ts";
import { buildAidoToolDefinitions } from "./tools.ts";

interface Topology {
  cwd: string;
  repoDir: string;
  calcPath: string;
  testPath: string;
  outsideCanaryPath: string;
}

interface SpyCall {
  op: string;
  path: string;
}

function makeSpyFileSystem(realFs: RawFileSystem, calls: SpyCall[]): RawFileSystem {
  return {
    readFile: async (p: string) => {
      calls.push({ op: "readFile", path: p });
      return realFs.readFile(p);
    },
    writeFile: async (p: string, content: string) => {
      calls.push({ op: "writeFile", path: p });
      return realFs.writeFile(p, content);
    },
    accessRead: async (p: string) => {
      calls.push({ op: "accessRead", path: p });
      return realFs.accessRead(p);
    },
    accessReadWrite: async (p: string) => {
      calls.push({ op: "accessReadWrite", path: p });
      return realFs.accessReadWrite(p);
    },
  };
}

async function main(): Promise<void> {
  const [piIndexPath, topologyPath] = process.argv.slice(2);
  if (!piIndexPath || !topologyPath) {
    throw new Error("usage: confinement_harness.ts <pi-dist-index.js> <topology.json>");
  }
  const topology: Topology = JSON.parse(readFileSync(topologyPath, "utf-8"));

  const nodeFs = await import("node:fs/promises");
  const nodeFsConstants = (await import("node:fs")).constants;
  const realFs: RawFileSystem = {
    readFile: (p: string) => nodeFs.readFile(p),
    writeFile: (p: string, content: string) => nodeFs.writeFile(p, content, "utf-8"),
    accessRead: (p: string) => nodeFs.access(p, nodeFsConstants.R_OK),
    accessReadWrite: (p: string) =>
      nodeFs.access(p, nodeFsConstants.R_OK | nodeFsConstants.W_OK),
  };

  const pi = await import(pathToFileURL(piIndexPath).href);

  const calls: SpyCall[] = [];
  const audit = createAudit();
  const built = buildAidoToolDefinitions(
    {
      experiment: "5F3A-AR1-offline-confinement",
      cwd: topology.cwd,
      readAllowlist: [topology.calcPath, topology.testPath],
      editAllowlist: [topology.calcPath],
    },
    topology.cwd,
    {
      createReadToolDefinition: pi.createReadToolDefinition,
      createEditToolDefinition: pi.createEditToolDefinition,
    },
    makeSpyFileSystem(realFs, calls),
    audit,
  );

  const readTool = built.readDefinition as {
    name: string;
    execute: (
      id: string,
      params: unknown,
      signal: undefined,
      onUpdate: undefined,
      ctx: unknown,
    ) => Promise<unknown>;
  };
  const editTool = built.editDefinition as typeof readTool;

  const results: Record<string, unknown> = {};

  async function runCase(
    label: string,
    tool: typeof readTool,
    params: unknown,
  ): Promise<void> {
    const callsBefore = calls.length;
    try {
      const result = await tool.execute("t-" + label, params, undefined, undefined, {});
      results[label] = {
        ok: true,
        underlying_fs_calls: calls.slice(callsBefore).map((c) => c.op),
        text: extractText(result),
      };
    } catch (error) {
      results[label] = {
        ok: false,
        error_name: error instanceof Error ? error.name : "unknown",
        error_message: error instanceof Error ? error.message : String(error),
        underlying_fs_calls: calls.slice(callsBefore).map((c) => c.op),
      };
    }
  }

  function extractText(result: unknown): string {
    const content = (result as { content?: { type: string; text?: string }[] }).content;
    if (!Array.isArray(content)) return "";
    return content
      .filter((block) => block.type === "text")
      .map((block) => block.text ?? "")
      .join("\n");
  }

  // 1/2 - allowed reads.
  await runCase("read_calc_allowed", readTool, { path: topology.calcPath });
  await runCase("read_test_allowed", readTool, { path: topology.testPath });
  await runCase("read_calc_relative_allowed", readTool, { path: "calc.py" });

  // 3 - allowed synthetic edit.
  await runCase("edit_calc_allowed", editTool, {
    path: topology.calcPath,
    edits: [{ oldText: "return value < limit", newText: "return value <= limit" }],
  });

  // 4 - absolute outside-canary read refusal.
  await runCase("read_outside_canary_absolute_refused", readTool, {
    path: topology.outsideCanaryPath,
  });

  // 5 - traversal-shaped refusal (resolves outside the allowed set).
  await runCase("read_traversal_refused", readTool, {
    path: "..\\outside_canary.txt",
  });
  await runCase("read_traversal_posix_refused", readTool, {
    path: "../outside_canary.txt",
  });

  // 6 - edit refusal on the outside canary.
  await runCase("edit_outside_canary_refused", editTool, {
    path: topology.outsideCanaryPath,
    edits: [{ oldText: "CANARY", newText: "TOUCHED" }],
  });

  // Extra: a file inside the repo that is NOT on the edit allowlist.
  await runCase("edit_test_calc_refused", editTool, {
    path: topology.testPath,
    edits: [{ oldText: "def ", newText: "def  " }],
  });

  const payload = {
    harness: "5F3A-AR1 offline confinement",
    tool_names: [readTool.name, editTool.name],
    cases: results,
    audit_refusals: audit.refusals,
    all_underlying_fs_call_paths: calls.map((c) => ({ op: c.op, path: c.path })),
  };
  process.stdout.write(JSON.stringify(payload) + "\n");
}

main().catch((error: unknown) => {
  process.stderr.write(String(error instanceof Error ? error.stack : error) + "\n");
  process.exit(2);
});
