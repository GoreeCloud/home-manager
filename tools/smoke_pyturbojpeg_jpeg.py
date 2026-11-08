#!/usr/bin/env python3
"""Disposable Linux-only synthetic JPEG API smoke; never open user media.

This script is intentionally inert unless explicitly enabled by a first-party
GitHub Actions job. It checks only the imported camera/stream JPEG API contract,
not the complete Home Assistant runtime or real device/camera integration.
"""

from __future__ import annotations

import os
import platform
import sys


def main() -> int:
    if os.environ.get("GOREECLOUD_SYNTHETIC_CODEC_CI") != "1":
        print("JPEG SMOKE BLOCKED: synthetic disposable CI opt-in required", file=sys.stderr)
        return 2
    if sys.version_info[:3] != (3, 14, 10) or platform.system() != "Linux":
        print("JPEG SMOKE BLOCKED: requires pinned Linux Python 3.14.10", file=sys.stderr)
        return 2

    from importlib import metadata
    import numpy as np
    from turbojpeg import TurboJPEG

    assert metadata.version("PyTurboJPEG") == "1.8.3"
    assert metadata.version("numpy") == "2.3.2"

    # Deterministic, bounded synthetic image. No filesystem or network reads.
    pixels = np.empty((48, 64, 3), dtype=np.uint8)
    pixels[:, :, 0] = np.arange(64, dtype=np.uint8)
    pixels[:, :, 1] = np.arange(48, dtype=np.uint8)[:, np.newaxis]
    pixels[:, :, 2] = 127

    codec = TurboJPEG()
    jpeg = codec.encode(pixels, quality=82)
    assert isinstance(jpeg, bytes) and 20 < len(jpeg) < 100_000
    result = codec.decode_header(jpeg)
    assert isinstance(result, tuple) and len(result) == 4
    assert result[:2] == (64, 48), "upstream camera decode_header contract changed"

    scaled = codec.scale_with_quality(jpeg, scaling_factor=(1, 2), quality=75)
    assert isinstance(scaled, bytes) and 20 < len(scaled) < 100_000
    scaled_header = codec.decode_header(scaled)
    assert scaled_header[:2] == (32, 24)
    decoded = codec.decode(scaled)
    assert decoded.shape == (24, 32, 3) and decoded.dtype == np.uint8
    print("JPEG RUNTIME PASS: Python 3.14.10, upstream 1.8.3, numpy 2.3.2, native libturbojpeg 2.x")
    print("Scope: one synthetic encode/header/scale/decode; no camera, network, Home Assistant or deployment")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
