/*
 * Phase 5F3A-AR1 - AIDO tool construction, with Pi's tool factories injected.
 *
 * This module imports nothing from Pi. The two factory functions are passed in,
 * which is what lets the offline confinement harness exercise the REAL Pi tool
 * code (loaded by absolute path) without any model, network, or Pi process.
 *
 * DISTINCT NAMES ARE THE FAIL-CLOSED CONTROL (FU1 4.3.1):
 *   These tools are registered as `aido_read` / `aido_edit`. They do NOT
 *   override Pi's built-in `read` / `edit`. A failed extension load therefore
 *   leaves the registry with ZERO tools matching the `--tools` allowlist, so
 *   the model gets no filesystem capability at all -- rather than silently
 *   falling back to Pi's unconfined built-ins.
 *
 * There is deliberately no aido_write in AR1: no architecture question here
 * requires whole-file creation or overwrite.
 */

import {
  createGuardedEditOperations,
  createGuardedReadOperations,
  type AidoAr1Config,
  type ConfinementAudit,
  type RawFileSystem,
} from "./confinement.ts";

/** The two Pi factories this module needs, injected rather than imported. */
export interface PiToolFactories {
  createReadToolDefinition: (cwd: string, options?: unknown) => Record<string, unknown>;
  createEditToolDefinition: (cwd: string, options?: unknown) => Record<string, unknown>;
}

export const AIDO_READ_TOOL_NAME = "aido_read";
export const AIDO_EDIT_TOOL_NAME = "aido_edit";
export const AIDO_SENTINEL_COMMAND = "aido_confinement_active";

/**
 * Strip Pi's TUI renderers.
 *
 * AR1 runs `--mode rpc`, where there is no TUI. `renderCall` / `renderResult`
 * are optional on ToolDefinition, so dropping them removes a code path that has
 * no business running in RPC mode (AR0-FU1 unknown U-13).
 */
function withoutRenderers(definition: Record<string, unknown>): Record<string, unknown> {
  const copy: Record<string, unknown> = { ...definition };
  delete copy.renderCall;
  delete copy.renderResult;
  return copy;
}

export interface BuiltAidoTools {
  readonly readDefinition: Record<string, unknown>;
  readonly editDefinition: Record<string, unknown>;
  readonly audit: ConfinementAudit;
}

export function buildAidoToolDefinitions(
  config: AidoAr1Config,
  cwd: string,
  factories: PiToolFactories,
  fs: RawFileSystem,
  audit: ConfinementAudit,
): BuiltAidoTools {
  const readOperations = createGuardedReadOperations(config.readAllowlist, fs, audit);
  const editOperations = createGuardedEditOperations(config.editAllowlist, fs, audit);

  const baseRead = factories.createReadToolDefinition(cwd, {
    autoResizeImages: false,
    operations: readOperations,
  });
  const baseEdit = factories.createEditToolDefinition(cwd, {
    operations: editOperations,
  });

  const readDefinition = {
    ...withoutRenderers(baseRead),
    name: AIDO_READ_TOOL_NAME,
    label: AIDO_READ_TOOL_NAME,
    description:
      "Read the contents of one file from the small fixed set of files this " +
      "task is allowed to touch. Any other path is refused.",
    promptSnippet: "Read one of the allowed files",
    promptGuidelines: [
      "Use aido_read to examine an allowed file. Only the files named in the task are readable.",
    ],
  };

  const editDefinition = {
    ...withoutRenderers(baseEdit),
    name: AIDO_EDIT_TOOL_NAME,
    label: AIDO_EDIT_TOOL_NAME,
    description:
      "Edit one allowed file using exact text replacement. Every edits[].oldText " +
      "must match a unique, non-overlapping region of the original file. Any path " +
      "outside the allowed set is refused.",
    promptSnippet: "Edit the allowed file with exact text replacement",
    promptGuidelines: [
      "Use aido_edit for precise changes (edits[].oldText must match the original file exactly).",
      "aido_edit may only change the file the task names as editable.",
    ],
  };

  return { readDefinition, editDefinition, audit };
}
