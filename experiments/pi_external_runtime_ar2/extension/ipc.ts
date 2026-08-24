/*
 * Phase 5F3A-AR2 - the broker IPC client. EXPERIMENT ONLY.
 *
 * READ THIS BEFORE CHANGING ANYTHING.
 *
 * This module is a SERIALIZER and a SINGLE-FLIGHT QUEUE. That is the whole job.
 * It deliberately contains, and must never gain:
 *
 *   - no path parsing            - no normalization      - no case folding
 *   - no containment logic       - no allowlist          - no realpath
 *   - no path comparison         - no authorization      - no policy of any kind
 *
 * AR1's `confinement.ts` was ~200 lines of security-critical TypeScript holding
 * a comparison key, an allowlist Map and a `realpathSync.native` cross-check.
 * ALL of it is deleted in AR2. The one path/security authority is AIDO's Python
 * broker, which reuses the accepted 914-line canonical guard rather than a second
 * implementation in a second language. This is a REDUCTION in security-critical
 * TypeScript, not an increase, and it is the strongest argument for B-rpc.
 *
 * The candidate string is sent to the broker VERBATIM, as untrusted input.
 *
 * Single-flight is required, not merely convenient: Pi may dispatch tool calls in
 * parallel, the broker's pipe has `nMaxInstances = 1`, and concurrent edits to
 * one file would make the pre-image hash precondition ambiguous. Serializing is
 * ordinary, non-security logic.
 *
 * There is NO cancellation verb in the wire protocol. No request cancels another,
 * and the runtime cannot ask AIDO to abort anything.
 */

import { connect, type Socket } from "node:net";

import { AIDO_AR2_CONFIG } from "./ar2_config.ts";

const PROTOCOL_VERSION = 1;

export interface BrokerErrorPayload {
  readonly code: string;
  readonly detail: string;
}

/**
 * Fail closed on a malformed broker response (optional hardening, FU-C's
 * sibling for the wire's OTHER end). This is shape validation only -- no path
 * authority, no policy, no new field, and no new protocol capability. A
 * response missing `v`/`id`/`ok`, carrying the wrong protocol version, or
 * mixing `ok` with the wrong one of `result`/`error` is treated exactly like a
 * non-JSON line: terminal, via the existing `fail()` path.
 */
function isWellFormedBrokerResponse(value: unknown): value is BrokerResponse {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  if (candidate.v !== PROTOCOL_VERSION) return false;
  if (typeof candidate.id !== "string" || candidate.id.length === 0) return false;
  if (typeof candidate.ok !== "boolean") return false;
  if (candidate.ok) {
    return typeof candidate.result === "object" && candidate.result !== null;
  }
  const error = candidate.error;
  return (
    typeof error === "object" &&
    error !== null &&
    typeof (error as Record<string, unknown>).code === "string" &&
    typeof (error as Record<string, unknown>).detail === "string"
  );
}

export interface BrokerResponse {
  readonly v: number;
  readonly id: string;
  readonly ok: boolean;
  readonly result?: Record<string, unknown>;
  readonly error?: BrokerErrorPayload;
}

/**
 * A broker refusal, surfaced to Pi as a thrown tool error.
 *
 * The message carries only the broker's coarse closed-set code. It never carries
 * a path, a pattern, a host detail, or the reason the broker refused: the model's
 * picture of the boundary is "that was refused", which is all it needs and all it
 * should have.
 */
export class AidoBrokerRefusedError extends Error {
  readonly code: string;

  constructor(tool: string, code: string) {
    super(
      `${tool} refused by the AIDO broker (${code}). No filesystem operation ` +
        `was performed on your behalf. Do not retry the same request unchanged.`,
    );
    this.name = "AidoBrokerRefusedError";
    this.code = code;
  }
}

export class AidoBrokerUnavailableError extends Error {
  constructor(tool: string) {
    super(
      `${tool} is unavailable: the AIDO broker channel is not open. No ` +
        `filesystem operation was performed on your behalf.`,
    );
    this.name = "AidoBrokerUnavailableError";
  }
}

interface Pending {
  resolve: (value: BrokerResponse) => void;
  reject: (reason: Error) => void;
}

export class BrokerChannel {
  private socket: Socket | null = null;
  private connecting: Promise<Socket> | null = null;
  private buffer = "";
  private readonly pending = new Map<string, Pending>();
  private queue: Promise<unknown> = Promise.resolve();
  private counter = 0;
  private dead = false;
  private readonly pipeName: string;

  // A plain assignment rather than a TypeScript parameter property, so these
  // sources stay inside the type-strippable subset and can be loaded directly.
  constructor(pipeName: string) {
    this.pipeName = pipeName;
  }

  private async open(): Promise<Socket> {
    if (this.socket !== null) return this.socket;
    if (this.connecting !== null) return this.connecting;
    this.connecting = new Promise<Socket>((resolve, reject) => {
      const socket = connect(this.pipeName);
      socket.setNoDelay(true);
      socket.once("connect", () => {
        this.socket = socket;
        resolve(socket);
      });
      socket.once("error", (error: Error) => {
        this.fail(error);
        reject(error);
      });
      socket.on("data", (chunk: Buffer) => this.absorb(chunk));
      socket.on("close", () => this.fail(new Error("broker channel closed")));
    });
    return this.connecting;
  }

  private fail(error: Error): void {
    this.dead = true;
    this.socket = null;
    for (const [, entry] of this.pending) entry.reject(error);
    this.pending.clear();
  }

  /** Strict LF framing. A non-JSON line is a hard failure, never skipped. */
  private absorb(chunk: Buffer): void {
    this.buffer += chunk.toString("utf-8");
    for (;;) {
      const index = this.buffer.indexOf("\n");
      if (index < 0) return;
      const line = this.buffer.slice(0, index);
      this.buffer = this.buffer.slice(index + 1);
      if (line.length === 0) continue;
      let raw: unknown;
      try {
        raw = JSON.parse(line);
      } catch {
        this.fail(new Error("broker response was not strict JSON"));
        return;
      }
      if (!isWellFormedBrokerResponse(raw)) {
        this.fail(new Error("broker response did not match the expected shape"));
        return;
      }
      const parsed: BrokerResponse = raw;
      const entry = this.pending.get(parsed.id);
      if (entry === undefined) {
        this.fail(new Error("broker response did not correlate to a request"));
        return;
      }
      this.pending.delete(parsed.id);
      entry.resolve(parsed);
    }
  }

  /** Serialize ONE request and await ONE response. Strictly single-flight. */
  request(payload: Record<string, unknown>): Promise<BrokerResponse> {
    const run = this.queue.then(
      () => this.send(payload),
      () => this.send(payload),
    );
    this.queue = run.then(
      () => undefined,
      () => undefined,
    );
    return run;
  }

  private async send(payload: Record<string, unknown>): Promise<BrokerResponse> {
    if (this.dead) throw new Error("broker channel is closed");
    const socket = await this.open();
    this.counter += 1;
    const id = `t${this.counter}`;
    const frame = { v: PROTOCOL_VERSION, id, ...payload };
    return new Promise<BrokerResponse>((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      socket.write(JSON.stringify(frame) + "\n", (error?: Error | null) => {
        if (error) {
          this.pending.delete(id);
          reject(error);
        }
      });
    });
  }
}

let channel: BrokerChannel | null = null;

function getChannel(): BrokerChannel {
  if (channel === null) channel = new BrokerChannel(AIDO_AR2_CONFIG.pipeName);
  return channel;
}

/**
 * Send one operation and return its result, or throw.
 *
 * The capability id and token come from the generated, disposable configuration
 * AIDO wrote next to this file. They are never logged, never printed, never put
 * in a tool result, and never shown to the model.
 */
export async function brokerCall(
  tool: string,
  operation: string,
  fields: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  let response: BrokerResponse;
  try {
    response = await getChannel().request({
      cap: AIDO_AR2_CONFIG.capabilityId,
      tok: AIDO_AR2_CONFIG.token,
      op: operation,
      ...fields,
    });
  } catch {
    throw new AidoBrokerUnavailableError(tool);
  }
  if (!response.ok) {
    throw new AidoBrokerRefusedError(tool, response.error?.code ?? "refused");
  }
  return response.result ?? {};
}
