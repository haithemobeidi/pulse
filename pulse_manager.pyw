"""
Pulse Manager - Server Control GUI
Double-click to launch. Controls start/stop/restart with live log output.
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
import subprocess
import threading
import os
import sys
import signal
import time
import queue
import re

# Resolve paths relative to this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(BASE_DIR, "venv", "Scripts", "python.exe")
LOG_FILE = os.path.join(BASE_DIR, "data", "server.log")


class PulseManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Pulse Manager")
        self.root.geometry("780x560")
        self.root.minsize(640, 450)
        self.root.configure(bg="#1a1a2e")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Try to set icon
        ico_path = os.path.join(BASE_DIR, "pulse.ico")
        if os.path.exists(ico_path):
            self.root.iconbitmap(ico_path)

        self.server_process = None
        self.log_queue = queue.Queue()
        self.running = False

        # Check if server is already running on port 5000
        self.check_existing_server()

        self.build_ui()
        self.poll_log_queue()

    def check_existing_server(self):
        """Check if something is already listening on port 5000"""
        try:
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            for line in result.stdout.splitlines():
                if ":5000 " in line and "LISTENING" in line:
                    parts = line.split()
                    self.existing_pid = parts[-1]
                    self.running = True
                    return
        except Exception:
            pass
        self.existing_pid = None

    def build_ui(self):
        # ── Header ──
        header = tk.Frame(self.root, bg="#16213e", pady=12)
        header.pack(fill="x")

        title = tk.Label(
            header, text="PULSE", font=("Segoe UI", 22, "bold"),
            fg="#00d4ff", bg="#16213e"
        )
        title.pack()

        subtitle = tk.Label(
            header, text="Server Manager", font=("Segoe UI", 10),
            fg="#8892b0", bg="#16213e"
        )
        subtitle.pack()

        # ── Status Bar ──
        status_frame = tk.Frame(self.root, bg="#1a1a2e", pady=8)
        status_frame.pack(fill="x", padx=16)

        self.status_indicator = tk.Canvas(
            status_frame, width=14, height=14,
            bg="#1a1a2e", highlightthickness=0
        )
        self.status_indicator.pack(side="left", padx=(0, 8))

        self.status_label = tk.Label(
            status_frame, text="Checking...", font=("Segoe UI", 11),
            fg="#ccd6f6", bg="#1a1a2e"
        )
        self.status_label.pack(side="left")

        self.url_label = tk.Label(
            status_frame, text="", font=("Segoe UI", 10, "underline"),
            fg="#00d4ff", bg="#1a1a2e", cursor="hand2"
        )
        self.url_label.pack(side="right")
        self.url_label.bind("<Button-1>", lambda e: self.open_browser())

        self.update_status_display()

        # ── Control Buttons ──
        btn_frame = tk.Frame(self.root, bg="#1a1a2e", pady=6)
        btn_frame.pack(fill="x", padx=16)

        btn_style = {
            "font": ("Segoe UI", 10, "bold"),
            "relief": "flat",
            "cursor": "hand2",
            "padx": 20,
            "pady": 6,
            "borderwidth": 0,
        }

        self.start_btn = tk.Button(
            btn_frame, text="Start", bg="#00b894", fg="white",
            activebackground="#00a381", command=self.start_server, **btn_style
        )
        self.start_btn.pack(side="left", padx=(0, 8))

        self.stop_btn = tk.Button(
            btn_frame, text="Stop", bg="#e74c3c", fg="white",
            activebackground="#c0392b", command=self.stop_server, **btn_style
        )
        self.stop_btn.pack(side="left", padx=(0, 8))

        self.restart_btn = tk.Button(
            btn_frame, text="Restart", bg="#f39c12", fg="white",
            activebackground="#d68910", command=self.restart_server, **btn_style
        )
        self.restart_btn.pack(side="left", padx=(0, 8))

        self.browser_btn = tk.Button(
            btn_frame, text="Open Browser", bg="#3498db", fg="white",
            activebackground="#2980b9", command=self.open_browser, **btn_style
        )
        self.browser_btn.pack(side="right")

        # ── Log Output ──
        log_header = tk.Frame(self.root, bg="#1a1a2e", pady=(4))
        log_header.pack(fill="x", padx=16)

        tk.Label(
            log_header, text="Server Log", font=("Segoe UI", 10, "bold"),
            fg="#8892b0", bg="#1a1a2e"
        ).pack(side="left")

        self.clear_btn = tk.Button(
            log_header, text="Clear", font=("Segoe UI", 8),
            bg="#2d2d44", fg="#8892b0", relief="flat", cursor="hand2",
            command=self.clear_log, borderwidth=0
        )
        self.clear_btn.pack(side="right")

        log_frame = tk.Frame(self.root, bg="#0a0a1a", padx=2, pady=2)
        log_frame.pack(fill="both", expand=True, padx=16, pady=(4, 16))

        self.log_text = scrolledtext.ScrolledText(
            log_frame, wrap="word", font=("Consolas", 9),
            bg="#0a0a1a", fg="#a8b2d1", insertbackground="#ccd6f6",
            selectbackground="#2d2d44", relief="flat", borderwidth=0,
            state="disabled"
        )
        self.log_text.pack(fill="both", expand=True)

        # Configure log text tags for colored output
        self.log_text.tag_config("info", foreground="#a8b2d1")
        self.log_text.tag_config("success", foreground="#00b894")
        self.log_text.tag_config("error", foreground="#e74c3c")
        self.log_text.tag_config("warning", foreground="#f39c12")
        self.log_text.tag_config("url", foreground="#00d4ff")
        self.log_text.tag_config("timestamp", foreground="#6272a4")

        self.log_message("Pulse Manager started.", "info")
        if self.running:
            pid_info = f" (PID: {self.existing_pid})" if self.existing_pid else ""
            self.log_message(f"Detected running server{pid_info}.", "success")

        self.update_button_states()

    def update_status_display(self):
        self.status_indicator.delete("all")
        if self.running:
            self.status_indicator.create_oval(2, 2, 12, 12, fill="#00b894", outline="#00b894")
            self.status_label.config(text="Running", fg="#00b894")
            self.url_label.config(text="http://localhost:5000")
        else:
            self.status_indicator.create_oval(2, 2, 12, 12, fill="#e74c3c", outline="#e74c3c")
            self.status_label.config(text="Stopped", fg="#e74c3c")
            self.url_label.config(text="")

    def update_button_states(self):
        if self.running:
            self.start_btn.config(state="disabled", bg="#555555")
            self.stop_btn.config(state="normal", bg="#e74c3c")
            self.restart_btn.config(state="normal", bg="#f39c12")
            self.browser_btn.config(state="normal", bg="#3498db")
        else:
            self.start_btn.config(state="normal", bg="#00b894")
            self.stop_btn.config(state="disabled", bg="#555555")
            self.restart_btn.config(state="disabled", bg="#555555")
            self.browser_btn.config(state="disabled", bg="#555555")

    def log_message(self, message, tag="info"):
        timestamp = time.strftime("%H:%M:%S")
        self.log_queue.put((f"[{timestamp}] {message}\n", tag))

    def poll_log_queue(self):
        """Process queued log messages on the main thread"""
        while not self.log_queue.empty():
            message, tag = self.log_queue.get_nowait()
            self.log_text.config(state="normal")
            self.log_text.insert("end", message, tag)
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        self.root.after(100, self.poll_log_queue)

    def clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    def start_server(self):
        if self.running:
            self.log_message("Server is already running.", "warning")
            return

        if not os.path.exists(VENV_PYTHON):
            self.log_message("ERROR: Virtual environment not found!", "error")
            self.log_message("Run: python -m venv venv", "error")
            self.log_message("Then: venv\\Scripts\\pip install -r requirements.txt", "error")
            return

        self.log_message("Starting Pulse server...", "info")

        # Ensure data directory exists for logs
        os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)

        def run_server():
            try:
                env = os.environ.copy()
                env["PYTHONPATH"] = BASE_DIR
                self.server_process = subprocess.Popen(
                    [VENV_PYTHON, "-m", "backend.app"],
                    cwd=BASE_DIR,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    env=env,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    bufsize=1,
                    text=True
                )
                self.running = True
                self.root.after(0, self.update_status_display)
                self.root.after(0, self.update_button_states)
                self.log_message("Server started! Opening http://localhost:5000", "success")

                # Stream output to log
                for line in self.server_process.stdout:
                    line = line.rstrip()
                    if not line:
                        continue
                    # Color-code log lines
                    if "error" in line.lower() or "traceback" in line.lower():
                        tag = "error"
                    elif "warning" in line.lower():
                        tag = "warning"
                    elif "running on" in line.lower() or "started" in line.lower():
                        tag = "success"
                    else:
                        tag = "info"
                    self.log_queue.put((f"{line}\n", tag))

                # Process ended
                proc = self.server_process
                if proc is not None:
                    proc.wait()
                    exit_code = proc.returncode
                    self.running = False
                    self.server_process = None
                    self.root.after(0, self.update_status_display)
                    self.root.after(0, self.update_button_states)
                    if exit_code != 0:
                        self.log_message(f"Server exited with code {exit_code}.", "error")
                    else:
                        self.log_message("Server stopped.", "info")

            except Exception as e:
                # Don't log if we were intentionally stopped
                if self.server_process is not None:
                    self.log_message(f"Server error: {e}", "error")
                self.running = False
                self.root.after(0, self.update_status_display)
                self.root.after(0, self.update_button_states)

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()

    def stop_server(self):
        if self.server_process:
            self.log_message("Stopping server...", "warning")
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
            self.server_process = None
            self.running = False
            self.log_message("Server stopped.", "info")
        elif self.existing_pid:
            self.log_message(f"Stopping external server (PID: {self.existing_pid})...", "warning")
            try:
                subprocess.run(
                    ["taskkill", "/PID", self.existing_pid, "/F"],
                    capture_output=True, timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                self.existing_pid = None
                self.running = False
                self.log_message("Server stopped.", "info")
            except Exception as e:
                self.log_message(f"Failed to stop: {e}", "error")
        else:
            self.log_message("No server to stop.", "warning")

        self.update_status_display()
        self.update_button_states()

    def restart_server(self):
        self.log_message("Restarting server...", "warning")
        self.stop_server()
        # Small delay before restart
        self.root.after(1500, self.start_server)

    def open_browser(self):
        if self.running:
            os.startfile("http://localhost:5000")
        else:
            self.log_message("Start the server first.", "warning")

    def on_close(self):
        if self.server_process:
            self.log_message("Shutting down server...", "warning")
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=3)
            except Exception:
                self.server_process.kill()
        self.root.destroy()


def main():
    root = tk.Tk()

    # Center window on screen
    root.update_idletasks()
    w, h = 780, 560
    x = (root.winfo_screenwidth() // 2) - (w // 2)
    y = (root.winfo_screenheight() // 2) - (h // 2)
    root.geometry(f"{w}x{h}+{x}+{y}")

    app = PulseManager(root)
    root.mainloop()


if __name__ == "__main__":
    main()
