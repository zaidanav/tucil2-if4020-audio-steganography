import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import threading

from core.embed import embed_file, CapacityError
from core.extract import extract_file, ExtractError
from core.capacity import compute_capacity_bits_for_file

MAX_KEY_LEN = 25

class StegaGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MP3 Steganography GUI - IF4020 Tucil II")
        self.geometry("880x600")
        self.resizable(True, True)

        nb = ttk.Notebook(self)
        self.embed_tab = ttk.Frame(nb)
        self.extract_tab = ttk.Frame(nb)
        nb.add(self.embed_tab, text="Embed")
        nb.add(self.extract_tab, text="Extract")
        nb.pack(fill=tk.BOTH, expand=True)

        self._build_embed_tab()
        self._build_extract_tab()

    # ---------------- EMBED TAB ----------------
    def _build_embed_tab(self):
        f = self.embed_tab
        pad = {"padx": 8, "pady": 6}

        ttk.Label(f, text="Cover MP3:").grid(row=0, column=0, sticky="w", **pad)
        self.cover_path_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.cover_path_var, width=70).grid(row=0, column=1, **pad)
        ttk.Button(f, text="Browse...", command=self._pick_cover).grid(row=0, column=2, **pad)

        ttk.Label(f, text="Secret file:").grid(row=1, column=0, sticky="w", **pad)
        self.secret_path_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.secret_path_var, width=70).grid(row=1, column=1, **pad)
        ttk.Button(f, text="Browse...", command=self._pick_secret).grid(row=1, column=2, **pad)

        ttk.Label(f, text="Stego output:").grid(row=2, column=0, sticky="w", **pad)
        self.stego_out_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.stego_out_var, width=70).grid(row=2, column=1, **pad)
        ttk.Button(f, text="Save As...", command=self._pick_stego_out).grid(row=2, column=2, **pad)

        ttk.Label(f, text="n-LSB (1..4):").grid(row=3, column=0, sticky="w", **pad)
        self.n_lsb_var = tk.IntVar(value=1)
        ttk.Combobox(f, textvariable=self.n_lsb_var, values=[1,2,3,4], width=5, state="readonly").grid(row=3, column=1, sticky="w", **pad)

        self.encrypt_var = tk.BooleanVar(value=False)
        self.random_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="Encrypt (Extended Vigenère 256)", variable=self.encrypt_var).grid(row=3, column=1, sticky="e", **pad)
        ttk.Checkbutton(f, text="Randomize embedding (seeded by key)", variable=self.random_var).grid(row=3, column=2, sticky="w", **pad)

        ttk.Label(f, text="Key (<= 25 chars):").grid(row=4, column=0, sticky="w", **pad)
        self.key_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.key_var, width=40, show="*").grid(row=4, column=1, sticky="w", **pad)

        btn_frame = ttk.Frame(f); btn_frame.grid(row=5, column=0, columnspan=3, sticky="w", **pad)
        ttk.Button(btn_frame, text="Compute Capacity", command=self._compute_capacity).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Embed", command=self._embed).pack(side=tk.LEFT, padx=5)

        ttk.Label(f, text="Log / Info:").grid(row=6, column=0, sticky="nw", **pad)
        self.embed_log = tk.Text(f, height=12); self.embed_log.grid(row=6, column=1, columnspan=2, sticky="nsew", **pad)
        f.rowconfigure(6, weight=1); f.columnconfigure(1, weight=1)

    def _pick_cover(self):
        p = filedialog.askopenfilename(title="Select cover MP3", filetypes=[("MP3 files", "*.mp3")])
        if p: self.cover_path_var.set(p)

    def _pick_secret(self):
        p = filedialog.askopenfilename(title="Select secret file", filetypes=[("All files", "*.*")])
        if p: self.secret_path_var.set(p)

    def _pick_stego_out(self):
        p = filedialog.asksaveasfilename(title="Save stego MP3 as", defaultextension=".mp3", filetypes=[("MP3 files", "*.mp3")])
        if p: self.stego_out_var.set(p)

    def _append_log(self, txt: str):
        self.embed_log.insert(tk.END, txt + "\n"); self.embed_log.see(tk.END)

    def _compute_capacity(self):
        cover = self.cover_path_var.get().strip()
        if not cover:
            messagebox.showwarning("Missing", "Please choose a cover MP3."); return
        try:
            bits = compute_capacity_bits_for_file(cover)
            self._append_log(f"Capacity: {bits} bits (~{bits//8} bytes)")
        except Exception as e:
            messagebox.showerror("Error", f"Capacity check failed: {e}")

    def _embed(self):
        cover = self.cover_path_var.get().strip()
        secret = self.secret_path_var.get().strip()
        out = self.stego_out_var.get().strip()
        key = self.key_var.get()
        try: n_lsb = int(self.n_lsb_var.get())
        except: n_lsb = 1
        use_enc = bool(self.encrypt_var.get())
        use_rand = bool(self.random_var.get())

        if not cover or not secret or not out:
            messagebox.showwarning("Missing", "Please select cover, secret, and output path."); return
        if len(key) == 0 or len(key) > MAX_KEY_LEN:
            messagebox.showwarning("Key", "Key must be 1..25 characters."); return

        self._append_log("Embedding...")
        def task():
            try:
                from core.embed import embed_file
                psnr = embed_file(cover, secret, out, key, n_lsb, use_enc, use_rand)
                self._append_log(f"Done. Stego saved to: {out}")
                self._append_log("PSNR: (unavailable)" if psnr is None else f"PSNR: {psnr:.2f} dB")
            except CapacityError as ce:
                messagebox.showerror("Capacity", str(ce))
            except Exception as e:
                messagebox.showerror("Error", str(e))
        threading.Thread(target=task, daemon=True).start()

    # ---------------- EXTRACT TAB ----------------
    def _build_extract_tab(self):
        f = self.extract_tab
        pad = {"padx": 8, "pady": 6}

        ttk.Label(f, text="Stego MP3:").grid(row=0, column=0, sticky="w", **pad)
        self.stego_in_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.stego_in_var, width=70).grid(row=0, column=1, **pad)
        ttk.Button(f, text="Browse...", command=self._pick_stego_in).grid(row=0, column=2, **pad)

        ttk.Label(f, text="Key:").grid(row=1, column=0, sticky="w", **pad)
        self.key_extract_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.key_extract_var, width=40, show="*").grid(row=1, column=1, sticky="w", **pad)

        ttk.Label(f, text="Output directory:").grid(row=2, column=0, sticky="w", **pad)
        self.outdir_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.outdir_var, width=70).grid(row=2, column=1, **pad)
        ttk.Button(f, text="Browse...", command=self._pick_outdir).grid(row=2, column=2, **pad)

        ttk.Button(f, text="Extract", command=self._extract).grid(row=3, column=1, sticky="w", **pad)

        ttk.Label(f, text="Log / Info:").grid(row=4, column=0, sticky="nw", **pad)
        self.extract_log = tk.Text(f, height=16)
        self.extract_log.grid(row=4, column=1, columnspan=2, sticky="nsew", **pad)
        f.rowconfigure(4, weight=1); f.columnconfigure(1, weight=1)

    def _pick_stego_in(self):
        p = filedialog.askopenfilename(title="Select stego MP3", filetypes=[("MP3 files", "*.mp3")])
        if p: self.stego_in_var.set(p)

    def _pick_outdir(self):
        p = filedialog.askdirectory(title="Select output directory")
        if p: self.outdir_var.set(p)

    def _append_extract_log(self, txt: str):
        self.extract_log.insert(tk.END, txt + "\n"); self.extract_log.see(tk.END)

    def _extract(self):
        stego = self.stego_in_var.get().strip()
        key = self.key_extract_var.get()
        outdir = self.outdir_var.get().strip()
        if not stego or not outdir:
            messagebox.showwarning("Missing", "Please choose stego MP3 and output directory."); return
        if len(key) == 0 or len(key) > MAX_KEY_LEN:
            messagebox.showwarning("Key", "Key must be 1..25 characters."); return

        self._append_extract_log("Extracting...")
        def task():
            try:
                out_path, flags = extract_file(stego, key, outdir)
                self._append_extract_log(f"Extracted to: {out_path}")
                self._append_extract_log(f"Flags -> encrypted={flags['encrypted']} randomized={flags['randomized']} n_lsb={flags['n_lsb']}")
            except ExtractError as ee:
                messagebox.showerror("Extract", str(ee))
            except Exception as e:
                messagebox.showerror("Error", str(e))
        threading.Thread(target=task, daemon=True).start()

def main():
    app = StegaGUI(); app.mainloop()

if __name__ == "__main__":
    main()
