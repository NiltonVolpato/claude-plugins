"""Unit tests for TruncateLeft renderable."""

from rich.console import Console
from rich.segment import Segment
from rich.styled import Styled
from rich.table import Table
from rich.text import Text

from statusline.renderables import TruncateLeft


def render_plain(renderable, width: int = 40) -> str:
    """Render a Rich renderable to plain text."""
    console = Console(width=width, force_terminal=False, no_color=True)
    with console.capture() as capture:
        console.print(renderable, end="")
    return capture.get()


def render_segments(renderable, width: int = 40) -> list[Segment]:
    """Render and return the list of Segments."""
    console = Console(width=width, force_terminal=True)
    lines = console.render_lines(renderable, pad=False)
    return [seg for line in lines for seg in line]


class TestTruncateLeftBasic:
    """Basic truncation tests."""

    def test_fits_completely(self):
        """Content that fits is unchanged."""
        text = Text("ABC")
        result = render_plain(TruncateLeft(text), width=10)
        assert result == "ABC"

    def test_exact_fit(self):
        """Content that exactly fits is unchanged."""
        text = Text("ABCDE")
        result = render_plain(TruncateLeft(text), width=5)
        assert result == "ABCDE"

    def test_truncates_from_left(self):
        """Content that overflows is truncated from the left."""
        text = Text("ABCDE")
        result = render_plain(TruncateLeft(text), width=3)
        assert result == "CDE"

    def test_single_char_width(self):
        """Single character width keeps last character."""
        text = Text("ABCDE")
        result = render_plain(TruncateLeft(text), width=1)
        assert result == "E"

    def test_empty_content(self):
        """Empty content renders empty."""
        text = Text("")
        result = render_plain(TruncateLeft(text), width=10)
        assert result == ""


class TestTruncateLeftExpand:
    """Tests for expand mode (left-padding)."""

    def test_expand_pads_left(self):
        """Expand mode left-pads content."""
        text = Text("X")
        result = render_plain(TruncateLeft(text, expand=True), width=5)
        assert result == "    X"

    def test_expand_exact_fit(self):
        """Expand with exact fit has no padding."""
        text = Text("ABC")
        result = render_plain(TruncateLeft(text, expand=True), width=3)
        assert result == "ABC"

    def test_expand_overflow_truncates(self):
        """Expand mode still truncates if content overflows."""
        text = Text("ABCDE")
        result = render_plain(TruncateLeft(text, expand=True), width=3)
        assert result == "CDE"


class TestTruncateLeftWithStyles:
    """Tests for style preservation during truncation."""

    def test_preserves_style_on_full_segment(self):
        """Full segments keep their styles."""
        text = Text()
        text.append("AAA", style="red")
        text.append("BBB", style="blue")

        segments = render_segments(TruncateLeft(text), width=6)
        # Filter out any empty/control segments
        segments = [s for s in segments if s.text.strip()]

        assert len(segments) == 2
        assert segments[0].text == "AAA"
        assert segments[0].style.color.name == "red"
        assert segments[1].text == "BBB"
        assert segments[1].style.color.name == "blue"

    def test_preserves_style_on_cropped_segment(self):
        """Cropped segments keep their styles."""
        text = Text()
        text.append("AAA", style="red")
        text.append("BBB", style="blue")

        # Width 4: full BBB (3) + 1 char from AAA
        segments = render_segments(TruncateLeft(text), width=4)
        segments = [s for s in segments if s.text.strip()]

        assert len(segments) == 2
        assert segments[0].text == "A"  # Cropped
        assert segments[0].style.color.name == "red"
        assert segments[1].text == "BBB"
        assert segments[1].style.color.name == "blue"

    def test_styled_wrapper(self):
        """Works with Styled wrapper."""
        inner = Text("Hello")
        styled = Styled(inner, style="bold")
        result = render_plain(TruncateLeft(styled), width=3)
        assert result == "llo"


class TestTruncateLeftWithGrid:
    """Tests with Table.grid as inner content."""

    def test_grid_fits(self):
        """Grid content that fits is unchanged."""
        grid = Table.grid()
        grid.add_row(Text("A"), Text("B"), Text("C"))
        result = render_plain(TruncateLeft(grid), width=10)
        assert result == "ABC"

    def test_grid_with_padding(self):
        """Grid with padding between columns."""
        grid = Table.grid(padding=(0, 1, 0, 0))
        grid.add_column()
        grid.add_column()
        grid.add_column()
        grid.add_row(Text("A"), Text("B"), Text("C"))
        result = render_plain(TruncateLeft(grid), width=10)
        assert result == "A B C"

    def test_grid_truncated(self):
        """Grid content truncated from left."""
        grid = Table.grid()
        grid.add_row(Text("AAA"), Text("BBB"), Text("CCC"))
        # 9 chars total, width 5 = keep "BCCC" with partial B
        result = render_plain(TruncateLeft(grid), width=5)
        assert result == "BBCCC"

    def test_nested_grids(self):
        """Nested grids work correctly."""
        inner1 = Table.grid()
        inner1.add_row(Text("A"), Text("B"))

        inner2 = Table.grid()
        inner2.add_row(Text("C"), Text("D"))

        outer = Table.grid()
        outer.add_row(inner1, inner2)

        result = render_plain(TruncateLeft(outer), width=10)
        assert result == "ABCD"

    def test_nested_grids_truncated(self):
        """Nested grids truncate correctly."""
        inner1 = Table.grid()
        inner1.add_row(Text("AAA"))

        inner2 = Table.grid()
        inner2.add_row(Text("BBB"))

        outer = Table.grid()
        outer.add_row(inner1, inner2)

        # 6 chars total, width 4 = "ABBB"
        result = render_plain(TruncateLeft(outer), width=4)
        assert result == "ABBB"


class TestTruncateLeftInGrid:
    """Tests for TruncateLeft behavior when nested inside Table.grid."""

    def test_no_justify_padding_in_grid(self):
        """TruncateLeft should not inherit justify=left padding from parent grid."""
        # This was a bug: Table.grid sets justify="left" on columns, which
        # propagates to render_lines and causes Text to pad to fill width.
        # The fix: use options.update(width=..., justify="default")
        from rich.table import Table

        grid = Table.grid()
        grid.add_column()
        grid.add_column()
        grid.add_column()
        grid.add_row(Text("["), TruncateLeft(Text("ABC")), Text("]"))

        result = render_plain(grid, width=10).rstrip("\n")
        assert result == "[ABC]"


class TestTruncateLeftMeasure:
    """Tests for __rich_measure__."""

    def test_measure_no_expand(self):
        """Without expand, measure returns content size."""
        text = Text("ABC")
        truncate = TruncateLeft(text, expand=False)

        console = Console(width=80)
        options = console.options
        measurement = truncate.__rich_measure__(console, options)

        assert measurement.minimum == 3
        assert measurement.maximum == 3

    def test_measure_with_expand(self):
        """With expand, measure returns 0 to max_width."""
        text = Text("ABC")
        truncate = TruncateLeft(text, expand=True)

        console = Console(width=80)
        options = console.options
        measurement = truncate.__rich_measure__(console, options)

        assert measurement.minimum == 0
        assert measurement.maximum == 80
