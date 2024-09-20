from rich.segment import Segment
from textual import events
from textual.app import App, ComposeResult
from textual.strip import Strip
from textual.widget import Widget


class Canvas(Widget):
    DEFAULT_CSS = """
    Canvas {
        width: 80;
        height: 24;
        hatch: "🭿" $panel-lighten-1;
    }
    """

    grid: list[list[str]] = [[" "] * 80 for _ in range(24)]
    draw: bool = False

    def render_line(self, y: int) -> Strip:
        return Strip([Segment(self.grid[y][x]) for x in range(80)])

    def draw_cell(self, x: int, y: int, char: str) -> None:
        self.grid[y][x] = char
        self.refresh()

    def on_mouse_down(self, event: events.MouseDown) -> None:
        self.draw = True
        self.draw_cell(event.x, event.y, "x")

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self.draw:
            self.draw_cell(event.x, event.y, "x")

    def on_mouse_up(self, _: events.MouseDown) -> None:
        self.draw = False

    def on_leave(self, _: events.Leave) -> None:
        self.draw = False


class TomodrawApp(App):
    CSS = """
    Screen {
        align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        yield Canvas()


def run() -> None:
    app = TomodrawApp()
    app.run()
