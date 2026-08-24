/*
 * Phase 5F3A-AR2 - the one explicitly loaded Pi extension. EXPERIMENT ONLY.
 *
 * Loaded with:  --no-extensions  --extension <disposable dir>/index.ts
 * Exposed with: --tools aido_read,aido_edit      <-- the actual registry control
 *
 * It registers exactly two tools and one sentinel command:
 *
 *   aido_read                  broker-backed read       (no local authority)
 *   aido_edit                  broker-backed edit       (no local authority)
 *   /aido_ar2_broker_active    sentinel; proves to AIDO, via get_commands and
 *                              the H1 identity gate, that THIS extension loaded
 *                              at THIS path, before any prompt is sent
 *
 * The sentinel proves extension LOAD. It does not by itself prove the contents
 * of the active tool registry: Pi 0.84.2 exposes no RPC command that enumerates
 * tools. AIDO records that distinction rather than overstating it. The same
 * limit applies to the broker: a broker that receives only read_file and
 * edit_file requests is evidence about what was REQUESTED through the broker,
 * never proof of what the registry contained.
 *
 * `ar2_config.ts` is GENERATED next to this file by the Python harness. It
 * carries the per-run pipe name, capability id and token. Those values are
 * AIDO's, exist only for this run, never enter a model prompt, are never logged
 * or printed, and are never persisted into any experiment artifact.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

import {
  AIDO_SENTINEL_COMMAND,
  buildEditToolDefinition,
  buildReadToolDefinition,
} from "./tools.ts";

export default function aidoAr2Broker(pi: ExtensionAPI): void {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  pi.registerTool(buildReadToolDefinition() as any);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  pi.registerTool(buildEditToolDefinition() as any);

  pi.registerCommand(AIDO_SENTINEL_COMMAND, {
    description:
      "AIDO AR2 broker sentinel. Registration proves this extension loaded.",
    // Deliberately inert, and deliberately free of ctx.ui: RPC mode has no TUI.
    handler: async () => {},
  });
}
