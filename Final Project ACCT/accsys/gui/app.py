# main window

import os
import sqlite3
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date
from decimal import Decimal

from ..core.engine import AccountingSystem
from ..core.demo import seed_demo
from ..core.money import money, from_cents, valid_date
from ..core.constants import CASH, ACCOUNT_TYPES
from ..core.errors import AccountingError

from .widgets import ScrolledTree
from .reports import render_report_text
from .dialogs import (
    JournalEntryDialog, AccountDialog, CompanyProfileDialog, _prompt_date,
)


class AccountingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Accounting Cycle System — Victor Lance Figueroa")
        self.root.geometry("1320x840")
        self.root.minsize(1120, 700)

        self.books = None
        self.db_path = None

        self._style()
        self._menu()
        self._toolbar()
        self._notebook()
        self._statusbar()
        self._new_books()
        self.refresh_all()

    def _style(self):
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure(".", font=("Helvetica", 10))
        s.configure("TNotebook.Tab", padding=(14, 8))
        s.configure("Treeview", rowheight=22, font=("Helvetica", 10))
        s.configure("Treeview.Heading", font=("Helvetica", 10, "bold"))
        s.configure("Card.TFrame", background="#ffffff", relief="solid", borderwidth=1)
        s.configure("CardTitle.TLabel", background="#ffffff", foreground="#555")
        s.configure("CardValue.TLabel", background="#ffffff",
                    foreground="#0a3a6b", font=("Helvetica", 18, "bold"))
        s.configure("Toolbar.TFrame", background="#f6f8fa")
        s.configure("Status.TLabel", background="#f0f0f0", anchor="w")

    def _menu(self):
        m = tk.Menu(self.root)

        fm = tk.Menu(m, tearoff=0)
        fm.add_command(label="New Books…", accelerator="Ctrl+N", command=self._new_books)
        fm.add_command(label="Open…", accelerator="Ctrl+O", command=self._open_books)
        fm.add_command(label="Save As…", accelerator="Ctrl+S", command=self._save_as)
        fm.add_separator()
        fm.add_command(label="Company Profile…", command=self._profile)
        fm.add_command(label="Seed Anna's Coffee Corner Demo", command=self._seed)
        fm.add_separator()
        fm.add_command(label="Exit", command=self.root.quit)
        m.add_cascade(label="File", menu=fm)

        em = tk.Menu(m, tearoff=0)
        em.add_command(label="New Journal Entry…", accelerator="Ctrl+J", command=self._new_entry)
        em.add_command(label="New Adjusting Entry…",
                       command=lambda: self._new_entry(default_type="ADJUSTING"))
        m.add_cascade(label="Entry", menu=em)

        rm = tk.Menu(m, tearoff=0)
        rm.add_command(label="Worksheet (10-column)", command=lambda: self._show_tab(5))
        rm.add_separator()
        rm.add_command(label="Statement of Financial Performance", command=lambda: self._show_tab(6, 0))
        rm.add_command(label="Statement of Financial Position", command=lambda: self._show_tab(6, 1))
        rm.add_command(label="Statement of Changes in Equity", command=lambda: self._show_tab(6, 2))
        rm.add_command(label="Statement of Cash Flows", command=lambda: self._show_tab(6, 3))
        rm.add_command(label="Notes to FS", command=lambda: self._show_tab(6, 4))
        rm.add_separator()
        rm.add_command(label="Trial Balance", command=lambda: self._show_tab(4))
        rm.add_command(label="General Ledger", command=lambda: self._show_tab(3))
        m.add_cascade(label="Reports", menu=rm)

        tm = tk.Menu(m, tearoff=0)
        tm.add_command(label="Close Period…", command=lambda: self._show_tab(7))
        tm.add_command(label="Verify Books", command=self._verify)
        m.add_cascade(label="Tools", menu=tm)

        hm = tk.Menu(m, tearoff=0)
        hm.add_command(label="About", command=self._about)
        hm.add_command(label="Accounting Concepts", command=self._concepts)
        m.add_cascade(label="Help", menu=hm)

        self.root.config(menu=m)
        self.root.bind("<Control-n>", lambda e: self._new_books())
        self.root.bind("<Control-o>", lambda e: self._open_books())
        self.root.bind("<Control-s>", lambda e: self._save_as())
        self.root.bind("<Control-j>", lambda e: self._new_entry())
        self.root.bind("<Control-q>", lambda e: self.root.quit)

    def _toolbar(self):
        b = ttk.Frame(self.root, style="Toolbar.TFrame", padding=(10, 6))
        b.pack(fill="x", side="top")
        ttk.Button(b, text="  New Entry  ", command=self._new_entry).pack(side="left")
        ttk.Button(b, text="  Adjusting Entry  ",
                   command=lambda: self._new_entry(default_type="ADJUSTING")).pack(side="left", padx=(6, 0))
        ttk.Button(b, text="  Refresh  ", command=self.refresh_all).pack(side="left", padx=(6, 0))
        ttk.Separator(b, orient="vertical").pack(side="left", fill="y", padx=12)
        ttk.Button(b, text="  Worksheet  ", command=lambda: self._show_tab(5)).pack(side="left")
        ttk.Button(b, text="  Verify  ", command=self._verify).pack(side="left", padx=(6, 0))
        self.db_label = ttk.Label(b, text="(no file)", style="Toolbar.TFrame")
        self.db_label.pack(side="right", padx=10)

    def _notebook(self):
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=10, pady=(6, 4))
        self._tab_dashboard()
        self._tab_accounts()
        self._tab_journal()
        self._tab_ledger()
        self._tab_trial()
        self._tab_worksheet()
        self._tab_statements()
        self._tab_close()

    def _tab_dashboard(self):
        f = ttk.Frame(self.nb, padding=14)
        self.nb.add(f, text="  Dashboard  ")

        ttk.Label(f, text="Financial Summary",
                  font=("Helvetica", 16, "bold")).pack(anchor="w", pady=(0, 12))

        cards = ttk.Frame(f)
        cards.pack(fill="x")
        self.card_vars = {}
        card_defs = [
            ("cash", "Cash"), ("assets", "Total Assets"),
            ("liabilities", "Total Liabilities"), ("equity", "Total Equity"),
            ("revenue", "Income (period)"), ("expenses", "Expenses (period)"),
            ("net", "Net Income (period)"), ("entries", "Journal Entries"),
        ]
        for i, (k, t) in enumerate(card_defs):
            r, c = divmod(i, 4)
            card = ttk.Frame(cards, style="Card.TFrame", padding=14)
            card.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")
            ttk.Label(card, text=t, style="CardTitle.TLabel").pack(anchor="w")
            v = tk.StringVar(value="0.00")
            ttk.Label(card, textvariable=v, style="CardValue.TLabel").pack(anchor="w", pady=(4, 0))
            self.card_vars[k] = v
            cards.grid_columnconfigure(c, weight=1)

        ttk.Label(f, text="Recent Journal Entries",
                  font=("Helvetica", 12, "bold")).pack(anchor="w", pady=(20, 6))
        self.dash_recent = ScrolledTree(
            f,
            columns=("id", "date", "ref", "desc", "type", "amount"),
            headings=("ID", "Date", "Reference", "Description", "Type", "Amount"),
            widths=(60, 100, 110, 400, 100, 130),
            anchor_right=("amount",), height=10)
        self.dash_recent.pack(fill="both", expand=True)

    def _tab_accounts(self):
        f = ttk.Frame(self.nb, padding=10)
        self.nb.add(f, text="  Chart of Accounts  ")

        b = ttk.Frame(f)
        b.pack(fill="x", pady=(0, 8))
        ttk.Button(b, text="Add Account", command=self._add_account).pack(side="left")
        ttk.Button(b, text="Edit Selected", command=self._edit_account).pack(side="left", padx=(6, 0))
        ttk.Button(b, text="Deactivate", command=self._deactivate).pack(side="left", padx=(6, 0))
        ttk.Label(b, text="Type:").pack(side="left", padx=(20, 4))
        self.coa_filter = tk.StringVar(value="ALL")
        cb = ttk.Combobox(b, textvariable=self.coa_filter,
                          values=("ALL",) + ACCOUNT_TYPES, state="readonly", width=14)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_accounts())

        self.coa_tree = ScrolledTree(
            f,
            columns=("code", "name", "type", "subtype", "normal", "cashflow", "active"),
            headings=("Code", "Name", "Type", "Subtype", "Normal", "Cash Flow", "Active"),
            widths=(70, 340, 100, 130, 100, 110, 70))
        self.coa_tree.pack(fill="both", expand=True)
        self.coa_tree.tree.bind("<Double-1>", lambda e: self._edit_account())

    def _tab_journal(self):
        f = ttk.Frame(self.nb, padding=10)
        self.nb.add(f, text="  Journal  ")

        b = ttk.Frame(f)
        b.pack(fill="x", pady=(0, 8))
        ttk.Button(b, text="New Entry", command=self._new_entry).pack(side="left")
        ttk.Button(b, text="View", command=self._view_entry).pack(side="left", padx=(6, 0))
        ttk.Button(b, text="Edit", command=self._edit_entry).pack(side="left", padx=(6, 0))
        ttk.Button(b, text="Reverse", command=self._reverse).pack(side="left", padx=(6, 0))
        ttk.Button(b, text="Delete", command=self._delete_entry).pack(side="left", padx=(6, 0))

        ttk.Label(b, text="From:").pack(side="left", padx=(20, 4))
        self.j_from = tk.StringVar()
        ttk.Entry(b, textvariable=self.j_from, width=12).pack(side="left")
        ttk.Label(b, text="To:").pack(side="left", padx=(10, 4))
        self.j_to = tk.StringVar()
        ttk.Entry(b, textvariable=self.j_to, width=12).pack(side="left")
        ttk.Button(b, text="Apply", command=self.refresh_journal).pack(side="left", padx=(8, 0))
        ttk.Button(b, text="Clear", command=self._clear_j).pack(side="left", padx=(4, 0))

        self.journal_tree = ScrolledTree(
            f,
            columns=("id", "date", "ref", "desc", "type", "dr", "cr"),
            headings=("ID", "Date", "Reference", "Description", "Type", "Debits", "Credits"),
            widths=(60, 100, 110, 380, 100, 120, 120),
            anchor_right=("dr", "cr"))
        self.journal_tree.pack(fill="both", expand=True)
        self.journal_tree.tree.bind("<Double-1>", lambda e: self._view_entry())

    def _tab_ledger(self):
        f = ttk.Frame(self.nb, padding=10)
        self.nb.add(f, text="  General Ledger  ")

        b = ttk.Frame(f)
        b.pack(fill="x", pady=(0, 8))
        ttk.Label(b, text="Account:").pack(side="left")
        self.ledger_acct = tk.StringVar()
        self.ledger_cb = ttk.Combobox(b, textvariable=self.ledger_acct, width=42, state="readonly")
        self.ledger_cb.pack(side="left", padx=(6, 16))
        self.ledger_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_ledger())
        ttk.Label(b, text="From:").pack(side="left")
        self.l_from = tk.StringVar()
        ttk.Entry(b, textvariable=self.l_from, width=12).pack(side="left", padx=(6, 10))
        ttk.Label(b, text="To:").pack(side="left")
        self.l_to = tk.StringVar()
        ttk.Entry(b, textvariable=self.l_to, width=12).pack(side="left", padx=(6, 10))
        ttk.Button(b, text="Refresh", command=self.refresh_ledger).pack(side="left")

        self.ledger_title = ttk.Label(f, text="", font=("Helvetica", 12, "bold"))
        self.ledger_title.pack(anchor="w", pady=(4, 6))

        self.ledger_tree = ScrolledTree(
            f,
            columns=("date", "id", "desc", "memo", "dr", "cr", "bal"),
            headings=("Date", "Entry", "Description", "Memo", "Debit", "Credit", "Balance"),
            widths=(100, 60, 330, 180, 110, 110, 130),
            anchor_right=("dr", "cr", "bal"))
        self.ledger_tree.pack(fill="both", expand=True)

    def _tab_trial(self):
        f = ttk.Frame(self.nb, padding=10)
        self.nb.add(f, text="  Trial Balance  ")

        b = ttk.Frame(f)
        b.pack(fill="x", pady=(0, 8))
        ttk.Label(b, text="As of:").pack(side="left")
        self.tb_date = tk.StringVar()
        ttk.Entry(b, textvariable=self.tb_date, width=14).pack(side="left", padx=(6, 6))
        ttk.Button(b, text="Generate", command=self.refresh_trial).pack(side="left")
        ttk.Separator(b, orient="vertical").pack(side="left", fill="y", padx=16)
        self.tb_mode = "unadjusted"
        self.tb_toggle = ttk.Button(b, text="Show Adjusted Trial Balance ▶",
                                    command=self._toggle_tb)
        self.tb_toggle.pack(side="left")

        self.tb_label = ttk.Label(f, text="", font=("Helvetica", 13, "bold"),
                                  foreground="#b35900")
        self.tb_label.pack(anchor="w", pady=(6, 6))

        self.tb_tree = ScrolledTree(
            f,
            columns=("code", "name", "type", "dr", "cr"),
            headings=("Code", "Account", "Type", "Debit", "Credit"),
            widths=(80, 420, 110, 150, 150),
            anchor_right=("dr", "cr"))
        self.tb_tree.pack(fill="both", expand=True)
        self.tb_status = ttk.Label(f, text="", font=("Helvetica", 10, "bold"))
        self.tb_status.pack(anchor="w", pady=(6, 0))

    def _tab_worksheet(self):
        f = ttk.Frame(self.nb, padding=10)
        self.nb.add(f, text="  Worksheet  ")

        b = ttk.Frame(f)
        b.pack(fill="x", pady=(0, 8))
        ttk.Label(b, text="As of:").pack(side="left")
        self.ws_date = tk.StringVar()
        ttk.Entry(b, textvariable=self.ws_date, width=14).pack(side="left", padx=(6, 6))
        ttk.Button(b, text="Generate Worksheet", command=self.refresh_worksheet).pack(side="left")
        ttk.Label(b, text="(TB → Adj → AdjTB → IS → BS)",
                  foreground="#666").pack(side="left", padx=(16, 0))

        cols = ("code", "name",
                "tb_dr", "tb_cr", "adj_dr", "adj_cr",
                "atb_dr", "atb_cr", "is_dr", "is_cr", "bs_dr", "bs_cr")
        headings = ("Code", "Account",
                    "TB Dr", "TB Cr", "Adj Dr", "Adj Cr",
                    "AdjTB Dr", "AdjTB Cr", "IS Dr", "IS Cr", "BS Dr", "BS Cr")
        widths = (55, 220, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90)
        self.ws_tree = ScrolledTree(
            f, columns=cols, headings=headings, widths=widths,
            anchor_right=("tb_dr", "tb_cr", "adj_dr", "adj_cr",
                          "atb_dr", "atb_cr", "is_dr", "is_cr", "bs_dr", "bs_cr"))
        self.ws_tree.pack(fill="both", expand=True)

    def _tab_statements(self):
        f = ttk.Frame(self.nb, padding=10)
        self.nb.add(f, text="  Financial Statements  ")

        b = ttk.Frame(f)
        b.pack(fill="x", pady=(0, 8))
        ttk.Label(b, text="Period Start:").pack(side="left")
        self.st_start = tk.StringVar()
        ttk.Entry(b, textvariable=self.st_start, width=12).pack(side="left", padx=(6, 12))
        ttk.Label(b, text="Period End:").pack(side="left")
        self.st_end = tk.StringVar()
        ttk.Entry(b, textvariable=self.st_end, width=12).pack(side="left", padx=(6, 12))
        ttk.Button(b, text="Generate All Reports",
                   command=self.refresh_statements).pack(side="left")

        sub = ttk.Notebook(f)
        sub.pack(fill="both", expand=True)
        self.statements_sub = sub

        def make(title):
            fr = ttk.Frame(sub, padding=4)
            sub.add(fr, text=f"  {title}  ")
            txt = tk.Text(fr, wrap="none", font=("Courier New", 10),
                          background="#fbfbfb", borderwidth=1, relief="solid")
            ys = ttk.Scrollbar(fr, orient="vertical", command=txt.yview)
            xs = ttk.Scrollbar(fr, orient="horizontal", command=txt.xview)
            txt.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
            txt.grid(row=0, column=0, sticky="nsew")
            ys.grid(row=0, column=1, sticky="ns")
            xs.grid(row=1, column=0, sticky="ew")
            fr.grid_rowconfigure(0, weight=1)
            fr.grid_columnconfigure(0, weight=1)
            return txt

        self.income_text = make("Statement of Financial Performance")
        self.bs_text = make("Statement of Financial Position")
        self.re_text = make("Statement of Changes in Equity")
        self.cf_text = make("Statement of Cash Flows")

        nf = ttk.Frame(sub, padding=6)
        sub.add(nf, text="  Notes to FS  ")
        self.notes_text = tk.Text(nf, wrap="word", font=("Courier New", 10),
                                  background="#fbfbfb", borderwidth=1, relief="solid")
        self.notes_text.pack(fill="both", expand=True)
        self.notes_text.bind("<KeyRelease>", lambda e: self._save_notes())
        self._notes_loading = False

    def _tab_close(self):
        f = ttk.Frame(self.nb, padding=14)
        self.nb.add(f, text="  Close Period  ")

        ttk.Label(f, text="Close the Accounting Period",
                  font=("Helvetica", 16, "bold")).pack(anchor="w")
        ttk.Label(f, text="Closes all income and expense accounts and transfers "
                          "the net result to equity.",
                  wraplength=900).pack(anchor="w", pady=(6, 14))

        r = ttk.Frame(f)
        r.pack(anchor="w", pady=(0, 10))
        ttk.Label(r, text="Close as of:").pack(side="left")
        self.close_date = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(r, textvariable=self.close_date, width=14).pack(side="left", padx=(6, 12))
        ttk.Label(r, text="Reference:").pack(side="left")
        self.close_ref = tk.StringVar()
        ttk.Entry(r, textvariable=self.close_ref, width=20).pack(side="left", padx=(6, 12))
        ttk.Button(r, text="Close Period", command=self._run_close).pack(side="left")

        self.close_log = tk.Text(f, height=20, font=("Courier New", 10),
                                 background="#fbfbfb", borderwidth=1, relief="solid")
        self.close_log.pack(fill="both", expand=True, pady=(6, 0))
        self.close_log.configure(state="disabled")

    def _statusbar(self):
        b = ttk.Frame(self.root, style="Toolbar.TFrame")
        b.pack(fill="x", side="bottom")
        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(b, textvariable=self.status_var, style="Status.TLabel",
                  padding=(10, 4)).pack(fill="x")

    def _status(self, m):
        self.status_var.set(m)
        self.root.update_idletasks()

    # file stuff -------------------------------------------------------------

    def _new_books(self, save_as=False):
        if save_as:
            p = filedialog.asksaveasfilename(
                defaultextension=".db",
                filetypes=[("Accounting books", "*.db"), ("All files", "*.*")])
            if not p:
                return
        else:
            p = ":memory:"
        if self.books:
            self.books.close()
        self.books = AccountingSystem(p)
        self.db_path = None if p == ":memory:" else p
        self._update_db()
        self.refresh_all()

    def _open_books(self):
        p = filedialog.askopenfilename(
            filetypes=[("Accounting books", "*.db"), ("All files", "*.*")])
        if not p:
            return
        try:
            if self.books:
                self.books.close()
            self.books = AccountingSystem(p)
            self.db_path = p
            self._update_db()
            self.refresh_all()
            self._status(f"Opened {p}")
        except Exception as e:
            messagebox.showerror("Cannot open", str(e))

    def _save_as(self):
        if not self.db_path:
            p = filedialog.asksaveasfilename(
                defaultextension=".db",
                filetypes=[("Accounting books", "*.db"), ("All files", "*.*")])
            if not p:
                return
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
            self.books.conn.commit()
            b = sqlite3.connect(p)
            with b:
                self.books.conn.backup(b)
            b.close()
            self.db_path = p
            self._update_db()
            self._status(f"Saved {p}")
        else:
            self.books.conn.commit()
            self._status(f"Saved {self.db_path}")

    def _profile(self):
        CompanyProfileDialog(self.root, self.books)
        self.refresh_all()
        self._status("Company profile updated.")

    def _seed(self):
        if not messagebox.askyesno("Seed Demo",
                                   "Load Anna's Coffee Corner demo transactions & adjustments?"):
            return
        try:
            seed_demo(self.books)
            self.refresh_all()
            self._status("Demo data loaded.")
        except AccountingError as e:
            messagebox.showerror("Cannot seed", str(e))

    def _update_db(self):
        lbl = self.db_path or "(in-memory)"
        self.db_label.configure(text=f"Books: {lbl}")

    # refresh ----------------------------------------------------------------

    def refresh_all(self):
        self.refresh_dashboard()
        self.refresh_accounts()
        self.refresh_journal()
        self.refresh_ledger_combo()
        self.refresh_trial()
        self.refresh_worksheet()
        self.refresh_statements()
        self._load_notes()

    def _default_period(self):
        r = self.books.conn.execute(
            "SELECT MIN(entry_date) a, MAX(entry_date) b FROM journal_entries").fetchone()
        t = date.today()
        return (r["a"] or t.replace(day=1).isoformat(),
                r["b"] or t.isoformat())

    def refresh_dashboard(self):
        for v in self.card_vars.values():
            v.set("0.00")
        self.dash_recent.clear()

        try:
            cash = self.books.account_balance(CASH)
        except Exception:
            cash = Decimal("0")

        s, e = self._default_period()
        bs = self.books.balance_sheet()
        inc = self.books.income_statement(s, e)
        cnt = self.books.conn.execute("SELECT COUNT(*) FROM journal_entries").fetchone()[0]

        self.card_vars["cash"].set(money(cash))
        self.card_vars["assets"].set(money(bs["total_assets"]))
        self.card_vars["liabilities"].set(money(bs["total_liabilities"]))
        self.card_vars["equity"].set(money(bs["total_equity"]))
        self.card_vars["revenue"].set(money(inc["total_revenue"]))
        self.card_vars["expenses"].set(money(inc["total_expenses"]))
        self.card_vars["net"].set(money(inc["net_income"]))
        self.card_vars["entries"].set(str(cnt))

        for en in reversed(self.books.journal()[-12:]):
            tot = sum(l["debit"] for l in en["lines"])
            self.dash_recent.add((en["id"], en["entry_date"], en["reference"] or "—",
                                  en["description"], en["entry_type"],
                                  money(from_cents(tot))))

    def refresh_accounts(self):
        self.coa_tree.clear()
        tf = self.coa_filter.get()
        for a in self.books.list_accounts(type_=None if tf == "ALL" else tf):
            self.coa_tree.add((a["code"], a["name"], a["type"], a["subtype"],
                               a["normal_balance"], a["cash_flow"],
                               "Yes" if a["is_active"] else "No"),
                              tags=() if a["is_active"] else ("muted",))

    def refresh_journal(self):
        self.journal_tree.clear()
        s = self.j_from.get().strip() or None
        e = self.j_to.get().strip() or None
        for en in self.books.journal(s, e):
            dr = sum(l["debit"] for l in en["lines"])
            cr = sum(l["credit"] for l in en["lines"])
            self.journal_tree.add((en["id"], en["entry_date"], en["reference"] or "—",
                                   en["description"], en["entry_type"],
                                   money(from_cents(dr)), money(from_cents(cr))))

    def _clear_j(self):
        self.j_from.set("")
        self.j_to.set("")
        self.refresh_journal()

    def refresh_ledger_combo(self):
        labs = [f"{a['code']}  {a['name']}" for a in self.books.list_accounts()]
        self.ledger_cb["values"] = labs
        if not self.ledger_acct.get() and labs:
            self.ledger_acct.set(labs[0])

    def refresh_ledger(self):
        self.ledger_tree.clear()
        self.ledger_title.configure(text="")
        lab = self.ledger_acct.get().strip()
        if not lab:
            return
        code = lab.split()[0]
        s = self.l_from.get().strip() or None
        e = self.l_to.get().strip() or None
        try:
            gl = self.books.general_ledger(code, s, e)
        except AccountingError as ex:
            self._status(str(ex))
            return
        a = gl["account"]
        self.ledger_title.configure(
            text=f"{a['code']}  {a['name']}  —  opening: "
                 f"{money(from_cents(gl['opening_cents']))} ({a['normal_balance']})")
        for r in gl["rows"]:
            dr = money(from_cents(r["debit"])) if r["debit"] else ""
            cr = money(from_cents(r["credit"])) if r["credit"] else ""
            bal = from_cents(r["balance_cents"])
            self.ledger_tree.add(
                (r["entry_date"], r["entry_id"], r["description"][:60],
                 r["memo"] or "", dr, cr, money(bal)),
                tags=("negative",) if bal < 0 else ())
        self.ledger_tree.add(
            ("", "", "Closing Balance", "", "", "",
             money(from_cents(gl["closing_cents"]))),
            tags=("total",))

    def _toggle_tb(self):
        self.tb_mode = "adjusted" if self.tb_mode == "unadjusted" else "unadjusted"
        if self.tb_mode == "adjusted":
            self.tb_toggle.configure(text="◀ Show Unadjusted Trial Balance")
        else:
            self.tb_toggle.configure(text="Show Adjusted Trial Balance ▶")
        self.refresh_trial()

    def refresh_trial(self):
        self.tb_tree.clear()
        d = self.tb_date.get().strip() or None
        if d and not valid_date(d):
            self.tb_status.configure(text="Bad date.", foreground="#b00")
            return

        if self.tb_mode == "unadjusted":
            ex = ("ADJUSTING", "REVERSING", "CLOSING")
            self.tb_label.configure(text="UNadjusted TRIAL BALANCE", foreground="#b35900")
        else:
            ex = ("CLOSING",)
            self.tb_label.configure(text="ADJUSTED TRIAL BALANCE", foreground="#1a7f37")

        tb = self.books.trial_balance(d, exclude_types=ex)
        for r in tb["rows"]:
            a = r["account"]
            self.tb_tree.add((a["code"], a["name"], a["type"],
                              money(r["debit"]) if r["debit"] else "",
                              money(r["credit"]) if r["credit"] else ""))
        self.tb_tree.add(("", "TOTALS", "",
                          money(tb["total_debit"]), money(tb["total_credit"])),
                         tags=("total",))
        if tb["balanced"]:
            self.tb_status.configure(text="✔ Balanced.", foreground="#1a7f37")
        else:
            self.tb_status.configure(text="✘ NOT BALANCED.", foreground="#b00")

    def refresh_worksheet(self):
        self.ws_tree.clear()
        d = self.ws_date.get().strip() or None
        if d and not valid_date(d):
            d = None
        ws = self.books.worksheet(d)

        def f(x):
            return money(from_cents(x)) if x else ""

        for r in ws["rows"]:
            a = r["account"]
            self.ws_tree.add((
                a["code"], a["name"],
                f(r["tb_dr"]), f(r["tb_cr"]),
                f(r["adj_dr"]), f(r["adj_cr"]),
                f(r["atb_dr"]), f(r["atb_cr"]),
                f(r["is_dr"]), f(r["is_cr"]),
                f(r["bs_dr"]), f(r["bs_cr"])))

        net = ws["net_income_cents"]
        label = "Net Income" if net >= 0 else "Net Loss"
        self.ws_tree.add((
            "", label,
            "", "", "", "", "", "",
            money(from_cents(ws["net_is_dr"])) if ws["net_is_dr"] else "",
            money(from_cents(ws["net_is_cr"])) if ws["net_is_cr"] else "",
            money(from_cents(ws["net_bs_dr"])) if ws["net_bs_dr"] else "",
            money(from_cents(ws["net_bs_cr"])) if ws["net_bs_cr"] else ""),
            tags=("net",))

        T = ws["totals"]
        self.ws_tree.add((
            "", "TOTALS",
            money(from_cents(T["tb_dr"])), money(from_cents(T["tb_cr"])),
            money(from_cents(T["adj_dr"])), money(from_cents(T["adj_cr"])),
            money(from_cents(T["atb_dr"])), money(from_cents(T["atb_cr"])),
            money(from_cents(T["is_dr"])), money(from_cents(T["is_cr"])),
            money(from_cents(T["bs_dr"])), money(from_cents(T["bs_cr"]))),
            tags=("total",))

    # statements -------------------------------------------------------------

    def _save_notes(self):
        if self._notes_loading:
            return
        try:
            self.books.set_setting("notes_to_fs", self.notes_text.get("1.0", "end").rstrip())
        except Exception:
            pass

    def _load_notes(self):
        self._notes_loading = True
        self.notes_text.delete("1.0", "end")
        self.notes_text.insert("1.0", self.books.get_setting("notes_to_fs", ""))
        self._notes_loading = False

    def refresh_statements(self):
        company = self.books.get_setting("company_name", "")
        org = self.books.get_setting("org_type", "Sole Proprietorship")

        s = self.st_start.get().strip() or None
        e = self.st_end.get().strip() or None
        if not (s and e):
            s, e = self._default_period()
            self.st_start.set(s)
            self.st_end.set(e)
        if not (valid_date(s) and valid_date(e)):
            return

        # statement of financial performance
        st = self.books.income_statement(s, e)
        sections = [{"type": "heading", "text": "INCOME"}]
        for r in st["revenue"]:
            sections.append({"type": "line",
                             "label": f"{r['account']['code']}  {r['account']['name']}",
                             "amount": money(r["amount"])})
        sections.append({"type": "total", "label": "Total Income",
                         "amount": money(st["total_revenue"])})
        sections.append({"type": "space"})

        if st.get("periodic_cogs"):
            pc = st["periodic_cogs"]
            sections.append({"type": "heading", "text": "COST OF GOODS SOLD (Periodic)"})
            sections.append({"type": "line", "label": "Beginning Inventory",
                             "amount": money(pc["beginning_inventory"])})
            sections.append({"type": "line", "label": "Add: Purchases",
                             "amount": money(pc["purchases"])})
            sections.append({"type": "line", "label": "Add: Freight-in",
                             "amount": money(pc["freight_in"])})
            sections.append({"type": "line", "label": "Less: Purchase Returns & Allow.",
                             "amount": money(-pc["purchase_returns"])})
            sections.append({"type": "line", "label": "Less: Purchase Discount",
                             "amount": money(-pc["purchase_discount"])})
            sections.append({"type": "total", "label": "Net Purchases",
                             "amount": money(pc["net_purchases"])})
            sections.append({"type": "total", "label": "TGAS",
                             "amount": money(pc["tgas"])})
            sections.append({"type": "line", "label": "Less: Ending Inventory",
                             "amount": money(-pc["ending_inventory"])})
            sections.append({"type": "total", "label": "Cost of Goods Sold",
                             "amount": money(pc["cogs"])})
            sections.append({"type": "space"})

        sections.append({"type": "heading", "text": "OPERATING EXPENSES"})
        for x in st["expenses"]:
            sections.append({"type": "line",
                             "label": f"{x['account']['code']}  {x['account']['name']}",
                             "amount": money(x["amount"])})
        cogs_add = st["periodic_cogs"]["cogs_cents"] if st.get("periodic_cogs") else 0
        sections.append({"type": "total", "label": "Total Operating Expenses",
                         "amount": money(st["total_expenses"] - cogs_add)})
        lbl = "NET INCOME" if st["net_income_cents"] >= 0 else "NET LOSS"
        sections.append({"type": "grand", "label": lbl,
                         "amount": money(st["net_income"])})
        render_report_text(self.income_text,
                           "STATEMENT OF FINANCIAL PERFORMANCE",
                           f"For the period {s} to {e}", sections, company=company)

        # statement of financial position
        bs = self.books.balance_sheet(e)

        def group(items, keys):
            g = {k: [] for k in keys}
            for it in items:
                g.setdefault(it["account"].get("subtype", "OTHER"), []).append(it)
            return [(k, g[k]) for k in g if g[k]]

        sections = [{"type": "heading", "text": "ASSETS"}]
        for sub, items in group(bs["assets"], ["CURRENT", "NONCURRENT", "INTANGIBLE", "CONTRA", "OTHER"]):
            lbl2 = {"CURRENT": "Current Assets", "NONCURRENT": "Noncurrent Assets",
                    "INTANGIBLE": "Intangible Assets",
                    "CONTRA": "Less: Contra Assets"}.get(sub, sub)
            sections.append({"type": "section", "text": lbl2})
            for r in items:
                sections.append({"type": "line",
                                 "label": f"{r['account']['code']}  {r['account']['name']}",
                                 "amount": money(r["amount"])})
        sections.append({"type": "total", "label": "Total Assets",
                         "amount": money(bs["total_assets"])})
        sections.append({"type": "space"})

        sections.append({"type": "heading", "text": "LIABILITIES"})
        for sub, items in group(bs["liabilities"], ["CURRENT", "NONCURRENT", "OTHER"]):
            lbl2 = {"CURRENT": "Current Liabilities",
                    "NONCURRENT": "Noncurrent Liabilities"}.get(sub, sub)
            sections.append({"type": "section", "text": lbl2})
            for r in items:
                sections.append({"type": "line",
                                 "label": f"{r['account']['code']}  {r['account']['name']}",
                                 "amount": money(r["amount"])})
        sections.append({"type": "total", "label": "Total Liabilities",
                         "amount": money(bs["total_liabilities"])})
        sections.append({"type": "space"})

        sections.append({"type": "heading", "text": "EQUITY"})
        for r in bs["equity"]:
            sections.append({"type": "line",
                             "label": f"{r['account']['code']}  {r['account']['name']}",
                             "amount": money(r["amount"])})
        sections.append({"type": "total", "label": "Total Equity",
                         "amount": money(bs["total_equity"])})
        sections.append({"type": "grand", "label": "TOTAL LIABILITIES AND EQUITY",
                         "amount": money(bs["total_liabilities_equity"])})
        sections.append({"type": "note",
                         "text": "✔ A = L + E" if bs["balanced"] else "✘ A ≠ L + E"})
        render_report_text(self.bs_text, "STATEMENT OF FINANCIAL POSITION",
                           f"As of {e}", sections, company=company)

        # statement of changes in equity
        sce = self.books.changes_in_equity_statement(s, e)
        if org == "Sole Proprietorship":
            sections = [
                {"type": "line", "label": "Owner's Capital, Beginning",
                 "amount": money(sce["beginning_capital"])},
                {"type": "line", "label": "Add: Net Income",
                 "amount": money(sce["net_income"])},
                {"type": "line", "label": "Less: Owner's Drawings",
                 "amount": money(-sce["distributions"])},
                {"type": "grand", "label": "Owner's Capital, Ending",
                 "amount": money(sce["beginning_capital"] + sce["net_income"]
                                 - sce["distributions"])}]
        else:
            sections = [
                {"type": "line", "label": "Retained Earnings, Beginning",
                 "amount": money(sce["beginning_earnings"])},
                {"type": "line", "label": "Add: Net Income",
                 "amount": money(sce["net_income"])},
                {"type": "line", "label": "Less: Dividends",
                 "amount": money(-sce["distributions"])},
                {"type": "grand", "label": "Retained Earnings, Ending",
                 "amount": money(sce["ending_earnings"])}]
        render_report_text(self.re_text, "STATEMENT OF CHANGES IN EQUITY",
                           f"For the period {s} to {e}", sections, company=company)

        # statement of cash flows
        cf = self.books.cash_flow_statement(s, e)
        sections = [{"type": "heading", "text": "OPERATING ACTIVITIES"}]
        for lbl2, amt in cf["operating"]:
            sections.append({"type": "line", "label": lbl2, "amount": money(from_cents(amt))})
        sections.append({"type": "total", "label": "Net Cash from Operations",
                         "amount": money(cf["net_cash_operating"])})
        sections.append({"type": "space"})

        sections.append({"type": "heading", "text": "INVESTING ACTIVITIES"})
        for lbl2, amt in cf["investing"]:
            sections.append({"type": "line", "label": lbl2, "amount": money(from_cents(amt))})
        sections.append({"type": "total", "label": "Net Cash from Investing",
                         "amount": money(cf["net_cash_investing"])})
        sections.append({"type": "space"})

        sections.append({"type": "heading", "text": "FINANCING ACTIVITIES"})
        for lbl2, amt in cf["financing"]:
            sections.append({"type": "line", "label": lbl2, "amount": money(from_cents(amt))})
        sections.append({"type": "total", "label": "Net Cash from Financing",
                         "amount": money(cf["net_cash_financing"])})
        sections.append({"type": "space"})

        sections.append({"type": "line", "label": "Net Change in Cash",
                         "amount": money(cf["net_change"])})
        sections.append({"type": "line", "label": "Cash, Beginning",
                         "amount": money(cf["cash_begin"])})
        sections.append({"type": "grand", "label": "Cash, Ending",
                         "amount": money(cf["cash_end"])})
        if cf["reconciled"]:
            sections.append({"type": "note", "text": "✔ Reconciles."})
        render_report_text(self.cf_text, "STATEMENT OF CASH FLOWS",
                           f"For the period {s} to {e}", sections, company=company)

    # actions ----------------------------------------------------------------

    def _show_tab(self, i, sub=None):
        self.nb.select(i)
        if sub is not None:
            self.statements_sub.select(sub)

    def _selected(self, t):
        s = t.tree.selection()
        return t.tree.item(s[0], "values") if s else None

    def _add_account(self):
        AccountDialog(self.root, self.books)
        self.refresh_accounts()
        self.refresh_ledger_combo()

    def _edit_account(self):
        r = self._selected(self.coa_tree)
        if not r:
            return
        a = self.books.get_account(r[0])
        if not a:
            return
        AccountDialog(self.root, self.books, a)
        self.refresh_accounts()

    def _deactivate(self):
        r = self._selected(self.coa_tree)
        if not r:
            return
        if not messagebox.askyesno("Deactivate", f"Deactivate {r[0]} {r[1]}?"):
            return
        try:
            self.books.deactivate_account(r[0])
            self.refresh_accounts()
        except AccountingError as e:
            messagebox.showerror("Error", str(e))

    def _new_entry(self, default_type=None):
        d = JournalEntryDialog(self.root, self.books)
        if d.result_id:
            self.refresh_all()
            self._status(f"Saved #{d.result_id}.")

    def _view_entry(self):
        r = self._selected(self.journal_tree)
        if not r:
            return
        e = self.books.get_entry(int(r[0]))
        if not e:
            return

        w = tk.Toplevel(self.root)
        w.title(f"Entry #{e['id']}")
        w.geometry("760x420")
        w.transient(self.root)

        info = ttk.Frame(w, padding=10)
        info.pack(fill="x")
        for x in (f"Date: {e['entry_date']}", f"Type: {e['entry_type']}",
                  f"Ref: {e['reference'] or '—'}", f"Description: {e['description']}"):
            ttk.Label(info, text=x).pack(anchor="w")

        t = ScrolledTree(w, columns=("code", "name", "memo", "dr", "cr"),
                         headings=("Code", "Account", "Memo", "Debit", "Credit"),
                         widths=(80, 220, 200, 110, 110), anchor_right=("dr", "cr"))
        t.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        for ln in e["lines"]:
            t.add((ln["account_code"], ln["account_name"], ln["memo"] or "",
                   money(from_cents(ln["debit"])) if ln["debit"] else "",
                   money(from_cents(ln["credit"])) if ln["credit"] else ""))
        dr = sum(x["debit"] for x in e["lines"])
        cr = sum(x["credit"] for x in e["lines"])
        t.add(("", "TOTALS", "", money(from_cents(dr)), money(from_cents(cr))),
              tags=("total",))
        ttk.Button(w, text="Close", command=w.destroy).pack(pady=(0, 10))

    def _edit_entry(self):
        r = self._selected(self.journal_tree)
        if not r:
            return
        e = self.books.get_entry(int(r[0]))
        if not e:
            return
        d = JournalEntryDialog(self.root, self.books, e)
        if d.result_id:
            self.refresh_all()

    def _reverse(self):
        r = self._selected(self.journal_tree)
        if not r:
            return
        e = self.books.get_entry(int(r[0]))
        if not e:
            return
        dd = _prompt_date(self.root, "Reversal date", e["entry_date"])
        if not dd:
            return
        try:
            nid = self.books.reverse_entry(int(r[0]), dd)
        except AccountingError as ex:
            messagebox.showerror("Error", str(ex))
            return
        self.refresh_all()
        self._status(f"Reversed → #{nid}.")

    def _delete_entry(self):
        r = self._selected(self.journal_tree)
        if not r:
            return
        eid = int(r[0])
        if not messagebox.askyesno("Delete", f"Delete entry #{eid}?"):
            return
        self.books.delete_entry(eid)
        self.refresh_all()

    def _run_close(self):
        d = self.close_date.get().strip()
        if not valid_date(d):
            messagebox.showerror("Bad date", "YYYY-MM-DD")
            return
        if not messagebox.askyesno("Close", f"Close as of {d}?"):
            return
        try:
            created = self.books.close_period(d, self.close_ref.get().strip() or None)
        except AccountingError as e:
            messagebox.showerror("Cannot close", str(e))
            return

        self.close_log.configure(state="normal")
        self.close_log.delete("1.0", "end")
        if not created:
            self.close_log.insert("end", "Nothing to close.\n")
        else:
            self.close_log.insert("end", f"Created {len(created)} entries:\n\n")
            for eid in created:
                e = self.books.get_entry(eid)
                self.close_log.insert("end", f"#{eid}  {e['description']}\n")
                for ln in e["lines"]:
                    dr = money(from_cents(ln["debit"])) if ln["debit"] else ""
                    cr = money(from_cents(ln["credit"])) if ln["credit"] else ""
                    self.close_log.insert(
                        "end",
                        f"      {ln['account_code']:<6}{ln['account_name'][:36]:<38}"
                        f"{dr:>13}{cr:>14}\n")
                self.close_log.insert("end", "\n")
        self.close_log.configure(state="disabled")
        self.refresh_all()

    def _verify(self):
        r = self.books.verify()
        if r["ok"]:
            messagebox.showinfo(
                "Verify",
                "✔ All checks passed.\n\n• Entries balance\n• No double-sided lines\n"
                "• A = L + E\n• Trial balance balances")
        else:
            messagebox.showwarning(
                "Verify",
                "Issues:\n\n" + "\n".join("• " + p for p in r["problems"]))

    def _about(self):
        messagebox.showinfo(
            "About",
            "Accounting Cycle System — GUI Edition\n\n"
            "Aligned with:\n"
            "• Basic Accounting Concepts (Bianca C. Taylan, CPA)\n"
            "• Anna's Coffee Corner worksheet (Periodic & Perpetual)")

    def _concepts(self):
        messagebox.showinfo(
            "Accounting Concepts",
            "ACCOUNTING EQUATION\n  Assets = Liabilities + Equity\n\n"
            "NORMAL SIDES\n  DEBIT : Assets, Expenses, Drawings\n"
            "  CREDIT: Liabilities, Equity, Income\n\n"
            "PERIODIC INVENTORY\n  Purchases + Freight-in\n"
            "  − Purchase Returns − Purchase Discount\n  = Net Purchases\n\n"
            "COGS = Beg Inv + Net Purchases − End Inv\n\n"
            "5 FINANCIAL STATEMENTS\n"
            "  1. Statement of Financial Performance\n"
            "  2. Statement of Financial Position\n"
            "  3. Statement of Cash Flows\n"
            "  4. Statement of Changes in Equity\n"
            "  5. Notes to FS")


def main():
    root = tk.Tk()
    try:
        if sys.platform == "darwin":
            root.tk.call("tk", "scaling", 1.2)
    except tk.TclError:
        pass

    app = AccountingApp(root)

    def _close():
        try:
            if app.books:
                app.books.conn.commit()
        except Exception:
            pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", _close)
    root.mainloop()