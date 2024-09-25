from __future__ import annotations

import enum

from rich.segment import Segment
from textual import events, on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.coordinate import Coordinate
from textual.geometry import Offset
from textual.screen import ModalScreen
from textual.strip import Strip
from textual.widget import Widget
from textual.widgets import Button, DataTable, Label, ListView
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

    def render_line(self, y: int) -> Strip:
        return Strip([Segment(self.grid[y][x]) for x in range(80)])

    def draw_cell(self, x: int, y: int, char: str) -> None:
        self.grid[y][x] = char
        self.refresh()

    def erase_cell(self, x: int, y: int) -> None:
        self.draw_cell(x, y, " ")

    def on_mouse_down(self, event: events.MouseDown) -> None:
        self.app.draw = True
        if self.app.tool == Tool.PENCIL:
            self.draw_cell(event.x, event.y, self.app.pencil_brush_char)
        elif self.app.tool == Tool.ERASER:
            self.erase_cell(event.x, event.y)

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if not self.app.draw:
            return
        if self.app.tool == Tool.PENCIL:
            self.draw_cell(event.x, event.y, self.app.pencil_brush_char)
        elif self.app.tool == Tool.ERASER:
            self.erase_cell(event.x, event.y)

    def on_mouse_up(self, _: events.MouseDown) -> None:
        self.app.draw = False

    def on_leave(self, _: events.Leave) -> None:
        self.app.draw = False

    @property
    def app(self) -> TomodrawApp:
        assert isinstance(self.app, TomodrawApp)
        return self.app


class ToolboxItem(ListItem):
    DEFAULT_CSS = """
    ToolboxItem {
        layout: horizontal;

        Label {
            width: 1fr;
            text-style: bold;
            padding: 1;
        }
    }
    """

    def __init__(self, *children: Widget, tool: Tool) -> None:
        super().__init__(*children)
        self.tool = tool


class PencilTool(ToolboxItem):
    DEFAULT_CSS = """
    PencilTool {
        Button {
            min-width: 5;
            background: transparent;
            border: solid $panel-lighten-3;
            margin-right: 1;
            &:focus {
                text-style: bold;
            }
            &:hover {
                background: $boost;
                border: solid $panel-lighten-3;
            }
            &.-active {
                background: transparent;
                border: solid $panel-lighten-3;
            }
        }

        &.--highlight {
            &:focus-within {
                background: $accent;
            }

            Button {
                border: solid $accent-lighten-3;
                &:hover {
                    border: solid $accent-lighten-3;
                }
                &.-active {
                    border: solid $accent-lighten-3;
                }
            }
        }
    }
    """

    brush_char = "x"

    def __init__(self) -> None:
        super().__init__(
            Label("Pencil"),
            Button(self.brush_char),
            tool=Tool.PENCIL,
        )

    @on(Button.Pressed)
    def on_button_pressed(self) -> None:
        def update_brush_char(char) -> None:
            self.brush_char = char
            self.query_one(Button).label = char

        self.app.push_screen(
            PencilSelectScreen(
                self.brush_char,
                offset_content=self.region.offset + Offset(self.size.width, 0),
            ),
            callback=update_brush_char,
        )


class PencilSelectScreen(ModalScreen):
    DEFAULT_CSS = """
    PencilSelectScreen {
        background: transparent;

        Container {
            width: auto;
            height: auto;
            background: $panel-lighten-1;
        }

        DataTable {
            width: auto;
            height: auto;
        }
    }
    """

    BRUSH_CHAR_GRID = [
        ["┌", "┐", "└", "┘", "◀", "▶", "▲", "▼", "│", "─"],
        ["┬", "┴", "┤", "├", "┼", "+", ">", "<", "^", "v"],
        [".", ",", ":", ";", "!", "?", '"', "'", "-", "_"],
        ["`", "=", "*", "&", "/", "\\", "|", "~", "@", "#"],
        ["$", "%", "(", ")", "[", "]", "{", "}", "a", "b"],
        ["c", "d", "e", "f", "g", "h", "i", "j", "k", "l"],
        ["m", "n", "o", "p", "q", "r", "s", "t", "u", "v"],
        ["w", "x", "y", "z", "A", "B", "C", "D", "E", "F"],
        ["G", "H", "I", "J", "K", "L", "M", "N", "O", "P"],
        ["Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"],
        ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"],
    ]

    def __init__(self, curr_brush_char: str, offset_content: Offset) -> None:
        super().__init__()
        self.selected_brush_char = curr_brush_char
        self.offset_content = offset_content

    def compose(self) -> ComposeResult:
        container = Container()
        container.offset = self.offset_content
        with container:
            yield DataTable(show_header=False)

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns(*[""] * len(self.BRUSH_CHAR_GRID[0]))
        table.add_rows(self.BRUSH_CHAR_GRID)
        table.cursor_coordinate = self.get_initial_coordinate()

    def get_initial_coordinate(self) -> Coordinate:
        for row_idx, row in enumerate(self.BRUSH_CHAR_GRID):
            if self.selected_brush_char in row:
                return Coordinate(row_idx, row.index(self.selected_brush_char))
        raise ValueError("Invalid brush character")

    @on(DataTable.CellSelected)
    def on_data_table_cell_selected(
        self,
        event: DataTable.CellSelected,
    ) -> None:
        self.selected_brush_char = str(event.value)
        self.call_after_refresh(self.safe_dismiss)

    def on_click(self, event: events.Click) -> None:
        clicked, _ = self.get_widget_at(event.screen_x, event.screen_y)
        if clicked is self:
            self.safe_dismiss()

    def safe_dismiss(self) -> None:
        self.dismiss(self.selected_brush_char)


class EraserTool(ToolboxItem):
    def __init__(self) -> None:
        super().__init__(Label("Eraser"), tool=Tool.ERASER)


class Toolbox(ListView):
    DEFAULT_CSS = """
    Toolbox {
        height: 24;
        width: 19;
        background: $panel-lighten-1;
    }
    """

    def __init__(self) -> None:
        super().__init__(
            PencilTool(),
            EraserTool(),
        )


class TomodrawApp(App):
    CSS = """
    Screen {
        align: center middle;
    }

    PencilSelectScreen {
        align: left top;
    }

    Horizontal {
        width: auto;
        height: auto;
    }
    """

    tool: Tool = Tool.PENCIL
    draw: bool = False

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Toolbox()
            yield Canvas()

    @on(Toolbox.Selected)
    def on_toolbox_tool_selected(self, event: Toolbox.Selected) -> None:
        assert isinstance(event.item, ToolboxItem)
        self.tool = event.item.tool

    @property
    def pencil_brush_char(self) -> str:
        return self.query_one(PencilTool).brush_char


def run() -> None:
    app = TomodrawApp()
    app.run()
