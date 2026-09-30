# modal dialogs and small popups

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date
from decimal import Decimal

from ..core.money import from_cents, money, parse_amount, valid_date
from ..core.constants import (
    ENTRY_TYPES, ACCOUNT_TYPES, CASH_FLOW_CATEGORIES,
    BUSINESS_TYPES, ORG_TYPES, INVENTORY_SYSTEMS,
)
from ..core.errors import AccountingError


class JournalEntryDialog(tk.Toplevel):
    def __init__(self, parent, books, entry=None):
        super().__init__(parent)
        self.books = books
        self.entry = entry
        self.result_id = None

        self.title("Journal Entry" if entry is None else f"Edit Entry #{entry['id']}")
        self.geometry("980x640")
        self.transient(parent)
        self.grab_set()

        self.accounts = books.list_accounts(active_only=True)
        self.account_labels = [f"{a['code']}  {a['name']}" for a in self.accounts]
        self.code_for_label = {f"{a['code']}  {a['name']}": a["code"] for a in self.accounts}

        self._build()
        if entry:
            self._load(entry)
        else:
            self._add_row()
            self._add_row()

        self.bind("<Escape>", lambda e: self.destroy())
        self.wait_window(self)

    def _build(self):
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)

        hdr = ttk.LabelFrame(outer, text="Entry Header", padding=10)
        hdr.pack(fill="x", pady=(0, 10))

        ttk.Label(hdr, text="Date:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.date_var = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(hdr, textvariable=self.date_var, width=14).grid(row=0, column=1, padx=(0, 16))

        ttk.Label(hdr, text="Type:").grid(row=0, column=2, sticky="w", padx=(0, 6))
        self.type_var = tk.StringVar(value="GENERAL")
        ttk.Combobox(hdr, textvariable=self.type_var, values=ENTRY_TYPES,
                     state="readonly", width=14).grid(row=0, column=3, padx=(0, 16))

        ttk.Label(hdr, text="Reference:").grid(row=0, column=4, sticky="w", padx=(0, 6))
        self.ref_var = tk.StringVar()
        ttk.Entry(hdr, textvariable=self.ref_var, width=18).grid(row=0, column=5, sticky="w")

        ttk.Label(hdr, text="Description:").grid(row=1, column=0, sticky="w",
                                                 pady=(8, 0), padx=(0, 6))
        self.desc_var = tk.StringVar()
        ttk.Entry(hdr, textvariable=self.desc_var).grid(
            row=1, column=1, columnspan=5, sticky="ew", pady=(8, 0))
        hdr.grid_columnconfigure(5, weight=1)

        lines_frame = ttk.LabelFrame(outer, text="Lines", padding=10)
        lines_frame.pack(fill="both", expand=True)

        canvas = tk.Canvas(lines_frame, borderwidth=0, highlightthickness=0)
        sb = ttk.Scrollbar(lines_frame, orient="vertical", command=canvas.yview)
        self.rows_frame = ttk.Frame(canvas)
        self.rows_frame.bind("<Configure>",
                             lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.rows_frame, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.line_rows = []

        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(10, 0))
        ttk.Button(footer, text="+ Add Line", command=self._add_row).pack(side="left")
        ttk.Button(footer, text="− Remove Last", command=self._remove_row).pack(side="left", padx=(6, 0))
        ttk.Button(footer, text="Depreciation Calculator…",
                   command=self._dep_calc).pack(side="left", padx=(6, 0))
        self.totals_var = tk.StringVar()
        ttk.Label(footer, textvariable=self.totals_var,
                  font=("Helvetica", 10, "bold")).pack(side="left", padx=20)
        ttk.Button(footer, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(footer, text="Save", command=self._save).pack(side="right", padx=(0, 6))
        self._update_totals()

    def _add_row(self, account_code=None, dr=None, cr=None, memo=None):
        row = ttk.Frame(self.rows_frame)
        row.pack(fill="x", pady=2)

        acct_var = tk.StringVar()
        dr_var = tk.StringVar()
        cr_var = tk.StringVar()
        memo_var = tk.StringVar()

        acct_cb = ttk.Combobox(row, textvariable=acct_var, values=self.account_labels, width=42)
        acct_cb.grid(row=0, column=0, padx=(0, 6), sticky="w")
        acct_cb.bind("<KeyRelease>", lambda e, cb=acct_cb: self._filter(cb))
        ttk.Entry(row, textvariable=dr_var, width=14, justify="right").grid(row=0, column=1, padx=(0, 6))
        ttk.Entry(row, textvariable=cr_var, width=14, justify="right").grid(row=0, column=2, padx=(0, 6))
        ttk.Entry(row, textvariable=memo_var, width=30).grid(row=0, column=3, padx=(0, 6))

        dr_var.trace_add("write", lambda *a: self._update_totals())
        cr_var.trace_add("write", lambda *a: self._update_totals())
        # debit/credit are mutually exclusive
        dr_var.trace_add("write", lambda *a, cv=cr_var, dv=dr_var: (cv.set("") if dv.get().strip() else None))
        cr_var.trace_add("write", lambda *a, dv=dr_var, cv=cr_var: (dv.set("") if cv.get().strip() else None))

        self.line_rows.append((acct_var, dr_var, cr_var, memo_var, row, acct_cb))

        if account_code:
            a = self.books.get_account(account_code)
            if a:
                acct_var.set(f"{a['code']}  {a['name']}")
        if dr:
            dr_var.set(str(dr))
        if cr:
            cr_var.set(str(cr))
        if memo:
            memo_var.set(memo)

    def _remove_row(self):
        if len(self.line_rows) <= 2:
            messagebox.showinfo("Min", "Need at least two lines.", parent=self)
            return
        _, _, _, _, row, _ = self.line_rows.pop()
        row.destroy()
        self._update_totals()

    def _filter(self, cb):
        t = cb.get().lower()
        if t:
            cb["values"] = [x for x in self.account_labels if t in x.lower()]
        else:
            cb["values"] = self.account_labels

    def _update_totals(self):
        d = Decimal("0")
        c = Decimal("0")
        for _, dr_v, cr_v, _, _, _ in self.line_rows:
            try:
                d += parse_amount(dr_v.get())
            except Exception:
                pass
            try:
                c += parse_amount(cr_v.get())
            except Exception:
                pass
        diff = d - c
        if diff == 0 and (d or c):
            self.totals_var.set(f"Dr {money(d)}  Cr {money(c)}  ✔ Balanced")
        else:
            self.totals_var.set(f"Dr {money(d)}  Cr {money(c)}  Diff {money(diff)}")

    def _load(self, entry):
        self.date_var.set(entry["entry_date"])
        self.type_var.set(entry["entry_type"])
        self.ref_var.set(entry["reference"] or "")
        self.desc_var.set(entry["description"])
        for ln in entry["lines"]:
            self._add_row(ln["account_code"],
                          from_cents(ln["debit"]) if ln["debit"] else None,
                          from_cents(ln["credit"]) if ln["credit"] else None,
                          ln.get("memo"))
        self._update_totals()

    def _dep_calc(self):
        StraightLineDialog(self, self)

    def _save(self):
        d = self.date_var.get().strip()
        if not valid_date(d):
            messagebox.showerror("Bad date", "YYYY-MM-DD")
            return
        desc = self.desc_var.get().strip()
        if not desc:
            messagebox.showerror("Missing", "Add description.")
            return

        lines = []
        for a_v, dr_v, cr_v, m_v, _, _ in self.line_rows:
            lab = a_v.get().strip()
            if not lab:
                continue
            code = self.code_for_label.get(lab)
            if not code:
                for lbl, c in self.code_for_label.items():
                    if lbl.startswith(lab):
                        code = c
                        break
            if not code:
                messagebox.showerror("Unknown", f"{lab} not found.")
                return
            try:
                dr = parse_amount(dr_v.get())
                cr = parse_amount(cr_v.get())
            except ValueError as e:
                messagebox.showerror("Bad amount", str(e))
                return
            if dr == 0 and cr == 0:
                continue
            lines.append({"account": code, "debit": dr, "credit": cr,
                          "memo": m_v.get().strip() or None})

        try:
            if self.entry is None:
                self.result_id = self.books.record_entry(
                    d, desc, lines, reference=self.ref_var.get().strip() or None,
                    entry_type=self.type_var.get())
            else:
                self.books.delete_entry(self.entry["id"])
                self.result_id = self.books.record_entry(
                    d, desc, lines, reference=self.ref_var.get().strip() or None,
                    entry_type=self.type_var.get())
        except AccountingError as e:
            messagebox.showerror("Cannot save", str(e))
            return
        self.destroy()


class StraightLineDialog(tk.Toplevel):
    def __init__(self, parent, journal_dlg):
        super().__init__(parent)
        self.parent_dlg = journal_dlg
        self.title("Straight-Line Depreciation / Amortization")
        self.geometry("440x320")
        self.transient(parent)
        self.grab_set()

        f = ttk.Frame(self, padding=14)
        f.pack(fill="both", expand=True)

        self.cost = tk.StringVar()
        self.resid = tk.StringVar(value="0")
        self.life_yrs = tk.StringVar()
        self.months = tk.StringVar(value="1")

        def add(r, lbl, var):
            ttk.Label(f, text=lbl).grid(row=r, column=0, sticky="w", pady=6, padx=(0, 10))
            ttk.Entry(f, textvariable=var, width=20).grid(row=r, column=1, sticky="ew")

        add(0, "Cost:", self.cost)
        add(1, "Residual value:", self.resid)
        add(2, "Useful life (years):", self.life_yrs)
        add(3, "Months to record:", self.months)
        f.grid_columnconfigure(1, weight=1)

        self.result_var = tk.StringVar()
        ttk.Label(f, textvariable=self.result_var, font=("Helvetica", 11, "bold"),
                  foreground="#0a3a6b").grid(row=4, column=0, columnspan=2, pady=14)
        ttk.Button(f, text="Compute", command=self._compute).grid(row=5, column=0, pady=4)
        ttk.Button(f, text="Insert into Line 1", command=self._insert).grid(row=5, column=1, pady=4)

    def _compute(self):
        try:
            c = parse_amount(self.cost.get())
            r = parse_amount(self.resid.get())
            y = parse_amount(self.life_yrs.get())
            m = parse_amount(self.months.get()) or Decimal("1")
            if y == 0:
                raise ValueError("Life years cannot be 0.")
            annual = (c - r) / y
            monthly = annual / 12
            total = monthly * m
            self.result_var.set(f"Annual: {money(annual)}    "
                                f"Monthly: {money(monthly)}    "
                                f"For {m} months: {money(total)}")
        except Exception as e:
            self.result_var.set(f"Error: {e}")

    def _insert(self):
        try:
            txt = self.result_var.get()
            if "For" not in txt:
                return
            amount = txt.split("For")[1].split("months:")[1].strip()
            acct_v, dr_v, cr_v, memo_v, _, _ = self.parent_dlg.line_rows[0]
            dr_v.set(amount)
            self.destroy()
        except Exception:
            pass


class AccountDialog(tk.Toplevel):
    def __init__(self, parent, books, account=None):
        super().__init__(parent)
        self.books = books
        self.account = account
        self.result = None

        self.title("Add Account" if not account else f"Edit {account['code']}")
        self.geometry("460x340")
        self.transient(parent)
        self.grab_set()

        f = ttk.Frame(self, padding=14)
        f.pack(fill="both", expand=True)

        self.code_var = tk.StringVar(value=account["code"] if account else "")
        self.name_var = tk.StringVar(value=account["name"] if account else "")
        self.type_var = tk.StringVar(value=account["type"] if account else "ASSET")
        self.subtype_var = tk.StringVar(value=account["subtype"] if account else "OPERATING")
        self.cf_var = tk.StringVar(value=account["cash_flow"] if account else "OPERATING")
        self.active_var = tk.BooleanVar(value=bool(account["is_active"]) if account else True)

        def row(r, lbl, w):
            ttk.Label(f, text=lbl).grid(row=r, column=0, sticky="w", pady=6, padx=(0, 10))
            w.grid(row=r, column=1, sticky="ew", pady=6)

        e = ttk.Entry(f, textvariable=self.code_var, width=30)
        if account:
            e.configure(state="readonly")
        row(0, "Code:", e)
        row(1, "Name:", ttk.Entry(f, textvariable=self.name_var, width=30))
        row(2, "Type:", ttk.Combobox(f, textvariable=self.type_var,
                                     values=ACCOUNT_TYPES, state="readonly", width=28))
        row(3, "Subtype:", ttk.Entry(f, textvariable=self.subtype_var, width=30))
        row(4, "Cash flow:", ttk.Combobox(f, textvariable=self.cf_var,
                                          values=CASH_FLOW_CATEGORIES, state="readonly", width=28))
        ttk.Checkbutton(f, text="Active", variable=self.active_var).grid(row=5, column=1, sticky="w")
        f.grid_columnconfigure(1, weight=1)

        btns = ttk.Frame(f)
        btns.grid(row=6, column=0, columnspan=2, pady=(16, 0), sticky="e")
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(btns, text="Save", command=self._save).pack(side="right", padx=(0, 6))
        self.wait_window(self)

    def _save(self):
        code = self.code_var.get().strip()
        name = self.name_var.get().strip()
        if not code or not name:
            messagebox.showerror("Missing", "Code & Name required.", parent=self)
            return
        try:
            if self.account is None:
                self.books.add_account(code, name, self.type_var.get(),
                                       subtype=self.subtype_var.get() or "OPERATING",
                                       cash_flow=self.cf_var.get() or "OPERATING")
            else:
                self.books.update_account(code, name,
                                          self.subtype_var.get() or "OPERATING",
                                          self.cf_var.get() or "OPERATING",
                                          self.active_var.get())
        except AccountingError as e:
            messagebox.showerror("Error", str(e), parent=self)
            return
        self.result = code
        self.destroy()


class CompanyProfileDialog(tk.Toplevel):
    def __init__(self, parent, books):
        super().__init__(parent)
        self.books = books
        self.title("Company Profile")
        self.geometry("500x420")
        self.transient(parent)
        self.grab_set()

        f = ttk.Frame(self, padding=14)
        f.pack(fill="both", expand=True)

        self.name_var = tk.StringVar(value=books.get_setting("company_name", ""))
        self.btype_var = tk.StringVar(value=books.get_setting("business_type", "Service"))
        self.org_var = tk.StringVar(value=books.get_setting("org_type", "Sole Proprietorship"))
        self.fye_var = tk.StringVar(value=books.get_setting("fiscal_year_end", "December 31"))
        self.inv_var = tk.StringVar(value=books.get_setting("inventory_system", "PERPETUAL"))
        self.tin_var = tk.StringVar(value=books.get_setting("tin", ""))

        def row(r, lbl, w):
            ttk.Label(f, text=lbl).grid(row=r, column=0, sticky="w", pady=6, padx=(0, 10))
            w.grid(row=r, column=1, sticky="ew", pady=6)

        row(0, "Business Name:", ttk.Entry(f, textvariable=self.name_var, width=36))
        row(1, "Type of Business:", ttk.Combobox(f, textvariable=self.btype_var,
                                                 values=BUSINESS_TYPES, state="readonly", width=34))
        row(2, "Form of Organization:", ttk.Combobox(f, textvariable=self.org_var,
                                                     values=ORG_TYPES, state="readonly", width=34))
        row(3, "Inventory System:", ttk.Combobox(f, textvariable=self.inv_var,
                                                 values=INVENTORY_SYSTEMS, state="readonly", width=34))
        row(4, "Fiscal Year End:", ttk.Entry(f, textvariable=self.fye_var, width=36))
        row(5, "TIN / Tax ID:", ttk.Entry(f, textvariable=self.tin_var, width=36))
        f.grid_columnconfigure(1, weight=1)

        btns = ttk.Frame(f)
        btns.grid(row=6, column=0, columnspan=2, pady=(16, 0), sticky="e")
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(btns, text="Save", command=self._save).pack(side="right", padx=(0, 6))
        self.wait_window(self)

    def _save(self):
        self.books.set_setting("company_name", self.name_var.get().strip())
        self.books.set_setting("business_type", self.btype_var.get())
        self.books.set_setting("org_type", self.org_var.get())
        self.books.set_setting("inventory_system", self.inv_var.get())
        self.books.set_setting("fiscal_year_end", self.fye_var.get().strip())
        self.books.set_setting("tin", self.tin_var.get().strip())
        self.destroy()


def _prompt_date(parent, title, default):
    w = tk.Toplevel(parent)
    w.title(title)
    w.geometry("300x120")
    w.transient(parent)
    w.grab_set()

    v = tk.StringVar(value=default)
    ttk.Label(w, text=title, padding=10).pack(anchor="w")
    ttk.Entry(w, textvariable=v, width=20).pack(padx=10)

    out = {"value": None}

    def ok():
        if valid_date(v.get().strip()):
            out["value"] = v.get().strip()
            w.destroy()
        else:
            messagebox.showerror("Bad date", "YYYY-MM-DD", parent=w)

    b = ttk.Frame(w, padding=10)
    b.pack(fill="x")
    ttk.Button(b, text="Cancel", command=w.destroy).pack(side="right")
    ttk.Button(b, text="OK", command=ok).pack(side="right", padx=(0, 6))
    parent.wait_window(w)
    return out["value"]