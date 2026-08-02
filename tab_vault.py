"""
Vault Tab — browse, view, add, edit, and delete stored credentials.
"""
import time
import tkinter as tk
import customtkinter as ctk
from tkinter import ttk, messagebox

from config import C, _font, _mono, font_title, font_label, font_caption, pad, ctk_font_title
from crypto import pw_strength, gen_password
from totp import _totp_valid, _totp_code
from vault_db import vault
from ui_common import EWP, StrengthBar, sep, abtn, gbtn, dbtn, TOTPWidget, copy_to_clipboard


class VaultTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=C["bg"], corner_radius=0)
        self.pack(fill="both", expand=True)
        self._selected    = None
        self._entries     = {}
        self._totp_widget = None
        self._build()
        self.refresh()

    def _build(self):
        top = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        top.pack(fill="x", padx=20, pady=(16, 0))
        ctk.CTkLabel(top, text="Password Vault", fg_color="transparent", text_color=C["white"],
                     font=ctk_font_title()).pack(side="left")
        abtn(top, "+ Add Entry", self._add).pack(side="right")

        sf = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        sf.pack(fill="x", padx=20, pady=10)
        self._search = EWP(sf, placeholder="🔍  Search by title, username or URL…")
        self._search.pack(fill="x", pady=(0, 0))
        self._search.bind("<KeyRelease>", lambda _: self.refresh())

        paned = tk.PanedWindow(self, orient=tk.HORIZONTAL,
                               bg=C["border"], sashwidth=2, relief="flat")
        paned.pack(fill="both", expand=True, padx=20, pady=(0,16))

        lf = ctk.CTkFrame(paned, fg_color=C["surface"], corner_radius=0)
        paned.add(lf, minsize=240)
        self._tree = ttk.Treeview(lf, columns=("t",), show="tree", selectmode="browse")
        self._tree.column("#0", width=0, stretch=False)
        self._tree.column("t",  width=240, stretch=True)
        self._tree.pack(fill="both", expand=True)
        self._tree.bind("<<TreeviewSelect>>", self._on_sel)
        self._tree.bind("<Delete>",           lambda _: self._delete())

        self._detail = ctk.CTkFrame(paned, fg_color=C["bg"], corner_radius=0)
        paned.add(self._detail, minsize=420)
        self._placeholder()

    def _placeholder(self):
        for w in self._detail.winfo_children(): w.destroy()
        tk.Label(self._detail, text="Select an entry to view details",
                 bg=C["bg"], fg=C["subtext"], font=_font(12)
                 ).place(relx=0.5, rely=0.5, anchor="center")

    def refresh(self):
        q = self._search.val().lower()
        for r in self._tree.get_children(): self._tree.delete(r)
        self._entries = vault.all_entries()
        for eid, e in self._entries.items():
            if q and not any(q in (e.get(k,"") or "").lower()
                             for k in ("title","username","url")):
                continue
            icon = "🔐  " if e.get("totp_secret") else "🔑  "
            self._tree.insert("", "end", iid=eid, values=(icon + e["title"],))

    def _on_sel(self, _=None):
        sel = self._tree.selection()
        if sel:
            self._selected = sel[0]
            self._show(self._selected)

    def _show(self, eid):
        e = self._entries.get(eid)
        if not e: return
        # Stop any running TOTP ticker from previous detail view
        if hasattr(self, "_totp_widget") and self._totp_widget:
            try: self._totp_widget.stop()
            except Exception: pass
            self._totp_widget = None
        for w in self._detail.winfo_children():
            w.destroy()
        d = ctk.CTkFrame(self._detail, fg_color=C["bg"], corner_radius=0)
        d.pack(fill="both", expand=True, padx=20, pady=20)

        tk.Label(d, text=e["title"], bg=C["bg"], fg=C["white"],
                 font=_font(18,"bold")).pack(anchor="w")
        if e.get("url"):
            tk.Label(d, text=e["url"], bg=C["bg"], fg=C["subtext"],
                     font=_font(10)).pack(anchor="w", pady=(2,0))
        sep(d, pady=12)

        for label, value, mono in [("Username", e.get("username",""), False),
                                    ("Password", e.get("password",""), True)]:
            row = ctk.CTkFrame(d, fg_color=C["bg"], corner_radius=0)
            row.pack(fill="x", pady=6)
            tk.Label(row, text=label, bg=C["bg"], fg=C["subtext"],
                     font=_font(10)).pack(anchor="w")
            vr = ctk.CTkFrame(row, fg_color=C["bg"], corner_radius=0)
            vr.pack(fill="x")
            var = tk.StringVar(value="••••••••" if mono else value)
            fnt = _mono(12) if mono else _font(12)
            tk.Label(vr, textvariable=var, bg=C["bg"], fg=C["text"],
                     font=fnt).pack(side="left")
            if mono:
                sc, lbl, col = pw_strength(value)
                tk.Label(vr, text=f"  {lbl}", bg=C["bg"],
                         fg=col, font=_font(9,"bold")).pack(side="left", padx=8)
            def mk_toggle(v, val, is_pw):
                def t(): v.set(val if v.get().startswith("•") else ("••••••••" if is_pw else val))
                return t
            def mk_copy(val):
                def cp(): copy_to_clipboard(self, val)
                return cp
            gbtn(vr, "👁", mk_toggle(var, value, mono)).pack(side="left", padx=(8,4))
            gbtn(vr, "Copy", mk_copy(value)).pack(side="left")

        if e.get("notes"):
            sep(d, pady=10)
            tk.Label(d, text="Notes", bg=C["bg"], fg=C["subtext"],
                     font=_font(10)).pack(anchor="w")
            tk.Label(d, text=e["notes"], bg=C["bg"], fg=C["text"],
                     font=_font(11), wraplength=400, justify="left").pack(anchor="w", pady=(4,0))

        # ── TOTP section ──
        totp_secret = e.get("totp_secret", "")
        if totp_secret:
            sep(d, pady=10)
            tk.Label(d, text="Two-Factor Code (TOTP)", bg=C["bg"],
                     fg=C["subtext"], font=_font(10)).pack(anchor="w")
            self._totp_widget = TOTPWidget(d, totp_secret)
            self._totp_widget.pack(anchor="w", pady=(6, 0))
        else:
            self._totp_widget = None

        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(e.get("created",0)))
        tk.Label(d, text=f"Added: {ts}", bg=C["bg"], fg=C["subtext"],
                 font=_font(9)).pack(anchor="w", pady=(8,0))

        sep(d, pady=14)
        br = ctk.CTkFrame(d, fg_color=C["bg"], corner_radius=0)
        br.pack(anchor="w")
        gbtn(br, "✏️  Edit",   lambda: self._edit(eid)).pack(side="left", padx=(0,8))
        dbtn(br, "🗑  Delete", lambda: self._delete(eid)).pack(side="left")

    def _add(self):
        EntryDialog(self.winfo_toplevel(), "Add Entry",
                    lambda d: (vault.add_entry(**d), self.refresh()))

    def _edit(self, eid):
        e = self._entries.get(eid,{})
        def save(d):
            vault.update_entry(eid, **d)
            self.refresh(); self._entries = vault.all_entries(); self._show(eid)
        EntryDialog(self.winfo_toplevel(), "Edit Entry", save, existing=e)

    def _delete(self, eid=None):
        eid = eid or self._selected
        if not eid: return
        title = self._entries.get(eid,{}).get("title","this entry")
        if messagebox.askyesno("Delete", f"Delete '{title}'? Cannot be undone."):
            vault.delete_entry(eid); self._selected = None
            self.refresh(); self._placeholder()

# ─────────────────────────── Entry Dialog ───────────────────────────

class EntryDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, callback, existing=None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self._cb = callback
        self._ex = existing or {}
        self._build()
        self.geometry("530x640")
        self.update_idletasks()
        px, py = parent.winfo_x(), parent.winfo_y()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        self.geometry(f"+{px + pw // 2 - 265}+{py + ph // 2 - 280}")

    def _build(self):
        p = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        p.pack(fill="both", expand=True, padx=28, pady=24)
        p.columnconfigure(1, weight=1)
        ctk.CTkLabel(p, text="Entry Details", fg_color="transparent", text_color=C["white"],
                     font=_font(14, "bold")).grid(row=0, columnspan=2, sticky="w", pady=(0, 14))

        def fld(label, row, show="", default=""):
            ctk.CTkLabel(p, text=label, fg_color="transparent", text_color=C["subtext"],
                         font=_font(10)).grid(row=row, column=0, sticky="w", pady=4)
            e = EWP(p, placeholder=label, show_char=show)
            e.grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=4)
            if default:
                e.set_val(default)
            return e

        self._title = fld("Title", 1, default=self._ex.get("title", ""))
        self._user = fld("Username", 2, default=self._ex.get("username", ""))

        ctk.CTkLabel(p, text="Password", fg_color="transparent", text_color=C["subtext"],
                     font=_font(10)).grid(row=3, column=0, sticky="w", pady=4)
        pc = ctk.CTkFrame(p, fg_color=C["bg"], corner_radius=0)
        pc.grid(row=3, column=1, sticky="ew", padx=(12, 0), pady=4)
        self._pw = EWP(pc, placeholder="Password", show_char="•")
        self._pw.pack(fill="x")
        if self._ex.get("password"):
            self._pw.set_val(self._ex["password"])
        self._sbar = StrengthBar(pc)
        self._sbar.pack(fill="x", pady=(4, 0))
        self._slbl = ctk.CTkLabel(pc, text="", fg_color="transparent",
                                  text_color=C["subtext"], font=_font(9))
        self._slbl.pack(anchor="w")
        self._pw.bind("<KeyRelease>", self._upd_str)
        gbtn(pc, "⚡ Generate strong password", self._gen_pw).pack(anchor="w", pady=(6, 0))
        if self._ex.get("password"):
            self._upd_str()

        self._url = fld("URL", 5, default=self._ex.get("url", ""))
        self._notes = fld("Notes", 6, default=self._ex.get("notes", ""))

        ctk.CTkLabel(p, text="2FA Secret", fg_color="transparent", text_color=C["subtext"],
                     font=_font(10)).grid(row=7, column=0, sticky="w", pady=4)
        totp_col = ctk.CTkFrame(p, fg_color=C["bg"], corner_radius=0)
        totp_col.grid(row=7, column=1, sticky="ew", padx=(12, 0), pady=4)
        self._totp = EWP(totp_col, placeholder="TOTP secret key (e.g. JBSWY3DPEHPK3PXP)")
        self._totp.pack(fill="x")
        if self._ex.get("totp_secret"):
            self._totp.set_val(self._ex["totp_secret"])
        self._totp_status = ctk.CTkLabel(totp_col, text="", fg_color="transparent",
                                         text_color=C["subtext"], font=_font(9))
        self._totp_status.pack(anchor="w", pady=(2, 0))
        ctk.CTkLabel(
            totp_col,
            text="Paste the secret key from the 2FA setup page. Leave blank if no 2FA.",
            fg_color="transparent", text_color=C["subtext"], font=_font(8),
            justify="left",
        ).pack(anchor="w")
        self._totp.bind("<KeyRelease>", self._validate_totp)
        if self._ex.get("totp_secret"):
            self._validate_totp()

        ctk.CTkFrame(p, fg_color=C["border"], height=1, corner_radius=0).grid(
            row=8, columnspan=2, sticky="ew", pady=14)
        br = ctk.CTkFrame(p, fg_color=C["bg"], corner_radius=0)
        br.grid(row=9, columnspan=2, sticky="ew")
        abtn(br, "Save", self._save).pack(side="right", padx=(8, 0))
        gbtn(br, "Cancel", self.destroy).pack(side="right")

    def _upd_str(self, _=None):
        sc, lbl, col = pw_strength(self._pw.val())
        self._sbar.set_score(sc, col)
        self._slbl.configure(text=lbl if self._pw.val() else "", text_color=col)

    def _gen_pw(self):
        self._pw.set_val(gen_password(20)); self._upd_str()

    def _validate_totp(self, _=None):
        secret = self._totp.val().strip()
        if not secret:
            self._totp_status.configure(text="")
            return
        if _totp_valid(secret):
            code, remaining, _ = _totp_code(secret)
            self._totp_status.configure(
                text=f"✅ Valid — current code: {code[:3]} {code[3:]}  ({remaining}s)",
                text_color=C["success"])
        else:
            self._totp_status.configure(
                text="❌ Invalid secret — must be base32 (A-Z, 2-7), min 16 chars",
                text_color=C["danger"])

    def _save(self):
        t, pw = self._title.val(), self._pw.val()
        if not t or not pw:
            messagebox.showwarning("Missing", "Title and Password required.", parent=self); return
        totp_secret = self._totp.val().strip().upper()
        if totp_secret and not _totp_valid(totp_secret):
            messagebox.showwarning("Invalid 2FA Secret",
                "The TOTP secret key is not valid base32. Copy it exactly from the website 2FA setup page.", parent=self)
            return
        self._cb(dict(title=t, username=self._user.val(), password=pw,
                      url=self._url.val(), notes=self._notes.val(),
                      totp_secret=totp_secret))
        self.destroy()
