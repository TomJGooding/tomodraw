from textual.app import App, ComposeResult
from textual.strip import Strip
from textual.widget import Widget


class Canvas(Widget):
    DEFAULT_CSS = """
    Canvas {
        width: 80;
        height: 24;
        hatch: "🭽" $panel-lighten-1;
    }
    """

    def render_line(self, y: int) -> Strip:
        return Strip.blank(80)


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
