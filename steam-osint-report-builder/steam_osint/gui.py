from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import traceback
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from .app import RunOptions, run_collection
from .models import CollectionResult, SteamReportError
from .reports import build_markdown


PROJECT_DIR = Path(__file__).resolve().parents[1]


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Steam OSINT Report Builder")
        self.root.geometry("1180x820")
        self.root.minsize(980, 680)

        self.api_enabled = tk.BooleanVar(value=False)
        self.dark_mode = tk.BooleanVar(value=False)
        self.api_key = tk.StringVar()
        self.output_dir = tk.StringVar(value=str((PROJECT_DIR / "output").resolve()))
        self.delay = tk.DoubleVar(value=1.0)
        self.retries = tk.IntVar(value=3)
        self.status = tk.StringVar(value="Ready.")
        self.cancelled = threading.Event()
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.worker_thread: threading.Thread | None = None
        self.last_results: list[CollectionResult] = []
        self.last_html_report: Path | None = None
        self.text_widgets: list[tk.Text] = []

        self._build_style()
        self._build_ui()
        self.root.after(150, self._drain_events)

    def _build_style(self) -> None:
        self.style = ttk.Style(self.root)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(2, weight=1)

        header = ttk.Frame(main)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Steam OSINT Report Builder", font=("Segoe UI", 16, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(header, text="Dark mode", variable=self.dark_mode, command=self._apply_theme).grid(row=0, column=1, sticky="e")

        form = ttk.LabelFrame(main, text="Collection")
        form.grid(row=1, column=0, sticky="ew", pady=8)
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="Targets:").grid(row=0, column=0, sticky="nw", padx=8, pady=6)
        self.targets_box = tk.Text(form, height=4, wrap="word", undo=True)
        self.targets_box.grid(row=0, column=1, columnspan=4, sticky="ew", padx=8, pady=6)
        self.targets_box.insert("1.0", "76561199100380710")
        self._add_context_menu(self.targets_box)

        ttk.Checkbutton(form, text="Use Steam Web API key", variable=self.api_enabled, command=self._toggle_api).grid(row=1, column=1, sticky="w", padx=8)
        ttk.Label(form, text="API key:").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        self.api_entry = ttk.Entry(form, textvariable=self.api_key, show="*", state="disabled")
        self.api_entry.grid(row=2, column=1, columnspan=4, sticky="ew", padx=8, pady=4)

        ttk.Label(form, text="Output:").grid(row=3, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(form, textvariable=self.output_dir).grid(row=3, column=1, sticky="ew", padx=8, pady=4)
        ttk.Button(form, text="Browse", command=self._browse_output).grid(row=3, column=2, padx=4)
        ttk.Label(form, text="Delay").grid(row=3, column=3, sticky="e")
        ttk.Spinbox(form, from_=0.2, to=10.0, increment=0.2, textvariable=self.delay, width=6).grid(row=3, column=4, sticky="w", padx=4)

        btns = ttk.Frame(main)
        btns.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        self.run_btn = ttk.Button(btns, text="Create Report", command=self.start)
        self.run_btn.pack(side="left")
        self.cancel_btn = ttk.Button(btns, text="Cancel", command=self.cancel, state="disabled")
        self.cancel_btn.pack(side="left", padx=6)
        ttk.Button(btns, text="Open Output Folder", command=self._open_output_folder).pack(side="left")
        self.open_html_btn = ttk.Button(btns, text="Open HTML Report", command=self._open_html_report, state="disabled")
        self.open_html_btn.pack(side="left", padx=6)
        ttk.Label(btns, textvariable=self.status).pack(side="left", padx=12)
        self.progress = ttk.Progressbar(btns, mode="indeterminate")
        self.progress.pack(side="right", fill="x", expand=True, padx=8)

        self.tabs = ttk.Notebook(main)
        self.tabs.grid(row=2, column=0, sticky="nsew", pady=8)
        self.help = self._tab("How to Use")
        self.profile = self._tab("Profile")
        self.games = self._tab("Games")
        self.friends = self._tab("Friends")
        self.content = self._tab("Public Content")
        self.raw = self._tab("Raw Evidence")
        self.console = self._tab("Status Console")
        self.report = self._tab("Final Report")
        self._set_text(self.help, HELP_TEXT)

    def _tab(self, name: str) -> scrolledtext.ScrolledText:
        frame = ttk.Frame(self.tabs)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        box = scrolledtext.ScrolledText(frame, wrap="word", undo=True)
        box.grid(row=0, column=0, sticky="nsew")
        self.tabs.add(frame, text=name)
        self.text_widgets.append(box)
        self._add_context_menu(box)
        return box

    def _add_context_menu(self, widget: tk.Text) -> None:
        menu = tk.Menu(widget, tearoff=False)
        menu.add_command(label="Copy", command=lambda: widget.event_generate("<<Copy>>"))
        menu.add_command(label="Paste", command=lambda: widget.event_generate("<<Paste>>"))
        menu.add_separator()
        menu.add_command(label="Select All", command=lambda: widget.tag_add("sel", "1.0", "end"))
        widget.bind("<Button-3>", lambda event: menu.tk_popup(event.x_root, event.y_root))

    def _apply_theme(self) -> None:
        dark = self.dark_mode.get()
        bg = "#0d1117" if dark else "#ffffff"
        fg = "#e6edf3" if dark else "#1f2328"
        insert = "#e6edf3" if dark else "#1f2328"
        for widget in self.text_widgets + [self.targets_box]:
            widget.configure(background=bg, foreground=fg, insertbackground=insert)

    def _toggle_api(self) -> None:
        self.api_entry.configure(state="normal" if self.api_enabled.get() else "disabled")

    def _browse_output(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.output_dir.get() or str(Path.cwd()))
        if selected:
            self.output_dir.set(selected)

    def _open_output_folder(self) -> None:
        path = self.last_results[-1].output_dir if self.last_results else Path(self.output_dir.get())
        path.mkdir(parents=True, exist_ok=True)
        self._open_path(path, "output folder")

    def _open_html_report(self) -> None:
        if not self.last_html_report or not self.last_html_report.exists():
            messagebox.showwarning("Report Missing", "No HTML report is available yet.")
            return
        self._open_path(self.last_html_report, "HTML report")

    def start(self) -> None:
        targets = [line.strip() for line in self.targets_box.get("1.0", "end").splitlines() if line.strip()]
        self.cancelled.clear()
        self.run_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.open_html_btn.configure(state="disabled")
        self.last_html_report = None
        self.progress.start(12)
        self.status.set("Working...")
        self._set_text(self.console, "")
        options = RunOptions(
            targets=targets,
            api_enabled=self.api_enabled.get(),
            api_key=self.api_key.get(),
            output_base=Path(self.output_dir.get()),
            delay=max(0.2, float(self.delay.get())),
            retries=max(1, int(self.retries.get())),
        )
        self.worker_thread = threading.Thread(target=self._worker, args=(options,), daemon=True)
        self.worker_thread.start()

    def cancel(self) -> None:
        self.cancelled.set()
        self.status.set("Cancelling...")
        self._log("Cancellation requested.")

    def _worker(self, options: RunOptions) -> None:
        try:
            results = run_collection(options, progress=self._queue_log, cancelled=self.cancelled)
            self.events.put(("done", results))
        except SteamReportError as exc:
            self.events.put(("error", str(exc)))
        except Exception:
            self.events.put(("error", traceback.format_exc()))

    def _queue_log(self, message: str) -> None:
        self.events.put(("log", message))

    def _drain_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "log":
                    self._log(str(payload))
                elif kind == "done":
                    self._display_results(payload)  # type: ignore[arg-type]
                elif kind == "error":
                    self._finish()
                    self.status.set("Error.")
                    messagebox.showerror("Error", str(payload))
        except queue.Empty:
            pass
        self.root.after(150, self._drain_events)

    def _display_results(self, results: list[CollectionResult]) -> None:
        self.last_results = results
        self._finish()
        if not results:
            self.status.set("Cancelled.")
            return
        result = results[-1]
        profile_name = result.profile.get("personaname") or result.profile.get("persona_name") or "Unknown"
        self._set_text(self.profile, "\n".join([
            f"Persona name: {profile_name}",
            f"Profile URL: {result.profile_url}",
            f"SteamID64: {result.steamid64 or 'Unknown'}",
            f"Mode: {result.mode}",
            f"Warnings: {len(result.warnings)}",
        ]))
        self._set_text(self.games, "\n".join((g.get("name") or str(g.get("appid")) or "Unknown") for g in result.games) or "No public games collected.")
        self._set_text(self.friends, "\n".join(f"{f.get('name') or f.get('steamid') or 'Friend'} {f.get('url', '')}" for f in result.friends) or "No public friends collected.")
        self._set_text(self.content, self._content_summary(result))
        self._set_text(self.raw, "\n".join(str(r.path) for r in result.evidence) or "No raw evidence files.")
        self._set_text(self.report, build_markdown(result))
        html_report = result.output_dir / "report.html"
        markdown_report = result.output_dir / "report.md"
        created = [path for path in (markdown_report, html_report) if path.exists()]
        self.last_html_report = html_report if html_report.exists() else None
        self.open_html_btn.configure(state="normal" if self.last_html_report else "disabled")
        self.status.set(f"Done. Created {len(created)} report file(s) in {result.output_dir}")
        self._log("Created files:")
        for path in created:
            self._log(f"  {path}")
        if html_report.exists():
            self._open_path(html_report, "HTML report")
        else:
            messagebox.showwarning("Report Missing", f"Expected HTML report was not found:\n{html_report}")

    def _open_path(self, path: Path, label: str) -> None:
        try:
            path = path.resolve()
            if path.is_dir():
                path.mkdir(parents=True, exist_ok=True)
            elif not path.exists():
                raise FileNotFoundError(path)

            if sys.platform.startswith("win"):
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
            self._log(f"Opened {label}: {path}")
        except Exception as exc:
            self._log(f"Could not open {label}: {exc}")
            messagebox.showerror("Open Failed", f"Could not open {label}:\n{path}\n\n{exc}")

    def _finish(self) -> None:
        self.progress.stop()
        self.run_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")

    def _log(self, message: str) -> None:
        self.console.insert("end", message + "\n")
        self.console.see("end")

    def _set_text(self, box: tk.Text, text: str) -> None:
        box.delete("1.0", "end")
        box.insert("1.0", text)

    @staticmethod
    def _content_summary(result: CollectionResult) -> str:
        lines = [
            f"Screenshots: {len(result.screenshots)}",
            f"Reviews: {len(result.reviews)}",
            f"Workshop items: {len(result.workshop_items)}",
            f"Groups: {len(result.groups)}",
            f"Badges: {len(result.badges)}",
            "",
            "Warnings:",
        ]
        lines.extend(result.warnings or ["None"])
        return "\n".join(lines)


HELP_TEXT = """Valid inputs, one per line for batch mode:

SteamID64:
  76561199100380710

Full profile URL:
  https://steamcommunity.com/profiles/76561199100380710

Custom URL:
  https://steamcommunity.com/id/Almightyjoe

Vanity only:
  Almightyjoe

Public Profile Mode uses public Steam Community pages only.
Steam API Mode uses official Steam Web API endpoints when you provide a key.
Private or unavailable data is never bypassed."""


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()
