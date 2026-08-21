/*
 * Phase 5F3A-AR1 - AIDO-authored filesystem confinement for Pi tools.
 *
 * WHAT THIS IS (read before changing anything):
 *
 *   This module implements FU1 "Option B-fixed": the confinement predicate is
 *   an EXACT ALLOWLIST of concrete absolute paths that AIDO computed, with its
 *   own accepted canonical-path machinery, BEFORE Pi was launched.
 *
 *   It deliberately implements NO general Windows path policy. There is no
 *   traversal parser, no UNC classifier, no ADS detector, no device-name table,
 *   no short-name expander, no Unicode normalizer. Every one of those hazards
 *   fails the exact-membership test automatically, because none of them IS one
 *   of the few allowed strings.
 *
 * WHAT THIS IS NOT:
 *
 *   This is capability restriction at the tool layer, enforced inside Pi's own
 *   Node process, with the launching user's full permissions. It is NOT an OS
 *   sandbox. It does not prove that no host file outside the fixture was read
 *   or written; a Pi defect, a dependency defect, or a future Pi version could
 *   bypass this seam entirely.
 *
 * FAIL-CLOSED RULES:
 *   - a non-allowlisted target is REFUSED. No repair, no fallback, no "closest"
 *     path, no partial operation.
 *   - the underlying filesystem implementation is reached ONLY after the guard
 *     has accepted, and it is always handed AIDO's own allowlisted string --
 *     never the model-supplied string.
 *   - any canonicalization error is a refusal.
 */

import { realpathSync } from "node:fs";
import { isAbsolute, resolve as resolvePath } from "node:path";

/** The generated, AIDO-authored confinement configuration. */
export interface AidoAr1Config {
  /** Experiment identity, carried for audit only. */
  readonly experiment: string;
  /** The canonical disposable repository root AIDO proved before launch. */
  readonly cwd: string;
  /** Absolute canonical paths aido_read may access. Exact membership. */
  readonly readAllowlist: readonly string[];
  /** Absolute canonical paths aido_edit may access. Exact membership. */
  readonly editAllowlist: readonly string[];
}

/** The raw filesystem seam. Injected so a test can prove it is not reached. */
export interface RawFileSystem {
  readFile(absolutePath: string): Promise<Buffer>;
  writeFile(absolutePath: string, content: string): Promise<void>;
  accessRead(absolutePath: string): Promise<void>;
  accessReadWrite(absolutePath: string): Promise<void>;
}

/** One refusal, recorded for evidence. The refused path is NOT retained. */
export interface RefusalRecord {
  readonly tool: string;
  readonly operation: string;
  readonly reason: string;
}

export interface ConfinementAudit {
  readonly refusals: RefusalRecord[];
  readonly allowedOperations: { tool: string; operation: string }[];
}

export function createAudit(): ConfinementAudit {
  return { refusals: [], allowedOperations: [] };
}

/**
 * Refusal error. The message deliberately carries NO path, so a refused
 * model-supplied absolute host path is never echoed back into the event stream.
 */
export class AidoPathRefusedError extends Error {
  constructor(tool: string, operation: string) {
    super(
      `${tool} refused: the requested path is not in this experiment's ` +
        `AIDO-authored allowlist. No filesystem operation was performed.`,
    );
    this.name = "AidoPathRefusedError";
    void operation;
  }
}

/**
 * The comparison key.
 *
 * Windows-only experiment: NTFS path comparison is case-insensitive, so a key
 * folds case. That widens *matching* between two spellings of the same file; it
 * never widens *scope*, because the map only ever contains the allowlisted
 * members themselves.
 */
export function comparisonKey(absolutePath: string): string {
  return resolvePath(absolutePath).toLowerCase();
}

export interface AllowlistGuard {
  /**
   * Return the AIDO-owned allowlisted path for `candidate`, or throw.
   * The returned string -- never the caller's -- is what reaches the filesystem.
   */
  (candidate: unknown, operation: string): Promise<string>;
}

export function makeAllowlistGuard(
  tool: string,
  allowlist: readonly string[],
  audit: ConfinementAudit,
): AllowlistGuard {
  const members = new Map<string, string>();
  for (const member of allowlist) {
    if (typeof member !== "string" || member.length === 0 || !isAbsolute(member)) {
      throw new Error(
        `aido confinement config error: allowlist entry for ${tool} is not an absolute path`,
      );
    }
    members.set(comparisonKey(member), member);
  }

  const refuse = (operation: string, reason: string): never => {
    audit.refusals.push({ tool, operation, reason });
    throw new AidoPathRefusedError(tool, operation);
  };

  return async (candidate: unknown, operation: string): Promise<string> => {
    if (typeof candidate !== "string" || candidate.length === 0) {
      return refuse(operation, "not_a_non_empty_string");
    }
    if (candidate.indexOf("\u0000") !== -1) {
      return refuse(operation, "embedded_nul");
    }

    let key: string;
    try {
      key = comparisonKey(candidate);
    } catch {
      return refuse(operation, "unresolvable_candidate");
    }

    const member = members.get(key);
    if (member === undefined) {
      return refuse(operation, "not_in_allowlist");
    }

    // Second, independent check: the real path on disk must still be the same
    // allowlisted member. This catches a symlink/junction/short-name alias that
    // happened to spell an allowed name, and it fails closed when the path
    // cannot be resolved at all.
    let real: string;
    try {
      real = realpathSync.native(member);
    } catch {
      return refuse(operation, "realpath_failed");
    }
    if (comparisonKey(real) !== key) {
      return refuse(operation, "realpath_mismatch");
    }

    audit.allowedOperations.push({ tool, operation });
    return member;
  };
}

/** Guarded ReadOperations. Every callback enforces the allowlist first. */
export function createGuardedReadOperations(
  allowlist: readonly string[],
  fs: RawFileSystem,
  audit: ConfinementAudit,
) {
  const guard = makeAllowlistGuard("aido_read", allowlist, audit);
  return {
    access: async (absolutePath: string): Promise<void> => {
      const allowed = await guard(absolutePath, "access");
      await fs.accessRead(allowed);
    },
    readFile: async (absolutePath: string): Promise<Buffer> => {
      const allowed = await guard(absolutePath, "readFile");
      return fs.readFile(allowed);
    },
    // Guarded, and then deliberately inert: this experiment's fixture is text
    // only, so image MIME detection never needs to touch the filesystem. It is
    // supplied rather than omitted so that no unguarded default can be used.
    detectImageMimeType: async (absolutePath: string): Promise<string | null> => {
      await guard(absolutePath, "detectImageMimeType");
      return null;
    },
  };
}

/** Guarded EditOperations. Every callback enforces the allowlist first. */
export function createGuardedEditOperations(
  allowlist: readonly string[],
  fs: RawFileSystem,
  audit: ConfinementAudit,
) {
  const guard = makeAllowlistGuard("aido_edit", allowlist, audit);
  return {
    access: async (absolutePath: string): Promise<void> => {
      const allowed = await guard(absolutePath, "access");
      await fs.accessReadWrite(allowed);
    },
    readFile: async (absolutePath: string): Promise<Buffer> => {
      const allowed = await guard(absolutePath, "readFile");
      return fs.readFile(allowed);
    },
    writeFile: async (absolutePath: string, content: string): Promise<void> => {
      const allowed = await guard(absolutePath, "writeFile");
      await fs.writeFile(allowed, content);
    },
  };
}
