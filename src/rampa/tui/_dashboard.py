"""Dashboard screen and app factory for the rampa TUI.

All Textual imports are deferred to this module so that
``import rampa.tui`` works without textual installed.

>>> import rampa.tui._dashboard
"""

from __future__ import annotations

import asyncio
import typing as t


def build_app() -> type:
    """Build and return the RampaDashboard App class.

    Defers all textual imports so the module stays importable
    without textual installed.

    Returns
    -------
    type
        The RampaDashboard App subclass.

    >>> import importlib.util
    >>> if importlib.util.find_spec("textual"):
    ...     cls = build_app()
    ...     cls.__name__
    ... else:
    ...     'RampaDashboard'
    'RampaDashboard'
    """
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal, Vertical
    from textual.widgets import Footer, Header, Static

    from rampa.engine import Engine
    from rampa.events import (
        LiveThresholdEvent,
        PauseEvent,
        PhaseEvent,
        ResumeEvent,
        RunResult,
        RunStatus,
        SnapshotEvent,
        ThresholdEvent,
    )
    from rampa.loader import TestPlan
    from rampa.runner import status_to_exit_code

    _DASHBOARD_CSS = """
    Screen {
        layout: vertical;
    }
    #phase {
        height: 1;
        background: $primary-background;
        color: $text;
        text-align: center;
        text-style: bold;
    }
    #metrics-grid {
        height: 1fr;
        layout: grid;
        grid-size: 2 1;
        grid-gutter: 1;
    }
    #left-panel {
        layout: vertical;
        border: tall $primary;
        padding: 0 1;
    }
    #right-panel {
        layout: vertical;
        border: tall $primary;
        padding: 0 1;
    }
    .section-title {
        text-style: bold;
        color: $text;
    }
    .metric-line {
        height: 1;
    }
    #thresholds-panel {
        height: auto;
        max-height: 6;
        border: tall $secondary;
        padding: 0 1;
    }
    """

    class RampaDashboard(App):  # type: ignore[type-arg]
        """Live dashboard for rampa load tests."""

        CSS = _DASHBOARD_CSS
        BINDINGS: t.ClassVar[list[t.Any]] = [
            ("q", "quit", "Quit"),
            ("p", "toggle_pause", "Pause/Resume"),
            ("s", "stop_run", "Stop"),
        ]

        def __init__(self, plan: TestPlan, **kwargs: t.Any) -> None:
            super().__init__(**kwargs)
            self._plan = plan
            self._result: RunResult | None = None
            self._controller: t.Any = None
            self._exit_code = 0

        @property
        def exit_code(self) -> int:
            """Process exit code after app exits."""
            return self._exit_code

        def compose(self) -> ComposeResult:
            """Build widget tree."""
            yield Header(show_clock=True)
            yield Static("starting...", id="phase")
            with Horizontal(id="metrics-grid"):
                with Vertical(id="left-panel"):
                    yield Static("[b]Execution[/b]", classes="section-title")
                    yield Static("VUs: -", id="vus")
                    yield Static("Iterations: -", id="iterations")
                    yield Static("Rate: -", id="rate")
                    yield Static("Errors: -", id="errors")
                    yield Static("Duration: -", id="duration")
                with Vertical(id="right-panel"):
                    yield Static("[b]HTTP Timing[/b]", classes="section-title")
                    yield Static("Requests: -", id="http-reqs")
                    yield Static("p(50): -", id="p50")
                    yield Static("p(90): -", id="p90")
                    yield Static("p(95): -", id="p95")
                    yield Static("p(99): -", id="p99")
            yield Static("", id="thresholds-panel")
            yield Footer()

        def on_mount(self) -> None:
            """Start the engine and event bridge."""
            self.run_worker(
                self._run_engine,
                name="engine",
                group="engine",
                thread=True,
                exclusive=True,
            )

        def _run_engine(self) -> None:
            """Worker thread: start engine, drain events via call_from_thread."""
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self._engine_lifecycle())
            finally:
                loop.close()

        async def _engine_lifecycle(self) -> None:
            """Async engine lifecycle running in worker thread."""
            engine = Engine(self._plan)
            controller = await engine.start()
            self._controller = controller

            self.call_from_thread(self._update_phase, "running")

            async for event in controller.events():
                if isinstance(event, SnapshotEvent):
                    snap = event.snapshot
                    self.call_from_thread(self._apply_snapshot, snap)
                elif isinstance(event, PhaseEvent):
                    self.call_from_thread(self._update_phase, event.phase)
                elif isinstance(event, PauseEvent):
                    self.call_from_thread(self._update_phase, "paused")
                elif isinstance(event, ResumeEvent):
                    self.call_from_thread(self._update_phase, "running")
                elif isinstance(event, (ThresholdEvent, LiveThresholdEvent)):
                    self.call_from_thread(self._apply_thresholds, event.results)

            result = await controller.wait()
            self._result = result
            self._exit_code = status_to_exit_code(result.status).value
            self.call_from_thread(self._apply_result, result)

        def _update_phase(self, phase: str) -> None:
            widget = self.query_one("#phase", Static)
            labels = {
                "setup": "▶ Setup",
                "execute": "▶ Executing",
                "running": "▶ Running",
                "paused": "⏸ Paused",
                "teardown": "▶ Teardown",
                "complete": "✓ Complete",
            }
            widget.update(labels.get(phase, phase))

        def _apply_snapshot(self, snap: t.Any) -> None:
            """Apply a MetricSnapshot to the dashboard widgets."""
            v = snap.values

            def _get(metric: str, stat: str) -> float:
                return v.get(metric, {}).get(stat, 0.0)

            def _fmt(val: float) -> str:
                if val == int(val) and val < 1e9:
                    return str(int(val))
                return f"{val:.2f}"

            def _ms(val: float) -> str:
                return f"{val:.1f}ms"

            self.query_one("#vus", Static).update(f"VUs: {_fmt(_get('vus', 'value'))}")
            self.query_one("#iterations", Static).update(
                f"Iterations: {_fmt(_get('iterations', 'count'))}"
            )
            self.query_one("#rate", Static).update(f"Rate: {_fmt(_get('iterations', 'rate'))}/s")
            self.query_one("#errors", Static).update(
                f"Errors: {_fmt(_get('iteration_errors', 'count'))}"
            )
            self.query_one("#duration", Static).update(f"Duration: {snap.duration:.1f}s")

            self.query_one("#http-reqs", Static).update(
                f"Requests: {_fmt(_get('http_reqs', 'count'))} "
                f"({_fmt(_get('http_reqs', 'rate'))}/s)"
            )
            self.query_one("#p50", Static).update(f"p(50): {_ms(_get('http_req_duration', 'med'))}")
            self.query_one("#p90", Static).update(
                f"p(90): {_ms(_get('http_req_duration', 'p(90)'))}"
            )
            self.query_one("#p95", Static).update(
                f"p(95): {_ms(_get('http_req_duration', 'p(95)'))}"
            )
            self.query_one("#p99", Static).update(
                f"p(99): {_ms(_get('http_req_duration', 'p(99)'))}"
            )

        def _apply_thresholds(self, results: list[t.Any]) -> None:
            lines: list[str] = ["[b]Thresholds[/b]"]
            for r in results:
                icon = "[green]✓[/green]" if r.passed else "[red]✗[/red]"
                lines.append(f"  {icon} {r.source}")
            self.query_one("#thresholds-panel", Static).update("\n".join(lines))

        def _apply_result(self, result: RunResult) -> None:
            self._update_phase("complete")
            status_text = result.status.value
            phase_widget = self.query_one("#phase", Static)
            if result.status == RunStatus.PASSED:
                phase_widget.update(f"[green]✓ {status_text}[/green]")
            else:
                phase_widget.update(f"[red]✗ {status_text}[/red]")

        def action_toggle_pause(self) -> None:
            """Toggle pause/resume."""
            if self._controller is None:
                return
            if self._controller.is_paused:
                self._controller.resume()
            else:
                self._controller.pause()

        def action_stop_run(self) -> None:
            """Stop the running test."""
            if self._controller is not None:
                asyncio.run_coroutine_threadsafe(
                    self._controller.stop("user requested via TUI"),
                    asyncio.get_event_loop(),
                )

    return RampaDashboard
