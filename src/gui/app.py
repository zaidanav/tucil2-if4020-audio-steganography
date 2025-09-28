import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from pathlib import Path
import threading

from stego.player import AudioPlayer
from stego.pipeline import (
    analyze_cover_file,
    compute_capacity_for_file,
    embed_to_file,
    extract_to_file,
)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Tucil II - Audio Steganography  ")
        self.geometry("980x720")
        # players
        self.player_cover = AudioPlayer()
        self.player_stego = AudioPlayer()
        # ui state vars
        self.cover_var = tk.StringVar()
        self.secret_var = tk.StringVar()
        self.out_var = tk.StringVar()
        self.n_var = tk.IntVar(value=2)
        self.key_var = tk.StringVar()
        self.enc_var = tk.BooleanVar(value=False)
        self.rnd_var = tk.BooleanVar(value=False)

        self.instego_var = tk.StringVar()
        self.outdir_var = tk.StringVar()
        self.key2_var = tk.StringVar()

        self._build()

    # Style & Header
    def _setup_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("Sub.TLabel", font=("Segoe UI", 10))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("Card.TFrame", padding=10)
        style.map("Accent.TButton",
                  foreground=[("active", "#000")],
                  background=[("!disabled", "#A7F3D0"), ("active", "#6EE7B7")])

    # UI BUILD
    def _build(self):
        self._setup_style()

        # Header
        header = ttk.Frame(self, style="Card.TFrame")
        header.pack(fill="x", padx=8, pady=(8, 0))
        ttk.Label(header, text="Audio Steganography", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="Embed secret in audio data samples", style="Sub.TLabel").pack(side="left", padx=12)

        nb = ttk.Notebook(self)
        nb.pack(fill="x", expand=False, padx=8, pady=(4,6))

        f1 = ttk.Frame(nb, style="Card.TFrame"); nb.add(f1, text="Embed")
        f2 = ttk.Frame(nb, style="Card.TFrame"); nb.add(f2, text="Extract")

        self._build_embed(f1)
        self._build_extract(f2)

        # log
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=8, pady=(2,4))
        self.log = ScrolledText(self, height=20, font=("Consolas", 10), wrap="word")
        self.log.pack(fill="both", expand=True, padx=8, pady=(0,6))

    def _build_embed(self, root):
        pad = dict(padx=6, pady=4, sticky="w")
        f = root

        # cover + play
        ttk.Label(f, text="Cover:").grid(row=0, column=0, **pad)
        ttk.Entry(f, textvariable=self.cover_var, width=60).grid(row=0, column=1, **pad)
        ttk.Button(f, text="Browse...", command=self._pick_cover).grid(row=0, column=2, **pad)
        ttk.Button(f, text="▶ Play", command=self._play_cover).grid(row=0, column=3, **pad)
        ttk.Button(f, text="■ Stop", command=self._stop_cover).grid(row=0, column=4, **pad)

        # secret
        ttk.Label(f, text="Secret file:").grid(row=1, column=0, **pad)
        ttk.Entry(f, textvariable=self.secret_var, width=60).grid(row=1, column=1, **pad)
        ttk.Button(f, text="Browse...", command=self._pick_secret).grid(row=1, column=2, **pad)

        # output
        ttk.Label(f, text="Stego output:").grid(row=2, column=0, **pad)
        ttk.Entry(f, textvariable=self.out_var, width=60).grid(row=2, column=1, **pad)
        ttk.Button(f, text="Save As...", command=self._pick_out).grid(row=2, column=2, **pad)

        # params
        frm = ttk.Frame(f); frm.grid(row=3, column=0, columnspan=5, sticky="w", padx=6, pady=4)
        ttk.Label(frm, text="n-LSB:").grid(row=0, column=0, padx=6, pady=4)
        ttk.Spinbox(frm, from_=1, to=4, width=5, textvariable=self.n_var).grid(row=0, column=1, padx=4, pady=4)
        ttk.Checkbutton(frm, text="Encrypt (Vigenère-256)", variable=self.enc_var).grid(row=0, column=2, padx=8)
        ttk.Checkbutton(frm, text="Random start by key", variable=self.rnd_var).grid(row=0, column=3, padx=8)
        ttk.Label(frm, text="Key:").grid(row=0, column=4, padx=8)
        ttk.Entry(frm, textvariable=self.key_var, width=30).grid(row=0, column=5, padx=4)

        # actions
        ttk.Button(f, text="Analyze Cover", command=self._analyze).grid(row=4, column=0, **pad)
        ttk.Button(f, text="Compute Capacity", command=self._capacity).grid(row=4, column=1, **pad)
        self.btn_embed = ttk.Button(f, text="Embed", command=self._embed, style="Accent.TButton")
        self.btn_embed.grid(row=4, column=2, **pad)

        for i in range(6):
            f.grid_columnconfigure(i, weight=0)
        f.grid_columnconfigure(1, weight=1) 

    def _build_extract(self, root):
        pad = dict(padx=6, pady=4, sticky="w")
        f = root

        # stego + play
        ttk.Label(f, text="Stego Audio:").grid(row=0, column=0, **pad)
        ttk.Entry(f, textvariable=self.instego_var, width=60).grid(row=0, column=1, **pad)
        ttk.Button(f, text="Browse...", command=self._pick_stego).grid(row=0, column=2, **pad)
        ttk.Button(f, text="▶ Play", command=self._play_stego).grid(row=0, column=3, **pad)
        ttk.Button(f, text="■ Stop", command=self._stop_stego).grid(row=0, column=4, **pad)

        # outdir
        ttk.Label(f, text="Output folder:").grid(row=1, column=0, **pad)
        ttk.Entry(f, textvariable=self.outdir_var, width=60).grid(row=1, column=1, **pad)
        ttk.Button(f, text="Browse...", command=self._pick_outdir).grid(row=1, column=2, **pad)

        # key
        ttk.Label(f, text="Key:").grid(row=2, column=0, **pad)
        ttk.Entry(f, textvariable=self.key2_var, width=30).grid(row=2, column=1, **pad)

        # action
        self.btn_extract = ttk.Button(f, text="Extract", command=self._extract, style="Accent.TButton")
        self.btn_extract.grid(row=3, column=0, **pad)

        for i in range(6):
            f.grid_columnconfigure(i, weight=0)
        f.grid_columnconfigure(1, weight=1)

    # File pickers
    def _pick_cover(self):
        fn = filedialog.askopenfilename(title="Pick cover audio", filetypes=[("Audio","*.wav *.mp3"),("WAV","*.wav"),("MP3","*.mp3"),("All files","*.*")])
        if fn: self.cover_var.set(fn)

    def _pick_secret(self):
        fn = filedialog.askopenfilename(title="Pick secret file", filetypes=[("All files","*.*")])
        if fn: self.secret_var.set(fn)

    def _pick_out(self):
        fn = filedialog.asksaveasfilename(title="Save stego WAV as", defaultextension=".wav", filetypes=[("WAV files","*.wav"),("All files","*.*")])
        if fn: self.out_var.set(fn)

    def _pick_stego(self):
        fn = filedialog.askopenfilename(title="Pick stego", filetypes=[("WAV files","*.wav"),("All files","*.*")])
        if fn: self.instego_var.set(fn)

    def _pick_outdir(self):
        dn = filedialog.askdirectory(title="Pick output folder")
        if dn: self.outdir_var.set(dn)

    # Logging
    def _log(self, msg: str):
        self.log.insert("end", msg + "\n")
        self.log.see("end")

    def _log_e(self, msg: str):
        self._log(msg)

    # Actions
    def _analyze(self):
        cover = self.cover_var.get().strip()
        if not cover:
            messagebox.showwarning("Missing", "Please choose a cover audio (MP3/WAV)."); return
        def task():
            try:
                info = analyze_cover_file(cover)
                self.after(0, lambda: self._log_e(
                    f"Analyze OK — channels={info['channels']} stereo={info.get('stereo', info['channels']==2)} "
                    f"sr={info['samplerate']}Hz sample_width={info['sample_width']} "
                    f"total_frames={info.get('total_frames','?')} total_samples={info['total_samples']} "
                    f"duration={info['duration_sec']:.2f}s"
                ))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Analyze", str(e)))
        threading.Thread(target=task, daemon=True).start()

    def _capacity(self):
        cover = self.cover_var.get().strip()
        n = self.n_var.get()
        if not cover:
            messagebox.showwarning("Missing", "Please choose a cover audio (MP3)."); return
        def task():
            try:
                cap = compute_capacity_for_file(cover, n)
                self.after(0, lambda: self._log_e(f"Capacity (PCM samples, n={n}) = {cap} bits ({cap//8} bytes)"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Capacity", str(e)))
        threading.Thread(target=task, daemon=True).start()

    def _set_enabled(self, enabled: bool):
        try:
            self.btn_embed.configure(state=("normal" if enabled else "disabled"))
        except Exception:
            pass
        try:
            self.btn_extract.configure(state=("normal" if enabled else "disabled"))
        except Exception:
            pass

    def _embed(self):
        cover = self.cover_var.get().strip()
        secret = self.secret_var.get().strip()
        out = self.out_var.get().strip()
        n = self.n_var.get()
        key = self.key_var.get()
        enc = self.enc_var.get()
        rnd = self.rnd_var.get()

        if not cover or not secret or not out:
            messagebox.showwarning("Missing", "Lengkapi cover, secret, dan output."); return

        def task():
            self.after(0, lambda: self._set_enabled(False))
            try:
                self.after(0, lambda: self._log("Embedding..."))
                psnr = embed_to_file(cover, secret, out, key, n, enc, rnd, compute_psnr=True)
                self.after(0, lambda: self._log_e(f"Done. Stego Audio saved to: {out if out.lower().endswith('.wav') else out + '.wav'}"))
                if psnr is not None:
                    self.after(0, lambda: self._log_e(f"PSNR: {psnr:.2f} dB"))
                self.after(0, lambda: messagebox.showinfo("Embed", "Selesai. Stego audio telah disimpan. Gunakan file hasil embed ini untuk proses Extract."))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Embed", str(e)))
            finally:
                self.after(0, lambda: self._set_enabled(True))
        threading.Thread(target=task, daemon=True).start()

    def _extract(self):
        stego = self.instego_var.get().strip()
        outdir = self.outdir_var.get().strip()
        key = self.key2_var.get()
        if not stego or not outdir:
            messagebox.showwarning("Missing", "Pilih stego audio dan output folder."); return
        def task():
            self.after(0, lambda: self._set_enabled(False))
            try:
                self.after(0, lambda: self._log("Extracting..."))
                op, flags = extract_to_file(stego, key, outdir)
                self.after(0, lambda: self._log_e(f"Extract OK → {op} (flags={flags})"))
                self.after(0, lambda: messagebox.showinfo("Extract", f"Berhasil! File tersimpan di:\n{op}"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Extract", str(e)))
            finally:
                self.after(0, lambda: self._set_enabled(True))
        threading.Thread(target=task, daemon=True).start()

    # Audio preview
    def _play_cover(self):
        path = self.cover_var.get().strip()
        if not path:
            messagebox.showwarning("Play", "Pilih cover audio dulu."); return
        def task():
            try:
                self.player_cover.play(path)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Play cover", str(e)))
        threading.Thread(target=task, daemon=True).start()

    def _stop_cover(self):
        try:
            self.player_cover.stop()
        except Exception:
            pass

    def _play_stego(self):
        path = self.instego_var.get().strip()
        if not path:
            messagebox.showwarning("Play", "Pilih stego audio dulu."); return
        def task():
            try:
                self.player_stego.play(path)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Play stego", str(e)))
        threading.Thread(target=task, daemon=True).start()

    def _stop_stego(self):
        try:
            self.player_stego.stop()
        except Exception:
            pass

def main():
    App().mainloop()

if __name__ == "__main__":
    main()
