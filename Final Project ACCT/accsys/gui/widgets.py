# reusable GUI bits

import tkinter as tk
from tkinter import ttk


class ScrolledTree(ttk.Frame):
    def __init__(self, parent, columns, headings=None, widths=None,
                 anchor_right=(), weights=None, **kw):
        super().__init__(parent)
        self.columns = columns

        self._min_widths = list(widths) if widths else [100] * len(columns)
        self._weights = list(weights) if weights else list(self._min_widths)

        self.tree = ttk.Treeview(self, columns=columns, show="headings",
                                 selectmode="browse", **kw)
        for i, col in enumerate(columns):
            h = headings[i] if headings and i < len(headings) else col
            w = widths[i] if widths and i < len(widths) else 120
            anc = "e" if col in anchor_right else "w"
            self.tree.heading(col, text=h)
            self.tree.column(col, width=w, minwidth=w, anchor=anc, stretch=True)

        vs = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        hs = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # stretch columns when window is resized
        self.tree.bind("<Configure>", self._on_resize)

        self.tree.tag_configure("total", background="#eef4fb",
                                font=("Helvetica", 10, "bold"))
        self.tree.tag_configure("section", background="#f4f4f4",
                                font=("Helvetica", 10, "bold"))
        self.tree.tag_configure("negative", foreground="#b00")
        self.tree.tag_configure("muted", foreground="#666")
        self.tree.tag_configure("net", background="#fff6e5",
                                font=("Helvetica", 10, "bold"))

    def _on_resize(self, event=None):
        avail = self.tree.winfo_width()
        base_total = sum(self._min_widths)
        if avail < 10 or avail <= base_total:
            return
        extra = avail - base_total
        wsum = sum(self._weights) or 1
        for i, col in enumerate(self.columns):
            new_w = self._min_widths[i] + int(extra * self._weights[i] / wsum)
            self.tree.column(col, width=new_w)

    def clear(self):
        self.tree.delete(*self.tree.get_children())

    def add(self, values, tags=()):
        return self.tree.insert("", "end", values=values, tags=tags)