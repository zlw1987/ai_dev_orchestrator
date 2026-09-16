"""L1's offline preflight: pinned Pi seam digests and the compat-detection gate.

Design Sec. 14.2 (the pinned digests) and Sec. 16.2 L1/L6.

**A digest mismatch refuses BEFORE any credential read.** It means the
derivation this whole experiment rests on must be re-reviewed -- never that Pi
is incompatible, and never that the run should proceed with a warning.

**The base-URL compat classification is a pure in-memory test.** It answers one
question -- does the configured base URL contain any substring Pi's own
``detectCompat`` branches on? -- and yields one bool. The URL itself is never
recorded, returned, digested, or logged, and this function never performs DNS,
opens a socket, or contacts anything.
"""

from __future__ import annotations

import hashlib
import os

#: SHA-256 of the installed Pi 0.85.1 files this design's source derivations
#: depend on. Eighteen were pinned at design time (Sec. 14.2); the last two --
#: ``dist/modes/rpc/jsonl.js`` and ``pi-agent-core/dist/agent-loop.js`` -- were
#: the design's own explicitly deferred implementation-time pins, computed
#: against the installed package during CFG1-IMPL and added here.
#:
#: Paths are relative to the installed ``@earendil-works/pi-coding-agent`` root
#: and use forward slashes on every platform.
PINNED_PI_SEAM_DIGESTS: dict[str, str] = {
    "package.json": "f1738e4b42203e5f22bcb513f13fb2fb224f1e98d1f129ff042f87048665a94c",
    "dist/cli.js": "8189b66abc4f9f431dbb70941dcba690d76d040de1fbfff212886be35a53639d",
    "dist/main.js": "f0b7e5a8419af8d149ffe367af2992c76ce70b73484c15492bd50787d4f4962a",
    "dist/core/sdk.js": "6969bd56ba8e1628cd033bb15cb15fe38299f00b5ad84f4f8ef37a33a98681c9",
    "dist/core/defaults.js": "13196dce2ddb143f6f4c28af2e34374f84004e50c7b71ba7b900e1acf84479b6",
    "dist/core/model-config.js": "ac983b5825f96eb2bfdeb9776cedeb540724e14f1c9fe41ded9f5411038dd522",
    "dist/core/provider-composer.js": "8eca507009d00768130e46cd9a0831e4fa2f98b81435ae0a8d5079a1d27e13cd",
    "dist/core/model-runtime.js": "32cd50599d9e6e001229090e3d0554b60e4addb8ab7b3165635a574feb660b74",
    "dist/core/model-resolver.js": "00f57b9c60f990f059c48b14269e571fabdfefaab93b062ee77501d5fa9db0a7",
    "dist/core/system-prompt.js": "4a57f022a27f2ae22d7d0c0d8f0ef4a63f869b878483699d4102055239bdea0a",
    "dist/core/agent-session.js": "fb8a3981c20c8c0bbd42231b1c99a10335fb3858b659056b341954de9cfa467f",
    "dist/modes/rpc/rpc-mode.js": "e7e4724aa55c5aac73cf36793653b26736200e5c59d58373990fc31028f86477",
    # Pinned by CFG1-IMPL (FU1 relies on it for the `get_state` derivation).
    "dist/modes/rpc/jsonl.js": "049a9f8ca4242c79f1911ed977949e8d8906b4561f424c2729687f426fabaacf",
    "node_modules/@earendil-works/pi-ai/package.json": "b54df5a36d523febdeebfc5682dc4faed101fee10aba913d5f3679582f018da3",
    "node_modules/@earendil-works/pi-ai/dist/api/openai-completions.js": "1e2097ced37cf0e21aa5711297eecc77916de8a4ed81a9019bc7d97b22825fa3",
    "node_modules/@earendil-works/pi-ai/dist/api/simple-options.js": "1caf860e028e22639578aba3ec8b79e5be9650c27bd3f19471c78502976555f3",
    "node_modules/@earendil-works/pi-ai/dist/models.js": "42610d47fe293d99f4b05b147971e181c7312ea47c9be2906a4803955276a8a4",
    "node_modules/@earendil-works/pi-agent-core/package.json": "f4c388363706ae0eb8eca4e7663f85f231bf0882d7e32c16f7cfd98153b26551",
    "node_modules/@earendil-works/pi-agent-core/dist/agent.js": "d84351e451b9fef40fe2532c446aca90d26a4be9038b2d77d3d45dd6eab21d41",
    # Pinned by CFG1-IMPL (FU1 relies on it for the unregistered-tool-name
    # derivation that makes Sec. 12.1 row 6 sound).
    "node_modules/@earendil-works/pi-agent-core/dist/agent-loop.js": "6732a1c65c09577d2ffcb716b48e4f4673e57e3e333f10ebfce5132d82e4d7a2",
}

#: The exact substrings Pi's own ``detectCompat`` branches on, plus
#: ``api.openai.com`` (which gates ``prompt_cache_key``). A base URL containing
#: ANY of these would make this experiment's effective-compat derivation wrong,
#: so a run whose URL matches refuses pre-dispatch rather than proceeding with
#: an unverifiable premise.
COMPAT_DETECTION_SUBSTRINGS: tuple[str, ...] = (
    "api.z.ai",
    "open.bigmodel.cn",
    "api.together.ai",
    "api.together.xyz",
    "api.moonshot.",
    "openrouter.ai",
    "api.cloudflare.com",
    "gateway.ai.cloudflare.com",
    "integrate.api.nvidia.com",
    "api.ant-ling.com",
    "deepseek.com",
    "cerebras.ai",
    "api.x.ai",
    "chutes.ai",
    "opencode.ai",
    "api.openai.com",
)


class Cfg1PreflightError(Exception):
    """An offline preflight gate failed. Bounded reason code only."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"cfg1 preflight refused: {reason_code}")
        self.reason_code = reason_code


def base_url_compat_detection_clear(base_url: str) -> bool:
    """True iff the URL matches NO detection substring. The URL is never retained.

    Pure and in-memory: no DNS, no socket, no request. The caller records only
    this bool -- never the URL, its host, its port, or its scheme.
    """
    if type(base_url) is not str:
        return False
    lowered = base_url.lower()
    return not any(needle in lowered for needle in COMPAT_DETECTION_SUBSTRINGS)


def _digest_file(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def verify_pi_seam_digests(pi_package_root: str) -> tuple[bool, tuple[str, ...]]:
    """Digest every pinned seam file. Returns ``(all_match, mismatched_paths)``.

    The returned paths are the pinned RELATIVE keys -- bounded, package-internal
    literals from the table above -- never absolute filesystem paths, which
    Sec. 21.2 forbids in every sink.
    """
    mismatched: list[str] = []
    for relative, expected in sorted(PINNED_PI_SEAM_DIGESTS.items()):
        absolute = os.path.join(pi_package_root, *relative.split("/"))
        try:
            actual = _digest_file(absolute)
        except OSError:
            mismatched.append(relative)
            continue
        if actual != expected:
            mismatched.append(relative)
    return (not mismatched), tuple(mismatched)
