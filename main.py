import io
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import cv2
import numpy as np
from PIL import Image, ImageGrab, ImageTk


class ImageDistorterApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Image Distorter")
        self.root.geometry("1000x750")
        self.root.minsize(600, 500)

        self.image_original: np.ndarray | None = None
        self.distorted_image: np.ndarray | None = None
        self.image_tk: ImageTk.PhotoImage | None = None  # prevent GC
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.points: list[tuple[float, float]] = []
        self.mode = "idle"  # "idle" | "annotating" | "result"
        self.drag_index: int | None = None

        self._build_menu()
        self._build_toolbar()
        self._build_canvas()
        self._build_statusbar()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_menu(self):
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Open Image…", accelerator="Ctrl+O", command=self.open_image)
        file_menu.add_command(label="Paste from Clipboard", accelerator="Ctrl+V", command=self.paste_from_clipboard)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.destroy)
        menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=False)
        edit_menu.add_command(label="Undo", accelerator="Ctrl+Z", command=self.undo)
        menubar.add_cascade(label="Edit", menu=edit_menu)

        self.root.config(menu=menubar)
        self.root.bind_all("<Control-o>", lambda _: self.open_image())
        self.root.bind_all("<Control-v>", lambda _: self.paste_from_clipboard())
        self.root.bind_all("<Control-z>", lambda _: self.undo())

    def _build_toolbar(self):
        bar = ttk.Frame(self.root, padding=(4, 3))
        bar.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(bar, text="Open Image", command=self.open_image).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="Paste from Clipboard", command=self.paste_from_clipboard).pack(side=tk.LEFT, padx=2)
        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=2)
        ttk.Button(bar, text="Clear Points", command=self.clear_points).pack(side=tk.LEFT, padx=2)
        self.btn_distort = ttk.Button(bar, text="Distort", command=self.distort, state=tk.DISABLED)
        self.btn_distort.pack(side=tk.LEFT, padx=2)
        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=2)
        self.btn_restore = ttk.Button(bar, text="Restore Original", command=self.restore_original, state=tk.DISABLED)
        self.btn_restore.pack(side=tk.LEFT, padx=2)
        self.btn_copy = ttk.Button(bar, text="Copy to Clipboard", command=self.copy_to_clipboard, state=tk.DISABLED)
        self.btn_copy.pack(side=tk.LEFT, padx=2)
        self.btn_save = ttk.Button(bar, text="Save As…", command=self.save_image, state=tk.DISABLED)
        self.btn_save.pack(side=tk.LEFT, padx=2)

    def _build_canvas(self):
        frame = ttk.Frame(self.root, relief=tk.SUNKEN, borderwidth=1)
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 3))
        self.canvas = tk.Canvas(frame, bg="#1e1e1e", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Motion>", self._on_hover)
        self.canvas.bind("<Configure>", self._on_resize)

    def _build_statusbar(self):
        self.status_var = tk.StringVar(value="Open an image to get started.")
        ttk.Label(
            self.root, textvariable=self.status_var,
            relief=tk.SUNKEN, anchor=tk.W, padding=(4, 2),
        ).pack(side=tk.BOTTOM, fill=tk.X)

    # ── Image loading ────────────────────────────────────────────────────────

    def open_image(self):
        path = filedialog.askopenfilename(
            title="Open Image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.webp"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        img = cv2.imread(path)
        if img is None:
            messagebox.showerror("Error", f"Could not load image:\n{path}")
            return
        self._load_image(img)
        h, w = img.shape[:2]
        self.status_var.set(f"{path}  |  {w}×{h}  |  Click to place 4 points (any order).")

    def paste_from_clipboard(self):
        try:
            img = ImageGrab.grabclipboard()
        except Exception as e:
            messagebox.showerror("Error", f"Could not read from clipboard:\n{e}")
            return
        if not isinstance(img, Image.Image):
            messagebox.showinfo("Clipboard", "No image found in clipboard.")
            return
        img_np = np.array(img.convert("RGB"))
        cv_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        self._load_image(cv_img)
        h, w = cv_img.shape[:2]
        self.status_var.set(f"Pasted from clipboard  |  {w}×{h}  |  Click to place 4 points (any order).")

    def _load_image(self, cv_img: np.ndarray):
        self.image_original = cv_img
        self.distorted_image = None
        self.mode = "annotating"
        self.points.clear()
        self._sync_buttons()
        self._render(self.image_original)

    # ── Canvas rendering ─────────────────────────────────────────────────────

    def _render(self, cv_img: np.ndarray):
        self.canvas.update_idletasks()
        cw = max(self.canvas.winfo_width(), 1)
        ch = max(self.canvas.winfo_height(), 1)
        ih, iw = cv_img.shape[:2]

        self.scale = min(cw / iw, ch / ih, 1.0)
        nw = int(iw * self.scale)
        nh = int(ih * self.scale)
        self.offset_x = (cw - nw) // 2
        self.offset_y = (ch - nh) // 2

        rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb).resize((nw, nh), Image.LANCZOS)
        self.image_tk = ImageTk.PhotoImage(pil)

        self.canvas.delete("all")
        self.canvas.create_image(self.offset_x, self.offset_y, anchor=tk.NW, image=self.image_tk)
        if self.mode == "annotating":
            self._draw_points()

    def _draw_points(self):
        COLORS = ("#ef4444", "#22c55e", "#3b82f6", "#eab308")
        self.canvas.delete("point")

        n = len(self.points)
        canvas_coords = [
            (ix * self.scale + self.offset_x, iy * self.scale + self.offset_y)
            for ix, iy in self.points
        ]

        if n >= 2:
            if n == 4:
                # Draw closed quad in sorted (non-self-intersecting) order
                sorted_pts = self._sort_quad(np.float32(self.points))
                line_coords = [
                    (px * self.scale + self.offset_x, py * self.scale + self.offset_y)
                    for px, py in sorted_pts
                ]
                for i in range(4):
                    p1, p2 = line_coords[i], line_coords[(i + 1) % 4]
                    self.canvas.create_line(
                        p1[0], p1[1], p2[0], p2[1],
                        fill="white", width=1.5, dash=(5, 3), tags="point",
                    )
            else:
                # Connect partial points in click order
                for i in range(n - 1):
                    p1, p2 = canvas_coords[i], canvas_coords[i + 1]
                    self.canvas.create_line(
                        p1[0], p1[1], p2[0], p2[1],
                        fill="white", width=1.5, dash=(5, 3), tags="point",
                    )

        for i, (cx, cy) in enumerate(canvas_coords):
            r = 8
            self.canvas.create_oval(
                cx - r, cy - r, cx + r, cy + r,
                fill=COLORS[i], outline="white", width=2, tags="point",
            )
            self.canvas.create_text(
                cx, cy, text=str(i + 1),
                fill="white", font=("Segoe UI", 8, "bold"), tags="point",
            )

    def _on_resize(self, _):
        if self.mode == "idle":
            return
        src = self.distorted_image if self.mode == "result" else self.image_original
        if src is not None:
            self._render(src)

    # ── Point placement & dragging ───────────────────────────────────────────

    def _point_at(self, canvas_x: float, canvas_y: float, radius: float = 12) -> int | None:
        for i, (ix, iy) in enumerate(self.points):
            cx = ix * self.scale + self.offset_x
            cy = iy * self.scale + self.offset_y
            if (canvas_x - cx) ** 2 + (canvas_y - cy) ** 2 <= radius ** 2:
                return i
        return None

    def _on_click(self, event):
        if self.mode != "annotating" or self.image_original is None:
            return
        hit = self._point_at(event.x, event.y)
        if hit is not None:
            self.drag_index = hit
            return
        if len(self.points) >= 4:
            return
        ih, iw = self.image_original.shape[:2]
        ix = (event.x - self.offset_x) / self.scale
        iy = (event.y - self.offset_y) / self.scale
        if not (0 <= ix <= iw and 0 <= iy <= ih):
            return
        self.points.append((ix, iy))
        self._draw_points()
        remaining = 4 - len(self.points)
        if remaining > 0:
            self.status_var.set(f"Point {len(self.points)} placed — {remaining} more to go (Ctrl+Z to undo).")
        else:
            self.btn_distort.config(state=tk.NORMAL)
            self.status_var.set("All 4 points placed. Click 'Distort' to apply perspective correction.")

    def _on_drag(self, event):
        if self.mode != "annotating" or self.drag_index is None or self.image_original is None:
            return
        ih, iw = self.image_original.shape[:2]
        ix = max(0.0, min((event.x - self.offset_x) / self.scale, float(iw)))
        iy = max(0.0, min((event.y - self.offset_y) / self.scale, float(ih)))
        self.points[self.drag_index] = (ix, iy)
        self._draw_points()

    def _on_release(self, _):
        self.drag_index = None

    def _on_hover(self, event):
        if self.mode != "annotating":
            return
        cursor = "fleur" if self._point_at(event.x, event.y) is not None else "crosshair"
        self.canvas.config(cursor=cursor)

    def clear_points(self):
        self.points.clear()
        if self.image_original is not None:
            self.mode = "annotating"
            self._render(self.image_original)
            self.status_var.set("Points cleared — click to place 4 points (any order).")
        self._sync_buttons()

    # ── Undo / restore ───────────────────────────────────────────────────────

    def undo(self):
        if self.mode == "result":
            self.restore_original()
        elif self.mode == "annotating" and self.points:
            self.points.pop()
            self._render(self.image_original)
            self._sync_buttons()
            remaining = 4 - len(self.points)
            if self.points:
                self.status_var.set(f"Point removed — {remaining} more to go (Ctrl+Z to undo).")
            else:
                self.status_var.set("All points cleared — click to place 4 points (any order).")

    def restore_original(self):
        if self.image_original is None:
            return
        self.distorted_image = None
        self.mode = "annotating"
        self._render(self.image_original)
        self._sync_buttons()
        h, w = self.image_original.shape[:2]
        n = len(self.points)
        if n == 4:
            self.status_var.set(f"Restored original  |  {w}×{h}  |  4 points placed. Click 'Distort' to apply.")
        else:
            self.status_var.set(f"Restored original  |  {w}×{h}  |  Click to place 4 points (any order).")

    # ── Perspective distortion ───────────────────────────────────────────────

    def distort(self):
        if len(self.points) != 4 or self.image_original is None:
            return
        src = self._sort_quad(np.float32(self.points))  # [TL, TR, BR, BL]
        w = int(max(
            np.linalg.norm(src[1] - src[0]),  # top edge
            np.linalg.norm(src[2] - src[3]),  # bottom edge
        ))
        h = int(max(
            np.linalg.norm(src[3] - src[0]),  # left edge
            np.linalg.norm(src[2] - src[1]),  # right edge
        ))
        dst = np.float32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]])
        M = cv2.getPerspectiveTransform(src, dst)
        self.distorted_image = cv2.warpPerspective(self.image_original, M, (w, h))
        self.mode = "result"
        self._render(self.distorted_image)
        self._sync_buttons()
        self.status_var.set(f"Done — output: {w}×{h}.  Use 'Restore Original' (Ctrl+Z), 'Copy to Clipboard', or 'Save As…'.")

    @staticmethod
    def _sort_quad(pts: np.ndarray) -> np.ndarray:
        """Order 4 points as [top-left, top-right, bottom-right, bottom-left]."""
        s = pts.sum(axis=1)
        d = np.diff(pts, axis=1).ravel()
        return np.float32([pts[s.argmin()], pts[d.argmin()], pts[s.argmax()], pts[d.argmax()]])

    # ── Output actions ───────────────────────────────────────────────────────

    def copy_to_clipboard(self):
        if self.distorted_image is None:
            return
        try:
            import win32clipboard
        except ImportError:
            messagebox.showwarning(
                "pywin32 not installed",
                "Install pywin32 to enable clipboard support:\n\n  pip install pywin32",
            )
            return
        rgb = cv2.cvtColor(self.distorted_image, cv2.COLOR_BGR2RGB)
        buf = io.BytesIO()
        Image.fromarray(rgb).save(buf, format="BMP")
        data = buf.getvalue()[14:]  # strip 14-byte BMP file header → CF_DIB
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        win32clipboard.CloseClipboard()
        self.status_var.set("Image copied to clipboard.")

    def save_image(self):
        if self.distorted_image is None:
            return
        path = filedialog.asksaveasfilename(
            title="Save Distorted Image",
            defaultextension=".png",
            filetypes=[
                ("PNG", "*.png"),
                ("JPEG", "*.jpg *.jpeg"),
                ("BMP", "*.bmp"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        if cv2.imwrite(path, self.distorted_image):
            self.status_var.set(f"Saved → {path}")
        else:
            messagebox.showerror("Error", f"Failed to save image to:\n{path}")

    # ── Button state ─────────────────────────────────────────────────────────

    def _sync_buttons(self):
        in_result = self.mode == "result"
        has_four = len(self.points) == 4 and self.mode == "annotating"
        self.btn_distort.config(state=tk.NORMAL if has_four else tk.DISABLED)
        self.btn_restore.config(state=tk.NORMAL if in_result else tk.DISABLED)
        self.btn_copy.config(state=tk.NORMAL if in_result else tk.DISABLED)
        self.btn_save.config(state=tk.NORMAL if in_result else tk.DISABLED)


if __name__ == "__main__":
    root = tk.Tk()
    app = ImageDistorterApp(root)
    root.mainloop()
