"""
Vault tab — search, browse, view, add, edit, and delete credentials.
Plaintext lives only in the unlocked session cache.
"""
import time
import webbrowser
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox

from config import C, _font, _mono, pad, ctk_font_title, ctk_font_body, ctk_font_label, ctk_font_caption
from crypto import pw_strength, gen_password
from totp import _totp_valid, _totp_code
from vault_db import vault
from ui_common import EWP, SecretEntry, StrengthBar, sep, abtn, gbtn, dbtn, TOTPWidget, copy_to_clipboard


def _safe_url(url: str) -> bool:
    u = (url or "").strip().lower()
    return u.startswith("https://") or u.startswith("http://")


class VaultTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=C["bg"], corner_radius=0)
        self.pack(fill="both", expand=True)
        self._selected = None
        self._entries = {}
        self._totp_widget = None
        self._search_after = None
        self._build()
        self.refresh()

    def focus_search(self):
        self._search.focus_set()

    def open_new_entry(self):
        self._add()

    def _build(self):
        top = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        top.pack(fill="x", padx=20, pady=(16, 0))
        ctk.CTkLabel(top, text="Password vault", fg_color="transparent", text_color=C["text"],
                     font=ctk_font_title()).pack(side="left")
        abtn(top, "Add entry", self._add).pack(side="right")

        sf = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        sf.pack(fill="x", padx=20, pady=10)
        self._search = EWP(sf, placeholder="Search title, username, URL, or notes")
        self._search.pack(fill="x")
        self._search.bind("<KeyRelease>", self._schedule_search)

        body = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        body.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        body.grid_columnconfigure(0, weight=2, minsize=260)
        body.grid_columnconfigure(1, weight=3, minsize=360)
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body, fg_color=C["surface"], corner_radius=pad(10),
                            border_width=1, border_color=C["border"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._list = ctk.CTkScrollableFrame(left, fg_color=C["surface"], corner_radius=0)
        self._list.pack(fill="both", expand=True, padx=4, pady=4)
        self._list.bind("<Delete>", self._on_delete_key)

        self._detail = ctk.CTkFrame(body, fg_color=C["bg"], corner_radius=0)
        self._detail.grid(row=0, column=1, sticky="nsew")
        self._placeholder("Select an entry to view details")

    def _schedule_search(self, _event=None):
        if self._search_after is not None:
            try:
                self.after_cancel(self._search_after)
            except Exception:
                pass
        self._search_after = self.after(140, self.refresh)

    def _placeholder(self, text):
        self._stop_totp()
        for w in self._detail.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._detail, text=text, fg_color="transparent",
                     text_color=C["subtext"], font=ctk_font_body()
                     ).place(relx=0.5, rely=0.5, anchor="center")

    def _stop_totp(self):
        if self._totp_widget is not None:
            try:
                self._totp_widget.stop()
            except Exception:
                pass
            self._totp_widget = None

    def refresh(self):
        self._search_after = None
        q = self._search.val().lower().strip()
        self._entries = vault.all_entries()
        for w in self._list.winfo_children():
            w.destroy()
        shown = []
        for eid, e in self._entries.items():
            if e.get("decrypt_error") and not e.get("title"):
                hay = "could not decrypt"
            else:
                hay = " ".join(
                    e.get(k, "") or "" for k in ("title", "username", "url", "notes")
                ).lower()
            if q and q not in hay:
                continue
            shown.append(eid)
            self._add_row(eid, e)
        if not shown:
            msg = "No matching entries" if q else "No entries yet"
            ctk.CTkLabel(self._list, text=msg, fg_color="transparent",
                         text_color=C["subtext"], font=ctk_font_body()
                         ).pack(anchor="w", padx=12, pady=16)
            if self._selected not in shown:
                self._selected = None
                self._placeholder(msg)
            return
        if self._selected not in shown:
            self._selected = None
            self._placeholder("Select an entry to view details")

    def _add_row(self, eid, e):
        selected = eid == self._selected
        row = ctk.CTkFrame(
            self._list,
            fg_color=C["primary_soft"] if selected else C["surface"],
            corner_radius=pad(8),
        )
        row.pack(fill="x", padx=4, pady=2)
        if selected:
            ctk.CTkFrame(row, width=3, fg_color=C["primary"], corner_radius=0).pack(side="left", fill="y")
        title = e.get("title") or "(untitled)"
        if e.get("decrypt_error"):
            title = title or "Could not decrypt"
        user = e.get("username") or "No username"
        mark = "2FA" if e.get("totp_secret") else ""
        head = ctk.CTkFrame(row, fg_color="transparent")
        head.pack(fill="x", padx=10, pady=(6, 0))
        ctk.CTkLabel(head, text=title, fg_color="transparent", text_color=C["text"],
                     font=ctk_font_body("bold"), anchor="w").pack(side="left")
        if mark:
            ctk.CTkLabel(head, text=mark, fg_color="transparent", text_color=C["primary"],
                         font=ctk_font_caption("bold")).pack(side="right")
        ctk.CTkLabel(row, text=user, fg_color="transparent", text_color=C["subtext"],
                     font=ctk_font_caption(), anchor="w").pack(fill="x", padx=10, pady=(0, 6))

        def _select(_event=None, i=eid):
            # Defer so the clicked row is not destroyed inside its own event.
            self.after_idle(lambda: self._select(i))

        for w in (row, head, *head.winfo_children(), *row.winfo_children()):
            w.bind("<Button-1>", _select)
        row.bind("<Delete>", self._on_delete_key)

    def _select(self, eid):
        self._selected = eid
        self.refresh()
        self._show(eid)

    def _on_delete_key(self, event=None):
        widget = event.widget if event is not None else None
        if widget is not None and widget.winfo_class() in ("Entry", "Text", "TEntry"):
            return
        self._delete()
        return "break"

    def _notify(self):
        self.refresh()
        root = self.winfo_toplevel()
        if hasattr(root, "refresh_status"):
            root.refresh_status()

    def _show(self, eid):
        e = self._entries.get(eid)
        if not e:
            return
        self._stop_totp()
        for w in self._detail.winfo_children():
            w.destroy()
        scroll = ctk.CTkScrollableFrame(self._detail, fg_color=C["bg"], corner_radius=0)
        scroll.pack(fill="both", expand=True)
        scroll.bind("<Delete>", self._on_delete_key)

        ctk.CTkLabel(scroll, text=e.get("title") or "(untitled)", fg_color="transparent",
                     text_color=C["text"], font=_font(18, "bold"), anchor="w",
                     justify="left", wraplength=480).pack(anchor="w", fill="x")
        if e.get("decrypt_error"):
            ctk.CTkLabel(
                scroll, text="Part of this entry could not be decrypted.",
                fg_color="transparent", text_color=C["danger"], font=ctk_font_caption(),
            ).pack(anchor="w", pady=(4, 0))
        if e.get("url"):
            url = e["url"]
            if _safe_url(url):
                link = ctk.CTkButton(
                    scroll, text=url, anchor="w", fg_color="transparent",
                    text_color=C["accent"], hover_color=C["accent_soft"],
                    font=ctk_font_caption(), command=lambda u=url: webbrowser.open(u),
                )
                link.pack(anchor="w", pady=(2, 0))
            else:
                ctk.CTkLabel(scroll, text=url, fg_color="transparent", text_color=C["subtext"],
                             font=ctk_font_caption(), anchor="w", justify="left",
                             wraplength=480).pack(anchor="w", pady=(2, 0))
        sep(scroll, pady=12)

        self._secret_row(scroll, "Username", e.get("username", ""), secret=False)
        self._secret_row(scroll, "Password", e.get("password", ""), secret=True,
                         disabled=bool(e.get("decrypt_error") and not e.get("password")))

        if e.get("notes"):
            sep(scroll, pady=10)
            ctk.CTkLabel(scroll, text="Notes", fg_color="transparent", text_color=C["subtext"],
                         font=ctk_font_label()).pack(anchor="w")
            notes = ctk.CTkLabel(
                scroll, text=e["notes"], fg_color="transparent", text_color=C["text"],
                font=_font(11), wraplength=480, justify="left", anchor="w",
            )
            notes.pack(anchor="w", fill="x", pady=(4, 0))

            def _fit(event, lbl=notes):
                lbl.configure(wraplength=max(220, event.width - 24))

            scroll.bind("<Configure>", _fit, add="+")

        totp_secret = e.get("totp_secret", "")
        if totp_secret:
            sep(scroll, pady=10)
            ctk.CTkLabel(scroll, text="Two-factor code", fg_color="transparent",
                         text_color=C["subtext"], font=ctk_font_label()).pack(anchor="w")
            self._totp_widget = TOTPWidget(scroll, totp_secret)
            self._totp_widget.pack(anchor="w", pady=(6, 0))

        created = time.strftime("%Y-%m-%d %H:%M", time.localtime(e.get("created") or 0))
        updated = e.get("updated") or e.get("created") or 0
        updated_s = time.strftime("%Y-%m-%d %H:%M", time.localtime(updated))
        ctk.CTkLabel(
            scroll, text=f"Added {created}   ·   Updated {updated_s}",
            fg_color="transparent", text_color=C["subtext"], font=_font(9),
        ).pack(anchor="w", pady=(8, 0))

        sep(scroll, pady=14)
        br = ctk.CTkFrame(scroll, fg_color="transparent")
        br.pack(anchor="w")
        gbtn(br, "Edit", lambda: self._edit(eid)).pack(side="left", padx=(0, 8))
        dbtn(br, "Delete", lambda: self._delete(eid)).pack(side="left")

    def _secret_row(self, parent, label, value, secret=False, disabled=False):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=6)
        ctk.CTkLabel(row, text=label, fg_color="transparent", text_color=C["subtext"],
                     font=ctk_font_label()).pack(anchor="w")
        line = ctk.CTkFrame(row, fg_color="transparent")
        line.pack(fill="x")
        shown = {"on": not secret}
        var = tk.StringVar(value="••••••••" if secret else value)
        ctk.CTkLabel(
            line, textvariable=var, fg_color="transparent", text_color=C["text"],
            font=_mono(12) if secret else _font(12), anchor="w",
        ).pack(side="left")
        if secret and value:
            sc, lbl, col = pw_strength(value)
            ctk.CTkLabel(line, text=f"  {lbl}", fg_color="transparent",
                         text_color=col, font=_font(9, "bold")).pack(side="left", padx=8)

            def toggle(v=var, val=value, state=shown):
                state["on"] = not state["on"]
                v.set(val if state["on"] else "••••••••")
                btn.configure(text="Hide" if state["on"] else "Show")

            btn = gbtn(line, "Show", toggle)
            btn.pack(side="left", padx=(8, 4))
        if not disabled:
            copy_btn = gbtn(line, "Copy", lambda: None)
            copy_btn.configure(command=lambda b=copy_btn, val=value: copy_to_clipboard(self, val, button=b))
            copy_btn.pack(side="left")

    def _add(self):
        def save(d):
            vault.add_entry(**d)
            self._notify()
        EntryDialog(self.winfo_toplevel(), "Add entry", save)

    def _edit(self, eid):
        e = self._entries.get(eid, {})
        def save(d):
            vault.update_entry(eid, **d)
            self._selected = eid
            self._notify()
            self._show(eid)
        EntryDialog(self.winfo_toplevel(), "Edit entry", save, existing=e)

    def _delete(self, eid=None):
        eid = eid or self._selected
        if not eid:
            return
        title = self._entries.get(eid, {}).get("title", "this entry")
        if messagebox.askyesno("Delete", f"Delete '{title}'? This cannot be undone."):
            vault.delete_entry(eid)
            self._selected = None
            self._notify()
            self._placeholder("Select an entry to view details")


class EntryDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, callback, existing=None):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.grab_set()
        self._cb = callback
        self._ex = existing or {}
        self.configure(fg_color=C["bg"])
        sh = max(640, parent.winfo_screenheight() - 120)
        h = min(760, sh)
        self.geometry(f"560x{h}")
        self.minsize(480, 520)
        self._build()
        self.update_idletasks()
        px, py = parent.winfo_x(), parent.winfo_y()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        self.geometry(f"+{px + max(0, pw // 2 - 280)}+{py + max(0, ph // 2 - h // 2)}")

    def _build(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color=C["bg"], corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=8, pady=8)
        p = scroll
        ctk.CTkLabel(p, text="Entry details", fg_color="transparent", text_color=C["text"],
                     font=_font(14, "bold")).pack(anchor="w", pady=(8, 12))

        def labeled_entry(label, default="", secret=False):
            ctk.CTkLabel(p, text=label, fg_color="transparent", text_color=C["subtext"],
                         font=_font(10)).pack(anchor="w", pady=(8, 2))
            if secret:
                e = SecretEntry(p, placeholder=label)
            else:
                e = EWP(p, placeholder=label)
            e.pack(fill="x")
            if default:
                e.set_val(default)
            return e

        self._title = labeled_entry("Title", self._ex.get("title", ""))
        self._user = labeled_entry("Username", self._ex.get("username", ""))

        ctk.CTkLabel(p, text="Password", fg_color="transparent", text_color=C["subtext"],
                     font=_font(10)).pack(anchor="w", pady=(8, 2))
        self._pw = SecretEntry(p, placeholder="Password")
        self._pw.pack(fill="x")
        if self._ex.get("password"):
            self._pw.set_val(self._ex["password"])
        self._sbar = StrengthBar(p)
        self._sbar.pack(fill="x", pady=(4, 0))
        self._slbl = ctk.CTkLabel(p, text="", fg_color="transparent",
                                  text_color=C["subtext"], font=_font(9))
        self._slbl.pack(anchor="w")
        self._pw.bind("<KeyRelease>", self._upd_str)
        gbtn(p, "Generate strong password", self._gen_pw).pack(anchor="w", pady=(6, 0))
        if self._ex.get("password"):
            self._upd_str()

        self._url = labeled_entry("URL", self._ex.get("url", ""))

        ctk.CTkLabel(p, text="Notes", fg_color="transparent", text_color=C["subtext"],
                     font=_font(10)).pack(anchor="w", pady=(8, 2))
        self._notes = ctk.CTkTextbox(
            p, height=90, fg_color=C["input_bg"], text_color=C["input_fg"],
            border_color=C["border"], border_width=1, corner_radius=pad(8),
            font=ctk_font_body(),
        )
        self._notes.pack(fill="x")
        self._notes.bind("<FocusIn>", lambda _e: self._notes.configure(border_color=C["ring"]), add="+")
        self._notes.bind("<FocusOut>", lambda _e: self._notes.configure(border_color=C["border"]), add="+")
        if self._ex.get("notes"):
            self._notes.insert("1.0", self._ex["notes"])

        ctk.CTkLabel(p, text="2FA secret", fg_color="transparent", text_color=C["subtext"],
                     font=_font(10)).pack(anchor="w", pady=(8, 2))
        self._totp = SecretEntry(p, placeholder="TOTP secret (base32)")
        self._totp.pack(fill="x")
        if self._ex.get("totp_secret"):
            self._totp.set_val(self._ex["totp_secret"])
        self._totp_status = ctk.CTkLabel(p, text="", fg_color="transparent",
                                         text_color=C["subtext"], font=_font(9))
        self._totp_status.pack(anchor="w", pady=(2, 0))
        ctk.CTkLabel(
            p, text="Paste the secret from the site's 2FA setup. Leave blank if there is none.",
            fg_color="transparent", text_color=C["subtext"], font=_font(8),
            justify="left", wraplength=480,
        ).pack(anchor="w")
        self._totp.bind("<KeyRelease>", self._validate_totp)
        if self._ex.get("totp_secret"):
            self._validate_totp()

        br = ctk.CTkFrame(p, fg_color="transparent")
        br.pack(fill="x", pady=(16, 12))
        abtn(br, "Save", self._save).pack(side="right", padx=(8, 0))
        gbtn(br, "Cancel", self.destroy).pack(side="right")

    def _notes_val(self):
        return self._notes.get("1.0", "end").strip()

    def _upd_str(self, _=None):
        sc, lbl, col = pw_strength(self._pw.val())
        self._sbar.set_score(sc, col)
        self._slbl.configure(text=lbl if self._pw.val() else "", text_color=col)

    def _gen_pw(self):
        self._pw.set_val(gen_password(20))
        self._upd_str()

    def _validate_totp(self, _=None):
        secret = self._totp.val().strip()
        if not secret:
            self._totp_status.configure(text="")
            return
        if _totp_valid(secret):
            code, remaining, _ = _totp_code(secret)
            self._totp_status.configure(
                text=f"Valid — current code {code[:3]} {code[3:]} ({remaining}s)",
                text_color=C["success"])
        else:
            self._totp_status.configure(
                text="Invalid secret — base32 (A-Z, 2-7), at least 16 characters",
                text_color=C["danger"])

    def _save(self):
        t, pw = self._title.val().strip(), self._pw.val()
        if not t or not pw:
            messagebox.showwarning("Missing", "Title and password are required.", parent=self)
            return
        totp_secret = self._totp.val().strip().upper().replace(" ", "")
        if totp_secret and not _totp_valid(totp_secret):
            messagebox.showwarning(
                "Invalid 2FA secret",
                "The TOTP secret is not valid base32. Copy it exactly from the site setup page.",
                parent=self,
            )
            return
        self._cb(dict(
            title=t, username=self._user.val(), password=pw,
            url=self._url.val().strip(), notes=self._notes_val(),
            totp_secret=totp_secret,
        ))
        self.destroy()
