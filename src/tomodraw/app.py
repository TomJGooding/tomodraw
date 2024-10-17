import copy
import enum

import pyperclip
from rich.segment import Segment
from rich.text import TextType
from textual import events, on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.coordinate import Coordinate
from textual.geometry import Offset
from textual.screen import ModalScreen
from textual.strip import Strip
from textual.widget import Widget
from textual.widgets import Button, DataTable, Input, Label, ListItem, ListView


class Tool(enum.Enum):
    RECTANGLE = 1
    TEXT = 2
    LINE = 3
    PENCIL = 4
    ERASER = 5


class Canvas(Widget):
    DEFAULT_CSS = """
    Canvas {
        width: 80;
        height: 24;
        hatch: "🭿" $panel-lighten-1;
    }
    """

    grid: list[list[str]] = [[" "] * 80 for _ in range(24)]

    @property
    def grid_as_text(self) -> str:
        return "\n".join("".join(row) for row in self.grid)

    def render_line(self, y: int) -> Strip:
        return Strip([Segment(self.grid[y][x]) for x in range(80)])

    def draw_cell(self, x: int, y: int, char: str) -> None:
        self.grid[y][x] = char
        self.refresh()

    def erase_cell(self, x: int, y: int) -> None:
        self.draw_cell(x, y, " ")

    def draw_horizontal_line(
        self,
        grid: list[list[str]],
        y: int,
        start_x: int,
        end_x: int,
    ) -> None:
        assert start_x < end_x
        for x in range(start_x, end_x + 1):
            grid[y][x] = "─"

    def draw_vertical_line(
        self,
        grid: list[list[str]],
        x: int,
        start_y: int,
        end_y: int,
    ) -> None:
        assert start_y < end_y
        for y in range(start_y, end_y + 1):
            grid[y][x] = "│"

    def draw_rectangle(self, x0: int, y0: int, x1: int, y1: int) -> None:
        assert isinstance(self.app, TomodrawApp)
        # TODO: Optimize the rectangle drawing method. Repeatedly creating deep
        # copies of the canvas grid is obviously not very efficient!
        new_grid = copy.deepcopy(self.app.last_canvas_grid)

        start_x = min(x0, x1)
        end_x = max(x0, x1)
        start_y = min(y0, y1)
        end_y = max(y0, y1)

        if start_x != end_x:
            self.draw_horizontal_line(new_grid, start_y, start_x, end_x)
            self.draw_horizontal_line(new_grid, end_y, start_x, end_x)
        if start_y != end_y:
            self.draw_vertical_line(new_grid, start_x, start_y, end_y)
            self.draw_vertical_line(new_grid, end_x, start_y, end_y)
        if start_x != end_x and start_y != end_y:
            new_grid[start_y][start_x] = "┌"
            new_grid[end_y][start_x] = "└"
            new_grid[start_y][end_x] = "┐"
            new_grid[end_y][end_x] = "┘"

        self.grid = new_grid
        self.refresh()

    def draw_line(
        self,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        horizontal_first: bool,
    ) -> None:
        assert isinstance(self.app, TomodrawApp)
        # TODO: Optimize the line drawing method. Repeatedly creating deep
        # copies of the canvas grid is obviously not very efficient!
        new_grid = copy.deepcopy(self.app.last_canvas_grid)

        start_x = min(x0, x1)
        end_x = max(x0, x1)
        start_y = min(y0, y1)
        end_y = max(y0, y1)

        if start_x != end_x:
            y = y0 if horizontal_first else y1
            self.draw_horizontal_line(new_grid, y, start_x, end_x)
        if start_y != end_y:
            x = x1 if horizontal_first else x0
            self.draw_vertical_line(new_grid, x, start_y, end_y)
        if start_x != end_x and start_y != end_y:
            if horizontal_first:
                corner_char = (("└", "┌"), ("┘", "┐"))[x0 < x1][y0 < y1]
                new_grid[y0][x1] = corner_char
            else:
                corner_char = (("┐", "┘"), ("┌", "└"))[x0 < x1][y0 < y1]
                new_grid[y1][x0] = corner_char

        self.grid = new_grid
        self.refresh()

    def draw_text(self, text: str, start_x: int, start_y) -> None:
        for x, char in enumerate(text, start=start_x):
            self.grid[start_y][x] = char
        self.refresh()

    def on_mouse_down(self, event: events.MouseDown) -> None:
        assert isinstance(self.app, TomodrawApp)
        self.app.last_canvas_grid = self.grid
        self.app.tool_start_x = event.x
        self.app.tool_start_y = event.y
        self.app.draw = True
        if self.app.tool == Tool.PENCIL:
            self.draw_cell(event.x, event.y, self.app.pencil_brush_char)
        elif self.app.tool == Tool.ERASER:
            self.erase_cell(event.x, event.y)
        elif self.app.tool == Tool.TEXT:
            # TODO: Investigate using the TextArea rather than the Input widget
            # to allow drawing multi-line text.
            text_input = TextInputOverlay(
                max_length=80 - event.x,
                start_x=event.x,
                start_y=event.y,
            )
            text_input.absolute_offset = event.screen_offset
            self.app.mount(text_input)
            text_input.focus()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        assert isinstance(self.app, TomodrawApp)
        if not self.app.draw:
            return
        if self.app.tool == Tool.PENCIL:
            self.draw_cell(event.x, event.y, self.app.pencil_brush_char)
        elif self.app.tool == Tool.ERASER:
            self.erase_cell(event.x, event.y)
        elif self.app.tool == Tool.RECTANGLE:
            self.draw_rectangle(
                self.app.tool_start_x,
                self.app.tool_start_y,
                event.x,
                event.y,
            )
        elif self.app.tool == Tool.LINE:
            # It seems that some terminal emulators (e.g. urxvt) might handle
            # mouse and modifier key events differently than most others.
            # Instead of continuously checking the state of modifier keys
            # during mouse interactions, these emulators only seem to indicate
            # the modifiers pressed at the time the mouse button was clicked.
            # This means that in some terminal emulators, pressing or releasing
            # the Ctrl key while dragging the mouse will not change the line
            # orientation.
            self.draw_line(
                self.app.tool_start_x,
                self.app.tool_start_y,
                event.x,
                event.y,
                horizontal_first=event.ctrl,
            )

    def on_mouse_up(self, _: events.MouseDown) -> None:
        assert isinstance(self.app, TomodrawApp)
        self.app.draw = False

    def on_leave(self, _: events.Leave) -> None:
        assert isinstance(self.app, TomodrawApp)
        self.app.draw = False


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


class RectangleTool(ToolboxItem):
    def __init__(self) -> None:
        super().__init__(Label("Rectangle"), tool=Tool.RECTANGLE)


class TextTool(ToolboxItem):
    def __init__(self) -> None:
        super().__init__(Label("Text"), tool=Tool.TEXT)


class TextInputOverlay(Input):
    DEFAULT_CSS = """
    TextInputOverlay {
        layer: overlay;
        width: auto;
        height: auto;
        padding: 0;
        border: none;

        &:focus {
            border: none;
        }
    }
    """

    def __init__(
        self,
        start_x: int,
        start_y: int,
        max_length: int = 0,
    ) -> None:
        super().__init__(max_length=max_length)
        self.start_x = start_x
        self.start_y = start_y

    def dismiss(self) -> None:
        assert isinstance(self.app, TomodrawApp)
        canvas = self.app.query_one(Canvas)
        canvas.draw_text(self.value, self.start_x, self.start_y)
        self.remove()

    @on(Input.Submitted)
    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.dismiss()

    def on_blur(self, _: events.Blur) -> None:
        self.dismiss()


class LineTool(ToolboxItem):
    def __init__(self) -> None:
        super().__init__(Label("Line"), tool=Tool.LINE)


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
            RectangleTool(),
            TextTool(),
            LineTool(),
            PencilTool(),
            EraserTool(),
        )

    @property
    def selected_tool(self) -> Tool:
        tool_selected = self.highlighted_child
        assert isinstance(tool_selected, ToolboxItem)
        return tool_selected.tool


class MenuButton(Button, can_focus=False):
    DEFAULT_CSS = """
    MenuButton {
        height: 1;
        min-width: 8;
        border: none;
        padding: 0 1;
        background: $panel-lighten-1;
        &:hover {
            border: none;
            padding: 0 1;
            background: $panel;
        }
    }
    """

    def __init__(
        self,
        label: TextType | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ):
        super().__init__(
            label,
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )


class CanvasMenu(Container):
    DEFAULT_CSS = """
    CanvasMenu {
        width: 99;
        height: 1;
        layout: horizontal;
        align: right middle;
    }
    """

    def compose(self) -> ComposeResult:
        yield MenuButton("Copy to clipboard", id="copy-button")


class TomodrawApp(App):
    CSS = """
    Screen {
        align: center middle;
        layers: base overlay;
    }

    PencilSelectScreen {
        align: left top;
    }

    Horizontal {
        width: auto;
        height: auto;
        margin-bottom: 1;
    }
    """

    draw: bool = False

    tool_start_x = 0
    tool_start_y = 0

    last_canvas_grid: list[list[str]] = [[" "] * 80 for _ in range(24)]

    def compose(self) -> ComposeResult:
        yield CanvasMenu()
        with Horizontal():
            yield Toolbox()
            yield Canvas()

    @property
    def tool(self) -> Tool:
        return self.query_one(Toolbox).selected_tool

    @property
    def pencil_brush_char(self) -> str:
        return self.query_one(PencilTool).brush_char

    @on(MenuButton.Pressed, "#copy-button")
    def on_copy_button_pressed(self) -> None:
        canvas = self.query_one(Canvas)
        try:
            pyperclip.copy(canvas.grid_as_text)
            self.notify("Copied drawing to clipboard")
        except pyperclip.PyperclipException:
            self.notify("Error copying to clipboard", severity="error")


def run() -> None:
    app = TomodrawApp()
    app.run()
