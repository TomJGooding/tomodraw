import enum

from rich.segment import Segment
from textual import events, on
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.strip import Strip
from textual.widget import Widget
from textual.widgets import Label, ListView
from textual.widgets._list_item import ListItem


class Tool(enum.Enum):
    PENCIL = 1
    ERASER = 2


class Canvas(Widget):
    DEFAULT_CSS = """
    Canvas {
        width: 80;
        height: 24;
        hatch: "🭿" $panel-lighten-1;
    }
    """

    grid: list[list[str]] = [[" "] * 80 for _ in range(24)]

    tool: Tool = Tool.PENCIL
    draw: bool = False

    def render_line(self, y: int) -> Strip:
        return Strip([Segment(self.grid[y][x]) for x in range(80)])

    def draw_cell(self, x: int, y: int, char: str) -> None:
        self.grid[y][x] = char
        self.refresh()

    def erase_cell(self, x: int, y: int) -> None:
        self.draw_cell(x, y, " ")

    def on_mouse_down(self, event: events.MouseDown) -> None:
        self.draw = True
        if self.tool == Tool.PENCIL:
            self.draw_cell(event.x, event.y, "x")
        elif self.tool == Tool.ERASER:
            self.erase_cell(event.x, event.y)

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if not self.draw:
            return
        if self.tool == Tool.PENCIL:
            self.draw_cell(event.x, event.y, "x")
        elif self.tool == Tool.ERASER:
            self.erase_cell(event.x, event.y)

    def on_mouse_up(self, _: events.MouseDown) -> None:
        self.draw = False

    def on_leave(self, _: events.Leave) -> None:
        self.draw = False


class ToolboxItem(ListItem):
    def __init__(
        self,
        *children: Widget,
        tool: Tool,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False
    ) -> None:
        super().__init__(
            *children, name=name, id=id, classes=classes, disabled=disabled
        )
        self.tool = tool


class Toolbox(ListView):
    DEFAULT_CSS = """
    Toolbox {
        height: 24;
        width: 19;
        background: $panel-lighten-1;

        Label {
            text-style: bold;
            padding: 1;
        }
    }
    """

    def __init__(self) -> None:
        super().__init__(
            ToolboxItem(Label("Pencil"), tool=Tool.PENCIL),
            ToolboxItem(Label("Eraser"), tool=Tool.ERASER),
        )


class TomodrawApp(App):
    CSS = """
    Screen {
        align: center middle;
    }

    Horizontal {
        width: auto;
        height: auto;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Toolbox()
            yield Canvas()

    @on(Toolbox.Selected)
    def on_toolbox_tool_selected(self, event: Toolbox.Selected) -> None:
        assert isinstance(event.item, ToolboxItem)
        canvas = self.query_one(Canvas)
        canvas.tool = event.item.tool


def run() -> None:
    app = TomodrawApp()
    app.run()
