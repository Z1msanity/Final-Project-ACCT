# renders statement text into a tk.Text widget

def render_report_text(w, title, subtitle, sections, company=""):
    w.configure(state="normal")
    w.delete("1.0", "end")

    for name, cfg in [
        ("title", dict(font=("Courier New", 13, "bold"), justify="center")),
        ("company", dict(font=("Courier New", 11, "bold"), justify="center")),
        ("subtitle", dict(font=("Courier New", 10), justify="center")),
        ("heading", dict(font=("Courier New", 11, "bold"), justify="center")),
        ("section", dict(font=("Courier New", 10, "bold"), justify="center")),
        ("bold", dict(font=("Courier New", 10, "bold"), justify="center")),
        ("body", dict(font=("Courier New", 10), justify="center")),
        ("rule", dict(font=("Courier New", 10), justify="center")),
    ]:
        w.tag_configure(name, **cfg)

    width = 80

    def put(text, tag="body"):
        # pad/truncate to fixed width so justify=center works
        w.insert("end", text[:width].ljust(width) + "\n", tag)

    if company:
        put(company, "company")
    put(title, "title")
    if subtitle:
        put(subtitle, "subtitle")
    put("=" * width, "rule")

    for s in sections:
        k = s.get("type", "body")
        if k == "space":
            w.insert("end", "\n")
        elif k == "heading":
            put(s["text"], "heading")
        elif k == "section":
            put("  " + s["text"], "section")
        elif k in ("line", "indent", "total"):
            pad = "  " if k != "indent" else "    "
            style = "bold" if k == "total" else "body"
            put(f"{pad}{s['label'][:52]:<54}{s['amount']:>22}", style)
        elif k == "grand":
            put("=" * width, "rule")
            put(f"{s['label'][:62]:<58}{s['amount']:>22}", "bold")
            put("=" * width, "rule")
        elif k == "note":
            put(s["text"], "body")

    w.configure(state="disabled")