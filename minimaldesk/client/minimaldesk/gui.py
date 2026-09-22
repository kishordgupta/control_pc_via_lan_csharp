from __future__ import annotations
import os
import queue
import time
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
from .capture import CaptureWorker, decode_frame
from .input_control import InputController, enable_dpi_awareness
from .session import Session
from .transport import Transport
from .validation import normalize_key


class Viewer(tk.Toplevel):
    def __init__(self, app: "App"):
        super().__init__(app.root)
        self.app = app
        self.title(f"MinimalDesk — {app.session.peer}")
        self.geometry("1100x760")
        self.minsize(640, 400)
        self.protocol("WM_DELETE_WINDOW", app.stop_session)
        self.bar = ttk.Frame(self, padding=8)
        self.bar.pack(fill="x")
        ttk.Button(self.bar, text="End session", command=app.stop_session).pack(side="left")
        ttk.Button(self.bar, text="Release keyboard / mouse", command=self.release).pack(side="left", padx=8)
        ttk.Button(self.bar, text="Send Escape", command=self.send_escape).pack(side="left")
        self.mode = ttk.Label(self.bar)
        self.mode.pack(side="right")
        self.update_mode()
        self.canvas = tk.Canvas(self, highlightthickness=0, background="#20242a", cursor="crosshair", takefocus=True)
        self.canvas.pack(fill="both", expand=True)
        self.item = self.canvas.create_image(0, 0, anchor="nw")
        self.image = self.photo = None
        self.bounds = (0, 0, 1, 1)
        self.last_move = 0.0
        self.canvas.bind("<Configure>", lambda _: self.render())
        self.canvas.bind("<Motion>", self.motion)
        for number, name in ((1, "left"), (2, "middle"), (3, "right")):
            self.canvas.bind(f"<ButtonPress-{number}>", lambda e, b=name: self.button(e, b, True))
            self.canvas.bind(f"<ButtonRelease-{number}>", lambda e, b=name: self.button(e, b, False))
        self.canvas.bind("<MouseWheel>", lambda e: self.scroll(max(-5, min(5, int(e.delta / 120)))))
        self.canvas.bind("<Button-4>", lambda _: self.scroll(1))
        self.canvas.bind("<Button-5>", lambda _: self.scroll(-1))
        self.canvas.bind("<KeyPress>", lambda e: self.key(e, True))
        self.canvas.bind("<KeyRelease>", lambda e: self.key(e, False))
        self.canvas.bind("<FocusOut>", lambda _: self.app.session.send_input({"op": "release_all"}))

    def update_mode(self) -> None:
        self.mode.configure(text="CONTROL ENABLED · Escape releases focus" if self.app.session.control else "VIEW ONLY")

    def frame(self, jpeg: bytes) -> None:
        self.image = decode_frame(jpeg)
        self.render()

    def render(self) -> None:
        if self.image is None:
            return
        width, height = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        scale = min(width / self.image.width, height / self.image.height)
        w, h = max(1, round(self.image.width * scale)), max(1, round(self.image.height * scale))
        x, y = (width - w) // 2, (height - h) // 2
        self.bounds = (x, y, w, h)
        self.photo = ImageTk.PhotoImage(self.image.resize((w, h), Image.Resampling.BILINEAR))
        self.canvas.coords(self.item, x, y)
        self.canvas.itemconfigure(self.item, image=self.photo)

    def position(self, event) -> tuple[float, float] | None:
        x, y, w, h = self.bounds
        if self.image is None or not (x <= event.x < x + w and y <= event.y < y + h):
            return None
        return (event.x - x) / max(1, w - 1), (event.y - y) / max(1, h - 1)

    def motion(self, event, force=False) -> None:
        point = self.position(event)
        now = time.monotonic()
        if point is not None and (force or now - self.last_move > 1 / 30):
            self.app.session.send_input({"op": "move", "x": point[0], "y": point[1]})
            self.last_move = now

    def button(self, event, button: str, down: bool) -> str:
        if down and self.position(event) is None:
            return "break"
        if down:
            self.canvas.focus_set()
            self.motion(event, True)
        self.app.session.send_input({"op": "button", "button": button, "down": down})
        return "break"

    def scroll(self, steps: int) -> str:
        self.app.session.send_input({"op": "scroll", "steps": steps})
        return "break"

    def key(self, event, down: bool) -> str:
        if event.keysym == "Escape":
            if down:
                self.release()
            return "break"
        key = normalize_key(event.keysym)
        if key:
            self.app.session.send_input({"op": "key", "key": key, "down": down})
        return "break"

    def release(self) -> None:
        self.app.session.send_input({"op": "release_all"})
        self.bar.focus_set()

    def send_escape(self) -> None:
        for down in (True, False):
            self.app.session.send_input({"op": "key", "key": "Escape", "down": down})


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("MinimalDesk 0.1 — Attended Remote Support")
        root.geometry("860x680")
        root.minsize(740, 650)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.transport: Transport | None = None
        self.session = Session(self.send, self.event)
        self.controller: InputController | None = None
        self.capture: CaptureWorker | None = None
        self.viewer: Viewer | None = None
        self.strip: tk.Toplevel | None = None
        self.capture_busy = False
        self.last_capture = 0.0
        self.closed = False
        self.connection_error = ""
        self.server = tk.StringVar(value=os.environ.get("MINIDESK_URL", "wss://remote.example.com/ws"))
        self.username = tk.StringVar(value=os.environ.get("MINIDESK_USER", ""))
        self.token = tk.StringVar(value=os.environ.get("MINIDESK_TOKEN", ""))
        self.invite = tk.StringVar()
        self.join_invite = tk.StringVar()
        self.request_control = tk.BooleanVar(value=False)
        self.fps = tk.IntVar(value=5)
        self.status = tk.StringVar(value="Disconnected. Only connect to people you know and trust.")
        self.build()
        root.after(20, self.pump)

    def build(self) -> None:
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="MinimalDesk", font=("TkDefaultFont", 22, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Windows + Linux/X11 · One-use invitations · Host approval required").pack(anchor="w", pady=(2, 12))
        login = ttk.LabelFrame(outer, text="1. Connect to your relay", padding=10)
        login.pack(fill="x")
        login.columnconfigure(1, weight=1)
        for row, (label, variable, hidden) in enumerate((("Server", self.server, False), ("Username", self.username, False), ("Account token", self.token, True))):
            ttk.Label(login, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=3)
            ttk.Entry(login, textvariable=variable, show="*" if hidden else "").grid(row=row, column=1, sticky="ew", pady=3)
        self.connect_button = ttk.Button(login, text="Connect", command=self.connect)
        self.connect_button.grid(row=3, column=0, pady=(8, 0), sticky="w")
        ttk.Button(login, text="Disconnect", command=self.disconnect).grid(row=3, column=1, pady=(8, 0), sticky="w")
        host = ttk.LabelFrame(outer, text="2A. Let someone help on this computer", padding=10)
        host.pack(fill="x", pady=10)
        top = ttk.Frame(host); top.pack(fill="x")
        self.host_button = ttk.Button(top, text="Share this computer", command=self.host, state="disabled")
        self.host_button.pack(side="left")
        ttk.Label(top, text="Frames / second:").pack(side="left", padx=(20, 6))
        ttk.Spinbox(top, from_=1, to=10, textvariable=self.fps, width=4, state="readonly").pack(side="left")
        ttk.Label(host, text="Send the invitation privately. It expires after 5 minutes and works for one attempt.").pack(anchor="w", pady=(8, 3))
        invitation_row = ttk.Frame(host); invitation_row.pack(fill="x")
        ttk.Entry(invitation_row, textvariable=self.invite, state="readonly").pack(side="left", fill="x", expand=True)
        self.copy_button = ttk.Button(invitation_row, text="Copy", command=self.copy_invite, state="disabled")
        self.copy_button.pack(side="left", padx=(6, 0))
        self.request_box = ttk.LabelFrame(outer, text="Verified incoming request", padding=10)
        self.request_label = ttk.Label(self.request_box, wraplength=760)
        self.request_label.pack(anchor="w")
        choices = ttk.Frame(self.request_box); choices.pack(fill="x", pady=(8, 0))
        ttk.Button(choices, text="Allow view only", command=lambda: self.approve(False)).pack(side="left")
        self.allow_control_button = ttk.Button(choices, text="Allow keyboard + mouse", command=lambda: self.approve(True))
        self.allow_control_button.pack(side="left", padx=8)
        ttk.Button(choices, text="Deny", command=self.stop_session).pack(side="left")
        join = self.join_box = ttk.LabelFrame(outer, text="2B. Help on another computer", padding=10)
        join.pack(fill="x")
        ttk.Entry(join, textvariable=self.join_invite).pack(fill="x")
        ttk.Checkbutton(join, text="Request keyboard and mouse control (the host must approve)", variable=self.request_control).pack(anchor="w", pady=7)
        self.join_button = ttk.Button(join, text="Join invitation", command=self.join, state="disabled")
        self.join_button.pack(anchor="w")
        ttk.Button(outer, text="STOP SESSION", command=self.stop_session).pack(anchor="w", pady=12)
        ttk.Label(outer, textvariable=self.status, wraplength=780).pack(anchor="w")
        ttk.Label(outer, text="No unattended access, file transfer, clipboard sync, audio, or recording.\nOn the host, Ctrl+Alt+F12 stops an active session.", foreground="#555555").pack(anchor="w", pady=(10, 0))

    def send(self, message: dict) -> None:
        if self.transport:
            self.transport.send(message)

    def controls(self) -> None:
        state = "normal" if self.session.connected and self.session.state == "idle" and not self.session.awaiting_stop else "disabled"
        self.host_button.configure(state=state)
        self.join_button.configure(state=state)
        self.connect_button.configure(state="disabled" if self.transport else "normal")
        self.copy_button.configure(state="normal" if self.invite.get().startswith("MD1.") else "disabled")

    def connect(self) -> None:
        if self.transport:
            return
        try:
            user, token = self.username.get().strip(), self.token.get().strip()
            if not user or not token:
                raise ValueError("Enter a username and the token issued by your server administrator")
            self.connection_error = ""
            self.transport = Transport(self.server.get(), user, token)
            self.transport.start()
            self.status.set("Connecting and authenticating…")
            self.controls()
        except Exception as exc:
            self.transport = None
            messagebox.showerror("Cannot connect", str(exc), parent=self.root)

    def disconnect(self) -> None:
        self.session.disconnect()
        if self.transport:
            self.transport.stop()
        self.controls()

    def host(self) -> None:
        try:
            # Open only the input/display connection here. No image is captured yet.
            self.controller = InputController()
            self.session.begin_host()
            self.status.set("Creating a one-use invitation. Nothing is being shared yet.")
            self.controls()
        except Exception as exc:
            self.cleanup()
            messagebox.showerror("Cannot host", str(exc), parent=self.root)

    def join(self) -> None:
        try:
            self.session.begin_join(self.join_invite.get(), self.request_control.get())
            self.join_invite.set("")
            self.status.set("Request sent. Waiting for the host to approve.")
            self.controls()
        except Exception as exc:
            messagebox.showerror("Cannot join", str(exc), parent=self.root)

    def copy_invite(self) -> None:
        if self.invite.get().startswith("MD1."):
            self.root.clipboard_clear()
            self.root.clipboard_append(self.invite.get())
            self.status.set("Invitation copied. Share privately with the person you expect.")

    def approve(self, control: bool) -> None:
        try:
            self.session.approve(control)
            self.request_box.pack_forget()
            self.status.set("Approval sent. Establishing the encrypted session.")
        except ValueError as exc:
            self.status.set(str(exc))

    def stop_session(self) -> None:
        self.session.stop()

    def cleanup(self) -> None:
        if self.capture:
            self.capture.stop()
            self.capture = None
        self.capture_busy = False
        if self.controller:
            self.controller.close()
            self.controller = None
        if self.viewer:
            self.viewer.destroy()
            self.viewer = None
        if self.strip:
            self.strip.destroy()
            self.strip = None
        self.request_box.pack_forget()
        self.invite.set("")

    def event(self, kind: str, value: object) -> None:
        if kind == "ready":
            self.token.set("")
            self.status.set(f"Connected as {value}. Choose Share or Join.")
        elif kind == "invitation":
            self.invite.set(str(value))
            self.status.set("Waiting for a viewer. No desktop capture until you approve.")
        elif kind == "pending":
            self.invite.set("")  # Never show the invitation secret in shared screen frames.
            self.status.set(f"Pairing with {value}; verifying the invitation key.")
        elif kind == "request":
            self.request_label.configure(text=f"{value['peer']} has the invitation key and requests " + ("keyboard/mouse control." if value['control'] else "view-only access.") + " Approve only if this is the person you expect.")
            self.allow_control_button.configure(state="normal" if value["control"] else "disabled")
            self.request_box.pack(fill="x", pady=8, before=self.join_box)
            self.root.geometry(f"860x{min(800, self.root.winfo_screenheight()-70)}")
            self.root.lift()
            self.root.bell()
        elif kind == "started":
            self.status.set(f"Session active with {value['peer']} — " + ("control enabled" if value['control'] else "view only"))
            if value["role"] == "host":
                self.invite.set("")
                self.request_box.pack_forget()
                if self.controller is None:
                    self.session.stop("Host backend was closed")
                    return
                self.controller.enable(value["control"])
                self.strip = tk.Toplevel(self.root)
                self.strip.title("MinimalDesk — SCREEN SHARING ACTIVE")
                self.strip.attributes("-topmost", True)
                self.strip.protocol("WM_DELETE_WINDOW", self.stop_session)
                ttk.Label(self.strip, text=f"SHARING WITH {value['peer']} · Ctrl+Alt+F12 to stop", padding=10).pack(side="left")
                ttk.Button(self.strip, text="STOP", command=self.stop_session).pack(side="left", padx=8)
                ttk.Button(self.strip, text="Revoke control", command=self.session.revoke).pack(side="left", padx=8)
                self.root.update_idletasks()
                self.capture = CaptureWorker()
            else:
                self.viewer = Viewer(self)
        elif kind == "frame" and self.viewer:
            try:
                number, _, _, jpeg = value
                self.viewer.frame(jpeg)
                self.session.ack_frame(number)
            except Exception as exc:
                self.session.stop(f"Cannot decode frame: {exc}")
        elif kind == "input" and self.controller:
            try:
                self.controller.handle(value)
            except Exception as exc:
                self.session.stop(f"Input stopped: {exc}")
        elif kind == "revoked":
            if self.controller:
                self.controller.enable(False)
            if self.viewer:
                self.viewer.update_mode()
            self.status.set("Remote control revoked. The session is view-only.")
        elif kind in {"ended", "disconnected"}:
            self.cleanup()
            self.status.set(str(value))
        elif kind == "error":
            if not self.session.connected:
                self.connection_error = str(value).replace("_", " ")
            self.status.set(str(value).replace("_", " "))
        self.controls()

    def pump(self) -> None:
        if self.closed:
            return
        try:
            if self.transport:
                for _ in range(32):
                    try:
                        kind, data = self.transport.inbox.get_nowait()
                    except queue.Empty:
                        break
                    if kind == "message":
                        self.session.handle(data)
                    elif kind == "disconnected":
                        self.session.disconnect(self.connection_error or "Disconnected")
                    else:
                        if not self.connection_error:
                            self.connection_error = str(data)
                        self.status.set(self.connection_error)
                if self.transport.finished.is_set() and self.transport.inbox.empty():
                    self.transport = None
                    if self.session.connected:
                        self.session.disconnect()
                    self.controls()
            self.session.tick()
            if self.capture and self.session.state == "active":
                if self.controller and self.controller.backend.stop_requested():
                    self.session.stop("Stopped locally with Ctrl+Alt+F12")
                else:
                    try:
                        kind, data = self.capture.result.get_nowait()
                        self.capture_busy = False
                        if kind == "error":
                            self.session.stop(str(data))
                        elif self.controller:
                            w, h, jpeg = data
                            self.controller.backend.width, self.controller.backend.height = w, h
                            self.session.send_frame(w, h, jpeg)
                    except queue.Empty:
                        pass
                    now = time.monotonic()
                    if self.capture and not self.capture_busy and not self.session.waiting_frame and now - self.last_capture >= 1 / max(1, min(10, self.fps.get())):
                        self.capture.request()
                        self.capture_busy, self.last_capture = True, now
        except Exception as exc:
            self.session.stop(f"Session stopped after an error: {exc}")
        finally:
            if not self.closed:
                self.root.after(20, self.pump)

    def close(self) -> None:
        self.closed = True
        self.disconnect()
        self.root.destroy()


def main() -> None:
    enable_dpi_awareness()
    root = tk.Tk()
    App(root)
    root.mainloop()
