# the accounting engine -- database, entries, statements, closing

import sqlite3
from datetime import date, timedelta
from decimal import Decimal

from .money import to_cents, from_cents, money, valid_date
from .constants import (
    ACCOUNT_TYPES, NORMAL_BALANCE, ENTRY_TYPES,
    CASH, INCOME_SUMMARY, RETAINED_EARNINGS,
)
from .chart import DEFAULT_CHART
from .errors import AccountingError


class AccountingSystem:
    def __init__(self, db_path=":memory:", seed_chart=True):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._create_schema()
        if seed_chart:
            self.seed_default_chart()

    def close(self):
        self.conn.close()

    def _create_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS accounts (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                subtype TEXT NOT NULL DEFAULT 'OPERATING',
                normal_balance TEXT NOT NULL CHECK (normal_balance IN ('DEBIT','CREDIT')),
                cash_flow TEXT NOT NULL DEFAULT 'OPERATING',
                is_active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS journal_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_date TEXT NOT NULL,
                reference TEXT,
                description TEXT NOT NULL,
                entry_type TEXT NOT NULL DEFAULT 'GENERAL',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS journal_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_id INTEGER NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE,
                line_no INTEGER NOT NULL,
                account_code TEXT NOT NULL REFERENCES accounts(code),
                debit INTEGER NOT NULL DEFAULT 0,
                credit INTEGER NOT NULL DEFAULT 0,
                memo TEXT,
                CHECK (debit >= 0 AND credit >= 0),
                CHECK (debit = 0 OR credit = 0)
            );
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
            CREATE INDEX IF NOT EXISTS idx_lines_account ON journal_lines(account_code);
            CREATE INDEX IF NOT EXISTS idx_entries_date ON journal_entries(entry_date);
        """)
        self.conn.commit()

    def seed_default_chart(self):
        with self.conn:
            self.conn.executemany(
                "INSERT OR IGNORE INTO accounts "
                "(code,name,type,subtype,normal_balance,cash_flow) VALUES (?,?,?,?,?,?)",
                DEFAULT_CHART)

    # accounts ---------------------------------------------------------------

    def add_account(self, code, name, type_, subtype="OPERATING", cash_flow="OPERATING"):
        code = str(code).strip()
        type_ = str(type_).upper()
        if type_ not in ACCOUNT_TYPES:
            raise AccountingError(f"Account type must be one of {ACCOUNT_TYPES}.")
        nb = NORMAL_BALANCE[type_]
        if self.get_account(code):
            raise AccountingError(f"Account {code} already exists.")
        with self.conn:
            self.conn.execute(
                "INSERT INTO accounts (code,name,type,subtype,normal_balance,cash_flow) "
                "VALUES (?,?,?,?,?,?)",
                (code, name, type_, subtype.upper(), nb, cash_flow))

    def update_account(self, code, name, subtype, cash_flow, is_active=True):
        with self.conn:
            self.conn.execute(
                "UPDATE accounts SET name=?,subtype=?,cash_flow=?,is_active=? WHERE code=?",
                (name, subtype.upper(), cash_flow.upper(), 1 if is_active else 0, str(code)))

    def get_account(self, code):
        r = self.conn.execute("SELECT * FROM accounts WHERE code=?", (str(code),)).fetchone()
        return dict(r) if r else None

    def list_accounts(self, type_=None, active_only=False):
        sql = "SELECT * FROM accounts WHERE 1=1"
        p = []
        if type_:
            sql += " AND type=?"
            p.append(str(type_).upper())
        if active_only:
            sql += " AND is_active=1"
        sql += " ORDER BY code"
        return [dict(r) for r in self.conn.execute(sql, p).fetchall()]

    def deactivate_account(self, code):
        with self.conn:
            self.conn.execute("UPDATE accounts SET is_active=0 WHERE code=?", (str(code),))

    def get_setting(self, key, default=""):
        r = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default

    def set_setting(self, key, value):
        with self.conn:
            self.conn.execute(
                "INSERT INTO settings (key,value) VALUES (?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)))

    # journal ----------------------------------------------------------------

    def record_entry(self, entry_date, description, lines, reference=None, entry_type="GENERAL"):
        entry_type = str(entry_type).upper()
        if entry_type not in ENTRY_TYPES:
            raise AccountingError("Bad entry type.")
        if not valid_date(entry_date):
            raise AccountingError("Bad date.")
        if not lines:
            raise AccountingError("Need at least two lines.")

        prepared = []
        tdr = tcr = 0
        for raw in lines:
            code = str(raw.get("account", "")).strip()
            dr = to_cents(raw.get("debit"))
            cr = to_cents(raw.get("credit"))
            if dr < 0 or cr < 0:
                raise AccountingError("Amounts cannot be negative.")
            if dr and cr:
                raise AccountingError(f"Line {code} has both debit and credit.")
            if dr == 0 and cr == 0:
                continue
            if not self.get_account(code):
                raise AccountingError(f"Unknown account {code}.")
            prepared.append((len(prepared) + 1, code, dr, cr, raw.get("memo")))
            tdr += dr
            tcr += cr

        if len(prepared) < 2:
            raise AccountingError("Need two lines with amounts.")
        if tdr != tcr:
            raise AccountingError(
                f"Entry does not balance: Dr {money(from_cents(tdr))} vs "
                f"Cr {money(from_cents(tcr))}.")

        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO journal_entries (entry_date,reference,description,entry_type) "
                "VALUES (?,?,?,?)",
                (entry_date, reference, description, entry_type))
            eid = cur.lastrowid
            self.conn.executemany(
                "INSERT INTO journal_lines (entry_id,line_no,account_code,debit,credit,memo) "
                "VALUES (?,?,?,?,?,?)",
                [(eid, n, c, d, k, m) for n, c, d, k, m in prepared])
        return eid

    def reverse_entry(self, entry_id, reversal_date=None, reference=None):
        e = self.get_entry(entry_id)
        if e is None:
            raise AccountingError(f"No entry #{entry_id}.")
        lines = []
        for ln in e["lines"]:
            lines.append({
                "account": ln["account_code"],
                "debit": from_cents(ln["credit"]),
                "credit": from_cents(ln["debit"]),
                "memo": "Reversal",
            })
        return self.record_entry(reversal_date or e["entry_date"],
                                 f"Reversing entry for #{entry_id}",
                                 lines, reference=reference or e["reference"],
                                 entry_type="REVERSING")

    def delete_entry(self, entry_id):
        with self.conn:
            self.conn.execute("DELETE FROM journal_entries WHERE id=?", (entry_id,))

    def get_entry(self, entry_id):
        r = self.conn.execute("SELECT * FROM journal_entries WHERE id=?", (entry_id,)).fetchone()
        if not r:
            return None
        e = dict(r)
        e["lines"] = [dict(x) for x in self.conn.execute(
            "SELECT l.*,a.name AS account_name FROM journal_lines l "
            "JOIN accounts a ON a.code=l.account_code WHERE l.entry_id=? "
            "ORDER BY l.line_no", (entry_id,)).fetchall()]
        return e

    def journal(self, start=None, end=None, entry_type=None):
        sql = "SELECT * FROM journal_entries WHERE 1=1"
        p = []
        if start:
            sql += " AND entry_date>=?"
            p.append(start)
        if end:
            sql += " AND entry_date<=?"
            p.append(end)
        if entry_type:
            sql += " AND entry_type=?"
            p.append(entry_type.upper())
        sql += " ORDER BY entry_date,id"
        out = []
        for r in self.conn.execute(sql, p).fetchall():
            e = dict(r)
            e["lines"] = [dict(x) for x in self.conn.execute(
                "SELECT l.*,a.name AS account_name FROM journal_lines l "
                "JOIN accounts a ON a.code=l.account_code WHERE l.entry_id=? "
                "ORDER BY l.line_no", (e["id"],)).fetchall()]
            out.append(e)
        return out

    # balances ---------------------------------------------------------------

    def _totals(self, start=None, end=None, exclude_types=(), only_types=()):
        sql = ["SELECT l.account_code AS code, SUM(l.debit) AS dr, SUM(l.credit) AS cr",
               "FROM journal_lines l JOIN journal_entries e ON e.id=l.entry_id",
               "WHERE 1=1"]
        p = []
        if start:
            sql.append("AND e.entry_date>=?")
            p.append(start)
        if end:
            sql.append("AND e.entry_date<=?")
            p.append(end)
        if only_types:
            ph = ",".join("?" * len(only_types))
            sql.append(f"AND e.entry_type IN ({ph})")
            p.extend(only_types)
        if exclude_types:
            ph = ",".join("?" * len(exclude_types))
            sql.append(f"AND e.entry_type NOT IN ({ph})")
            p.extend(exclude_types)
        sql.append("GROUP BY l.account_code")
        return {r["code"]: (r["dr"] or 0, r["cr"] or 0)
                for r in self.conn.execute(" ".join(sql), p).fetchall()}

    def account_balance(self, code, start=None, end=None):
        a = self.get_account(code)
        if not a:
            raise AccountingError(f"Unknown account {code}.")
        dr, cr = self._totals(start, end).get(str(code), (0, 0))
        raw = (dr - cr) if a["normal_balance"] == "DEBIT" else (cr - dr)
        return from_cents(raw)

    def general_ledger(self, code, start=None, end=None):
        a = self.get_account(code)
        if not a:
            raise AccountingError(f"Unknown account {code}.")

        opening = 0
        if start:
            prev = (date.fromisoformat(start) - timedelta(days=1)).isoformat()
            dr0, cr0 = self._totals(end=prev).get(str(code), (0, 0))
            opening = (dr0 - cr0) if a["normal_balance"] == "DEBIT" else (cr0 - dr0)

        sql = ("SELECT e.id AS entry_id,e.entry_date,e.description,e.reference,"
               "e.entry_type,l.debit,l.credit,l.memo FROM journal_lines l "
               "JOIN journal_entries e ON e.id=l.entry_id WHERE l.account_code=?")
        p = [str(code)]
        if start:
            sql += " AND e.entry_date>=?"
            p.append(start)
        if end:
            sql += " AND e.entry_date<=?"
            p.append(end)
        sql += " ORDER BY e.entry_date,e.id,l.line_no"

        rows = []
        run = opening
        for r in self.conn.execute(sql, p).fetchall():
            d = r["debit"] - r["credit"]
            run += d if a["normal_balance"] == "DEBIT" else -d
            rows.append({**dict(r), "balance_cents": run})
        return {"account": a, "opening_cents": opening, "rows": rows, "closing_cents": run}

    # trial balance ----------------------------------------------------------

    def trial_balance(self, as_of=None, exclude_types=()):
        totals = self._totals(end=as_of, exclude_types=exclude_types)
        rows = []
        tdr = tcr = 0
        for a in self.list_accounts():
            dr, cr = totals.get(a["code"], (0, 0))
            net = dr - cr
            if net == 0:
                continue
            if net > 0:
                rows.append({"account": a, "debit": from_cents(net), "credit": Decimal("0.00")})
                tdr += net
            else:
                rows.append({"account": a, "debit": Decimal("0.00"), "credit": from_cents(-net)})
                tcr += -net
        return {
            "as_of": as_of, "rows": rows,
            "total_debit": from_cents(tdr), "total_credit": from_cents(tcr),
            "balanced": tdr == tcr,
            "total_debit_cents": tdr, "total_credit_cents": tcr,
        }

    # worksheet --------------------------------------------------------------

    def worksheet(self, as_of=None):
        # 10 columns: TB, Adj, AdjTB, IS, BS (each Dr/Cr)
        t_tb = self._totals(end=as_of, exclude_types=("ADJUSTING", "REVERSING", "CLOSING"))
        t_adj = self._totals(end=as_of, only_types=("ADJUSTING",))

        rows = []
        T = dict(tb_dr=0, tb_cr=0, adj_dr=0, adj_cr=0, atb_dr=0, atb_cr=0,
                 is_dr=0, is_cr=0, bs_dr=0, bs_cr=0)

        for a in self.list_accounts():
            tb_dr, tb_cr = t_tb.get(a["code"], (0, 0))
            adj_dr, adj_cr = t_adj.get(a["code"], (0, 0))
            tb_net = tb_dr - tb_cr
            adj_net = adj_dr - adj_cr
            atb_net = tb_net + adj_net
            if tb_net == 0 and adj_net == 0:
                continue

            row = {
                "account": a,
                "tb_dr": max(tb_net, 0), "tb_cr": max(-tb_net, 0),
                "adj_dr": max(adj_net, 0), "adj_cr": max(-adj_net, 0),
                "atb_dr": max(atb_net, 0), "atb_cr": max(-atb_net, 0),
                "is_dr": 0, "is_cr": 0, "bs_dr": 0, "bs_cr": 0,
            }
            if a["type"] in ("INCOME", "EXPENSE"):
                row["is_dr"] = row["atb_dr"]
                row["is_cr"] = row["atb_cr"]
            else:
                row["bs_dr"] = row["atb_dr"]
                row["bs_cr"] = row["atb_cr"]

            rows.append(row)
            for k in T:
                T[k] += row[k]

        net = T["is_cr"] - T["is_dr"]
        net_is_dr = net_bs_cr = net_is_cr = net_bs_dr = 0
        if net > 0:
            net_is_dr = net
            net_bs_cr = net
        elif net < 0:
            net_is_cr = -net
            net_bs_dr = -net

        T["is_dr"] += net_is_dr
        T["is_cr"] += net_is_cr
        T["bs_dr"] += net_bs_dr
        T["bs_cr"] += net_bs_cr

        return {"as_of": as_of, "rows": rows, "net_income_cents": net,
                "net_is_dr": net_is_dr, "net_is_cr": net_is_cr,
                "net_bs_dr": net_bs_dr, "net_bs_cr": net_bs_cr, "totals": T}

    # income statement -------------------------------------------------------

    def _periodic_cogs(self, start, end):
        # periodic: COGS = Beg Inv + Net Purchases - End Inv
        t = self._totals(start, end, exclude_types=("CLOSING",))
        beg = self._totals(end=(date.fromisoformat(start) - timedelta(days=1)).isoformat())
        inv_dr, inv_cr = beg.get("1200", (0, 0))
        beg_inv_c = inv_dr - inv_cr

        purchases = t.get("5010", (0, 0))[0] - t.get("5010", (0, 0))[1]
        p_ret = t.get("5020", (0, 0))[1] - t.get("5020", (0, 0))[0]
        p_disc = t.get("5030", (0, 0))[1] - t.get("5030", (0, 0))[0]
        f_in = t.get("5040", (0, 0))[0] - t.get("5040", (0, 0))[1]
        net_purch = purchases + f_in - p_ret - p_disc
        tgas = beg_inv_c + net_purch

        inv_bal = self._totals(end=end).get("1200", (0, 0))
        end_inv = inv_bal[0] - inv_bal[1]
        cogs = tgas - end_inv

        return {
            "beginning_inventory": from_cents(beg_inv_c),
            "purchases": from_cents(purchases),
            "freight_in": from_cents(f_in),
            "purchase_returns": from_cents(p_ret),
            "purchase_discount": from_cents(p_disc),
            "net_purchases": from_cents(net_purch),
            "tgas": from_cents(tgas),
            "ending_inventory": from_cents(end_inv),
            "cogs": from_cents(cogs), "cogs_cents": cogs,
        }

    def income_statement(self, start, end):
        totals = self._totals(start, end, exclude_types=("CLOSING",))
        income = []
        expenses = []
        total_inc = total_exp = 0
        cogs_cents = 0
        periodic_cogs = None
        inv_system = self.get_setting("inventory_system", "PERPETUAL").upper()

        if inv_system == "PERIODIC":
            periodic_cogs = self._periodic_cogs(start, end)
            cogs_cents = periodic_cogs["cogs_cents"]
            # skip the 5xxx purchases -- they roll into COGS
            skip_codes = {"5000", "5010", "5020", "5030", "5040"}
        else:
            skip_codes = set()

        for a in self.list_accounts():
            dr, cr = totals.get(a["code"], (0, 0))
            if a["type"] == "INCOME":
                amt = cr - dr
                if amt:
                    income.append({"account": a, "amount": from_cents(amt)})
                    total_inc += amt
            elif a["type"] == "EXPENSE":
                if a["code"] in skip_codes:
                    continue
                amt = dr - cr
                if amt:
                    expenses.append({"account": a, "amount": from_cents(amt)})
                    total_exp += amt

        total_exp += cogs_cents
        net = total_inc - total_exp
        return {
            "start": start, "end": end,
            "revenue": income, "expenses": expenses,
            "total_revenue": from_cents(total_inc),
            "total_expenses": from_cents(total_exp),
            "net_income": from_cents(net),
            "total_revenue_cents": total_inc,
            "total_expenses_cents": total_exp,
            "net_income_cents": net,
            "periodic_cogs": periodic_cogs,
            "inventory_system": inv_system,
        }

    def changes_in_equity_statement(self, start, end):
        period = self.income_statement(start, end)
        begin = (date.fromisoformat(start) - timedelta(days=1)).isoformat()

        def snap(as_of):
            totals = self._totals(end=as_of)
            cap = re_ = 0
            for a in self.list_accounts():
                if a["type"] != "EQUITY":
                    continue
                dr, cr = totals.get(a["code"], (0, 0))
                if a["code"] in (RETAINED_EARNINGS, INCOME_SUMMARY):
                    re_ += cr - dr
                elif a["subtype"] == "CAPITAL":
                    cap += cr - dr
            earn = 0
            for a in self.list_accounts():
                dr, cr = totals.get(a["code"], (0, 0))
                if a["type"] == "INCOME":
                    earn += cr - dr
                elif a["type"] == "EXPENSE":
                    earn -= dr - cr
            return cap, re_ + earn

        cap_b, eq_b = snap(begin)
        cap_e, eq_e = snap(end)

        draws = 0
        totals = self._totals(start, end, exclude_types=("CLOSING",))
        for a in self.list_accounts():
            if a["subtype"] in ("DISTRIBUTION", "DRAWING"):
                dr, cr = totals.get(a["code"], (0, 0))
                draws += dr - cr

        return {
            "start": start, "end": end,
            "beginning_capital": from_cents(cap_b),
            "beginning_earnings": from_cents(eq_b),
            "beginning": from_cents(cap_b + eq_b),
            "net_income": period["net_income"],
            "distributions": from_cents(draws),
            "ending_capital": from_cents(cap_e),
            "ending_earnings": from_cents(eq_e),
            "ending": from_cents(cap_e + eq_e),
        }

    def retained_earnings_statement(self, start, end):
        return self.changes_in_equity_statement(start, end)

    def balance_sheet(self, as_of=None):
        totals = self._totals(end=as_of)
        assets = []
        liabilities = []
        equity = []
        ta = tl = te = 0
        cur_earn = 0
        inv_system = self.get_setting("inventory_system", "PERPETUAL").upper()

        for a in self.list_accounts():
            dr, cr = totals.get(a["code"], (0, 0))
            t = a["type"]
            if t == "ASSET":
                amt = dr - cr
                if amt:
                    assets.append({"account": a, "amount": from_cents(amt)})
                    ta += amt
            elif t == "LIABILITY":
                amt = cr - dr
                if amt:
                    liabilities.append({"account": a, "amount": from_cents(amt)})
                    tl += amt
            elif t == "EQUITY":
                amt = cr - dr
                if amt:
                    equity.append({"account": a, "amount": from_cents(amt)})
                    te += amt
            elif t == "INCOME":
                cur_earn += cr - dr
            elif t == "EXPENSE":
                # periodic COGS isn't posted -- skip purchases here
                if inv_system == "PERIODIC" and a["code"] in {"5000", "5010", "5020", "5030", "5040"}:
                    continue
                cur_earn -= dr - cr

        if cur_earn:
            equity.append({
                "account": {"code": "—", "name": "Current Period Earnings", "type": "EQUITY"},
                "amount": from_cents(cur_earn),
            })
            te += cur_earn

        return {
            "as_of": as_of,
            "assets": assets, "liabilities": liabilities, "equity": equity,
            "total_assets": from_cents(ta),
            "total_liabilities": from_cents(tl),
            "total_equity": from_cents(te),
            "total_liabilities_equity": from_cents(tl + te),
            "balanced": ta == tl + te,
            "total_assets_cents": ta,
            "total_liabilities_cents": tl,
            "total_equity_cents": te,
        }

    def _normal_cents(self, totals, a):
        dr, cr = totals.get(a["code"], (0, 0))
        return (dr - cr) if a["normal_balance"] == "DEBIT" else (cr - dr)

    def cash_flow_statement(self, start, end):
        begin = (date.fromisoformat(start) - timedelta(days=1)).isoformat()
        t_b = self._totals(end=begin)
        t_e = self._totals(end=end)
        t_p = self._totals(start, end, exclude_types=("CLOSING",))
        period = self.income_statement(start, end)
        net_income = period["net_income_cents"]
        accts = self.list_accounts()

        dep = 0
        for a in accts:
            if a["type"] == "EXPENSE" and a["subtype"] == "DEPRECIATION":
                dr, cr = t_p.get(a["code"], (0, 0))
                dep += dr - cr

        operating = [("Net income", net_income)]
        if dep:
            operating.append(("Depreciation", dep))
        investing = []
        financing = []

        for a in accts:
            if a["type"] not in ("ASSET", "LIABILITY", "EQUITY"):
                continue
            if a["cash_flow"] in ("CASH", "NONCASH"):
                continue
            if a["subtype"] in ("DISTRIBUTION", "DRAWING"):
                continue
            delta = self._normal_cents(t_e, a) - self._normal_cents(t_b, a)
            if delta == 0:
                continue
            impact = -delta if a["type"] == "ASSET" else delta
            lbl = f"{'Increase' if delta > 0 else 'Decrease'} in {a['name']}"
            bucket = {"OPERATING": operating, "INVESTING": investing,
                      "FINANCING": financing}.get(a["cash_flow"], operating)
            bucket.append((lbl, impact))

        for a in accts:
            if a["subtype"] in ("DISTRIBUTION", "DRAWING"):
                delta = self._normal_cents(t_e, a) - self._normal_cents(t_b, a)
                if delta:
                    financing.append(("Owner's drawings", -delta))

        cfo = sum(x for _, x in operating)
        cfi = sum(x for _, x in investing)
        cff = sum(x for _, x in financing)
        change = cfo + cfi + cff
        cb = sum(self._normal_cents(t_b, a) for a in accts if a["cash_flow"] == "CASH")
        ce = sum(self._normal_cents(t_e, a) for a in accts if a["cash_flow"] == "CASH")

        return {
            "start": start, "end": end,
            "operating": operating, "investing": investing, "financing": financing,
            "net_cash_operating": from_cents(cfo),
            "net_cash_investing": from_cents(cfi),
            "net_cash_financing": from_cents(cff),
            "net_change": from_cents(change),
            "cash_begin": from_cents(cb),
            "cash_end": from_cents(ce),
            "reconciled": (cb + change) == ce,
        }

    # closing ----------------------------------------------------------------

    @staticmethod
    def _mirror(account_code, dr, cr, memo):
        n = dr - cr
        if n > 0:
            return {"account": account_code, "credit": from_cents(n), "memo": memo}
        if n < 0:
            return {"account": account_code, "debit": from_cents(-n), "memo": memo}
        return None

    def _close_group(self, as_of, filt, desc, ref):
        totals = self._totals(end=as_of)
        lines = []
        sdr = scr = 0
        for a in self.list_accounts():
            if not filt(a):
                continue
            dr, cr = totals.get(a["code"], (0, 0))
            ln = self._mirror(a["code"], dr, cr, "Close")
            if ln:
                lines.append(ln)
                sdr += to_cents(ln.get("debit"))
                scr += to_cents(ln.get("credit"))
        if not lines:
            return None
        diff = sdr - scr
        if diff > 0:
            lines.append({"account": INCOME_SUMMARY, "credit": from_cents(diff)})
        elif diff < 0:
            lines.append({"account": INCOME_SUMMARY, "debit": from_cents(-diff)})
        return self.record_entry(as_of, desc, lines, reference=ref, entry_type="CLOSING")

    def close_period(self, as_of, reference=None):
        if not valid_date(as_of):
            raise AccountingError("Bad date.")
        created = []

        for eid in [
            self._close_group(as_of, lambda a: a["type"] == "INCOME",
                              "Closing — income to Income Summary", reference),
            self._close_group(as_of, lambda a: a["type"] == "EXPENSE",
                              "Closing — expenses to Income Summary", reference),
        ]:
            if eid:
                created.append(eid)

        t = self._totals(end=as_of)
        dr, cr = t.get(INCOME_SUMMARY, (0, 0))
        net = cr - dr
        if net:
            if net > 0:
                lines = [{"account": INCOME_SUMMARY, "debit": from_cents(net)},
                         {"account": RETAINED_EARNINGS, "credit": from_cents(net)}]
            else:
                lines = [{"account": INCOME_SUMMARY, "credit": from_cents(-net)},
                         {"account": RETAINED_EARNINGS, "debit": from_cents(-net)}]
            created.append(self.record_entry(
                as_of, f"Closing — Income Summary ({'income' if net > 0 else 'loss'})",
                lines, reference=reference, entry_type="CLOSING"))

        t = self._totals(end=as_of)
        dl = []
        sdr = scr = 0
        for a in self.list_accounts():
            if a["subtype"] not in ("DISTRIBUTION", "DRAWING"):
                continue
            dr, cr = t.get(a["code"], (0, 0))
            ln = self._mirror(a["code"], dr, cr, "Close")
            if ln:
                dl.append(ln)
                sdr += to_cents(ln.get("debit"))
                scr += to_cents(ln.get("credit"))
        if dl:
            diff = sdr - scr
            if diff > 0:
                dl.append({"account": RETAINED_EARNINGS, "credit": from_cents(diff)})
            elif diff < 0:
                dl.append({"account": RETAINED_EARNINGS, "debit": from_cents(-diff)})
            created.append(self.record_entry(as_of, "Closing — drawings/dividends",
                                             dl, reference=reference, entry_type="CLOSING"))
        return created

    def verify(self, as_of=None):
        problems = []
        bad = self.conn.execute(
            "SELECT e.id, SUM(l.debit) AS dr, SUM(l.credit) AS cr "
            "FROM journal_entries e JOIN journal_lines l ON l.entry_id=e.id "
            "GROUP BY e.id HAVING SUM(l.debit)<>SUM(l.credit)").fetchall()
        for r in bad:
            problems.append(f"Entry #{r['id']} out of balance.")
        bad = self.conn.execute(
            "SELECT id FROM journal_lines WHERE debit>0 AND credit>0").fetchall()
        for r in bad:
            problems.append(f"Line #{r['id']} has both D and C.")
        bs = self.balance_sheet(as_of)
        if not bs["balanced"]:
            problems.append("A ≠ L + E.")
        tb = self.trial_balance(as_of)
        if not tb["balanced"]:
            problems.append("TB not balanced.")
        return {"ok": not problems, "problems": problems}