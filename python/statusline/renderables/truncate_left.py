"""A renderable that truncates content from the left to fit available width."""

from __future__ import annotations

from rich.console import Console, ConsoleOptions, RenderResult
from rich.measure import Measurement
from rich.segment import Segment


class TruncateLeft:
    """Truncates content from the left, keeping the rightmost (most recent) content.

    When content exceeds available width:
    - Keeps segments from the right (most recent)
    - Crops the leftmost visible segment if needed for partial fit
    - Optionally left-pads when expanding to fill available width
    """

    def __init__(self, renderable, *, expand: bool = False):
        """Initialize TruncateLeft.

        Args:
            renderable: Any Rich renderable to wrap.
            expand: If True, left-pad with spaces to fill available width.
        """
        self.renderable = renderable
        self.expand = expand

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        """Render content, truncating from the left to fit width."""
        # Render inner content at unlimited width to get all segments
        # Reset justify to avoid padding from inherited "left" justify
        unlimited_options = options.update(width=10000, justify="default")
        lines = console.render_lines(self.renderable, options=unlimited_options, pad=False)
        segments = list(lines[0]) if lines else []

        width = options.max_width

        # Walk from right, accumulate widths, keep what fits
        result: list[Segment] = []
        used = 0

        for seg in reversed(segments):
            seg_len = seg.cell_length
            if used + seg_len > width:
                # Partial fit - crop from left
                remaining = width - used
                if remaining > 0:
                    # Take rightmost `remaining` characters
                    cropped_text = seg.text[-remaining:]
                    result.append(Segment(cropped_text, seg.style))
                    used += remaining
                break
            result.append(seg)
            used += seg_len

        result.reverse()

        # Left-pad if expanding
        if self.expand and used < width:
            yield Segment(" " * (width - used))

        yield from result

    def __rich_measure__(
        self, console: Console, options: ConsoleOptions
    ) -> Measurement:
        """Measure the renderable."""
        if self.expand:
            return Measurement(0, options.max_width)

        # Measure inner content at unlimited width
        # Reset justify to avoid padding from inherited "left" justify
        unlimited_options = options.update(width=10000, justify="default")
        lines = console.render_lines(self.renderable, options=unlimited_options, pad=False)
        segments = lines[0] if lines else []
        total = sum(seg.cell_length for seg in segments)
        return Measurement(total, total)
