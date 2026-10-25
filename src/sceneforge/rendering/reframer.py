"""Portrait reframing strategies.

Two strategies are implemented, in priority order:

1. Center crop  — crops the source to the target aspect ratio centred
   horizontally and vertically. Safe for most landscape-to-portrait
   conversions when no subject position is known.

2. Blurred-pad  — scales the source to fit the target width, then pads
   top and bottom with a blurred, darkened version of the source frame.
   Preserves the entire original frame; no content is cropped.

IMPORTANT: Neither strategy performs intelligent subject tracking or
face detection. Any claim of "subject-aware" reframing beyond these
deterministic geometric operations would require a face-detection model
that is not currently integrated. The strategy used is always recorded
in the timeline entry for transparency.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

ReframeStrategy = Literal["center_crop", "blurred_pad"]

_DEFAULT_STRATEGY = os.getenv("REFRAME_STRATEGY", "blurred_pad")


@dataclass
class ReframeParams:
    """Parameters for a single reframe operation."""

    strategy: ReframeStrategy
    source_width: int
    source_height: int
    target_width: int
    target_height: int
    # Center-crop offset (pixels from top-left of source)
    crop_x: int = 0
    crop_y: int = 0
    # Blurred-pad scale dimensions
    scale_w: int = 0
    scale_h: int = 0
    pad_y: int = 0

    def as_ffmpeg_vf(self) -> str:
        """Return the FFmpeg -vf filter string for this reframe."""
        if self.strategy == "center_crop":
            return (
                f"crop={self.target_width}:{self.target_height}"
                f":{self.crop_x}:{self.crop_y}"
            )
        else:
            # Blurred pad:
            # 1. Scale source to target width (letterboxed height)
            # 2. Create blurred background scaled to fill target entirely
            # 3. Overlay sharp foreground on blurred background
            return (
                f"split=2[fg][bg];"
                f"[bg]scale={self.target_width}:{self.target_height}:force_original_aspect_ratio=increase,"
                f"crop={self.target_width}:{self.target_height},"
                f"gblur=sigma=20,"
                f"colorchannelmixer=aa=0.7[blurred];"
                f"[fg]scale={self.scale_w}:{self.scale_h}[sharp];"
                f"[blurred][sharp]overlay=(W-w)/2:(H-h)/2"
            )


def compute_reframe(
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
    *,
    strategy: ReframeStrategy = _DEFAULT_STRATEGY,
) -> ReframeParams:
    """Compute reframe parameters without running FFmpeg.

    Args:
        source_width/height:  Dimensions of the source clip.
        target_width/height:  Desired output dimensions.
        strategy:             "center_crop" or "blurred_pad".

    Returns:
        ReframeParams with all computed values.
    """
    params = ReframeParams(
        strategy=strategy,
        source_width=source_width,
        source_height=source_height,
        target_width=target_width,
        target_height=target_height,
    )

    if strategy == "center_crop":
        # Crop from center: scale source so the shorter target dimension fits,
        # then crop the longer dimension.
        scale_w = target_width
        scale_h = int(source_height * target_width / source_width)

        if scale_h < target_height:
            # Height is the constraining dimension
            scale_h = target_height
            scale_w = int(source_width * target_height / source_height)

        # Centre offset
        params.crop_x = max(0, (scale_w - target_width) // 2)
        params.crop_y = max(0, (scale_h - target_height) // 2)

    else:  # blurred_pad
        # Scale source to fit target_width, maintain aspect ratio
        scale_h = int(source_height * target_width / source_width)
        scale_h = scale_h if scale_h % 2 == 0 else scale_h + 1
        params.scale_w = target_width
        params.scale_h = scale_h
        params.pad_y = max(0, (target_height - scale_h) // 2)

    return params


def needs_reframe(
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
) -> bool:
    """Return True when the source aspect ratio differs from the target."""
    if source_height == 0 or target_height == 0:
        return False
    src_ratio = source_width / source_height
    tgt_ratio = target_width / target_height
    return abs(src_ratio - tgt_ratio) > 0.01
