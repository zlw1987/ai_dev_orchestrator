/*
 * Phase 5F3A-AR1 - the one explicitly loaded Pi extension.
 *
 * Loaded with:  --no-extensions  -e <disposable dir>/index.ts
 * Exposed with: --tools aido_read,aido_edit      <-- the actual security control
 *
 * It registers exactly two tools and one sentinel command:
 *
 *   aido_read                  guarded ReadOperations, exact-allowlist
 *   aido_edit                  guarded EditOperations, exact-allowlist
 *   /aido_confinement_active   sentinel; proves to AIDO (via get_commands)
 *                              that THIS extension loaded, before any prompt
 *
 * The sentinel proves extension LOAD. It does not by itself prove the contents
 * of the active tool registry: Pi 0.84.2 exposes no RPC command that enumerates
 * tools (AR0-FU1 4.1j / risk N4). AIDO records that distinction rather than
 * overstating it.
 *
 * `ar1_config.ts` is GENERATED next to this file by the Python harness and
 * carries the concrete absolute allowlist. This file is static and reviewable.
 */

import { constants } from "node:fs";
import { access, readFile, writeFile } from "node:fs/promises";
import {
  createEditToolDefinition,
  createReadToolDefinition,
  type ExtensionAPI,
} from "@earendil-works/pi-coding-agent";

import { createAudit, type RawFileSystem } from "./confinement.ts";
import { AIDO_SENTINEL_COMMAND, buildAidoToolDefinitions } from "./tools.ts";
import { AIDO_AR1_CONFIG } from "./ar1_config.ts";

const realFileSystem: RawFileSystem = {
  readFile: (absolutePath: string) => readFile(absolutePath),
  writeFile: (absolutePath: string, content: string) =>
    writeFile(absolutePath, content, "utf-8"),
  accessRead: (absolutePath: string) => access(absolutePath, constants.R_OK),
  accessReadWrite: (absolutePath: string) =>
    access(absolutePath, constants.R_OK | constants.W_OK),
};

export default function aidoAr1Confinement(pi: ExtensionAPI): void {
  const audit = createAudit();
  const built = buildAidoToolDefinitions(
    AIDO_AR1_CONFIG,
    AIDO_AR1_CONFIG.cwd,
    { createReadToolDefinition, createEditToolDefinition },
    realFileSystem,
    audit,
  );

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  pi.registerTool(built.readDefinition as any);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  pi.registerTool(built.editDefinition as any);

  pi.registerCommand(AIDO_SENTINEL_COMMAND, {
    description:
      "AIDO AR1 confinement sentinel. Registration proves this extension loaded.",
    // Deliberately inert, and deliberately free of ctx.ui: RPC mode has no TUI.
    handler: async () => {},
  });
}
