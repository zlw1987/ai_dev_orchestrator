/*
 * Phase 5F3A-AR2 - the two AIDO tool definitions. EXPERIMENT ONLY.
 *
 * DISTINCT NAMES ARE THE FAIL-CLOSED CONTROL:
 *   These are registered as `aido_read` / `aido_edit`. They do NOT override Pi's
 *   built-in `read` / `edit`. Combined with `--tools aido_read,aido_edit`, a
 *   failed extension load leaves the registry with ZERO tools matching the
 *   allowlist, so the model gets no filesystem capability at all -- rather than
 *   silently falling back to Pi's unconfined built-ins. `--no-builtin-tools` is
 *   passed belt-and-braces and is NOT relied on as the security property.
 *
 * These definitions perform NO authorization. Each one serializes its arguments
 * and returns what the broker said. Every decision -- containment, manifest
 * membership, exclusions, protected/witness status, caps, write-after-read --
 * is made in AIDO's Python broker, per request, from the accepted canonical
 * primitives.
 *
 * There is deliberately no aido_write, no aido_list, no aido_search, no
 * aido_verify, and no shell.
 */

import { Type } from "typebox";

import { brokerCall } from "./ipc.ts";

export const AIDO_READ_TOOL_NAME = "aido_read";
export const AIDO_EDIT_TOOL_NAME = "aido_edit";
export const AIDO_SENTINEL_COMMAND = "aido_ar2_broker_active";
export const AIDO_TOOL_NAMES: readonly string[] = [
  AIDO_READ_TOOL_NAME,
  AIDO_EDIT_TOOL_NAME,
];

interface ToolTextResult {
  content: { type: "text"; text: string }[];
  details: Record<string, unknown>;
}

function text(body: string, details: Record<string, unknown>): ToolTextResult {
  return { content: [{ type: "text", text: body }], details };
}

export function buildReadToolDefinition(): Record<string, unknown> {
  return {
    name: AIDO_READ_TOOL_NAME,
    label: AIDO_READ_TOOL_NAME,
    description:
      "Read one repository file through the AIDO broker. Give the " +
      "repository-relative path exactly as it appears in the task's file list. " +
      "The broker decides whether the file may be read; some files are readable " +
      "and some are refused. The reply includes a sha256 you must pass to " +
      "aido_edit as base_sha256 when editing that same file.",
    promptSnippet: "Read one repository file through the AIDO broker",
    promptGuidelines: [
      "Use aido_read to read a repository file before reasoning about it; the broker refuses anything it does not permit.",
      "Use aido_read on a file before calling aido_edit on it: aido_edit requires the sha256 that aido_read returned.",
    ],
    parameters: Type.Object({
      path: Type.String({
        description:
          "Repository-relative path of the file to read, exactly as listed in the task.",
      }),
    }),
    async execute(
      _toolCallId: string,
      params: { path: string },
    ): Promise<ToolTextResult> {
      const result = await brokerCall(AIDO_READ_TOOL_NAME, "read_file", {
        path_candidate: params.path,
      });
      const body =
        `aido_read ok: bytes=${String(result.bytes)} ` +
        `sha256=${String(result.sha256)} encoding=${String(result.encoding)} ` +
        `contains_crlf=${String(result.contains_crlf)}\n` +
        `Pass that sha256 as base_sha256 if you edit this file.\n` +
        `--- file content follows ---\n${String(result.text)}`;
      return text(body, {
        bytes: result.bytes,
        sha256: result.sha256,
        contains_crlf: result.contains_crlf,
      });
    },
  };
}

export function buildEditToolDefinition(): Record<string, unknown> {
  return {
    name: AIDO_EDIT_TOOL_NAME,
    label: AIDO_EDIT_TOOL_NAME,
    description:
      "Edit one repository file through the AIDO broker using exact text " +
      "replacement. old_text must be non-empty and must occur EXACTLY ONCE in " +
      "the current file; new_text replaces it byte for byte. base_sha256 must be " +
      "the sha256 the most recent aido_read (or aido_edit) reported for this " +
      "file. The broker decides whether the file may be edited; some readable " +
      "files are not editable.",
    promptSnippet: "Edit one repository file with exact unique text replacement",
    promptGuidelines: [
      "Use aido_edit for precise changes: old_text must match the current file exactly and appear exactly once.",
      "Use aido_edit only after aido_read on the same file, and pass the sha256 aido_read returned as base_sha256.",
      "If aido_edit is refused, do not retry the same edit unchanged and do not try to reach the file another way.",
    ],
    parameters: Type.Object({
      path: Type.String({
        description:
          "Repository-relative path of the file to edit, exactly as listed in the task.",
      }),
      base_sha256: Type.String({
        description:
          "The sha256 reported by the most recent aido_read or aido_edit for this file.",
      }),
      old_text: Type.String({
        description:
          "Exact, non-empty text to replace. It must occur exactly once in the file.",
      }),
      new_text: Type.String({ description: "Exact replacement text." }),
    }),
    async execute(
      _toolCallId: string,
      params: {
        path: string;
        base_sha256: string;
        old_text: string;
        new_text: string;
      },
    ): Promise<ToolTextResult> {
      const result = await brokerCall(AIDO_EDIT_TOOL_NAME, "edit_file", {
        path_candidate: params.path,
        base_sha256: params.base_sha256,
        old_text: params.old_text,
        new_text: params.new_text,
      });
      const body =
        `aido_edit applied: bytes_after=${String(result.bytes_after)} ` +
        `sha256_after=${String(result.sha256_after)}\n` +
        `Use that sha256_after as base_sha256 for any further edit to this file.`;
      return text(body, {
        applied: result.applied,
        bytes_after: result.bytes_after,
        sha256_after: result.sha256_after,
      });
    },
  };
}
