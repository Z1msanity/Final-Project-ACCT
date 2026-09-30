# Anna's Coffee Corner demo data

def seed_demo(books):
    books.set_setting("company_name", "ANNA'S COFFEE CORNER")
    books.set_setting("business_type", "Merchandising/Trading")
    books.set_setting("org_type", "Sole Proprietorship")
    books.set_setting("inventory_system", "PERIODIC")

    txns = [
        ("2025-01-01", "Initial investment", "MEMO-001", [
            {"account": "1000", "debit": 100000}, {"account": "3000", "credit": 100000}]),
        ("2025-01-01", "Rent for 2 years", "MEMO-002", [
            {"account": "1300", "debit": 72000}, {"account": "1000", "credit": 72000}]),
        ("2025-01-04", "Purchase coffee machine", "MEMO-003", [
            {"account": "1500", "debit": 8000}, {"account": "1000", "credit": 8000}]),
        ("2025-01-04", "Purchase tables & chairs", "MEMO-004", [
            {"account": "1520", "debit": 3000}, {"account": "1000", "credit": 3000}]),
        ("2025-01-05", "Additional investment", "MEMO-005", [
            {"account": "1000", "debit": 30000}, {"account": "3000", "credit": 30000}]),
        ("2025-01-06", "Purchase coffee beans & cups", "MEMO-006", [
            {"account": "5010", "debit": 22000}, {"account": "1000", "credit": 22000}]),
        ("2025-01-06", "Purchase discount received", "MEMO-006", [
            {"account": "1000", "debit": 2000}, {"account": "5030", "credit": 2000}]),
        ("2025-01-06", "Freight-in paid", "MEMO-007", [
            {"account": "5040", "debit": 200}, {"account": "1000", "credit": 200}]),
        ("2025-01-07", "Purchase return", "MEMO-008", [
            {"account": "1000", "debit": 1000}, {"account": "5020", "credit": 1000}]),
        ("2025-01-10", "Cash sales", "INV-1001", [
            {"account": "1000", "debit": 7000}, {"account": "4000", "credit": 7000}]),
        ("2025-01-10", "Freight-out paid", "INV-1001", [
            {"account": "6610", "debit": 300}, {"account": "1000", "credit": 300}]),
        ("2025-01-11", "Sales return & refund", "INV-1002", [
            {"account": "4900", "debit": 600}, {"account": "1000", "credit": 600}]),
        ("2025-01-12", "Owner's withdrawal", "MEMO-009", [
            {"account": "3100", "debit": 2000}, {"account": "1000", "credit": 2000}]),
        ("2025-01-15", "Purchase beans & milk on account", "MEMO-010", [
            {"account": "5010", "debit": 3000}, {"account": "2000", "credit": 3000}]),
        ("2025-01-20", "Utilities paid", "MEMO-011", [
            {"account": "6200", "debit": 1200}, {"account": "1000", "credit": 1200}]),
        ("2025-01-30", "Loan from Metrobank", "MEMO-012", [
            {"account": "1000", "debit": 50000}, {"account": "2600", "credit": 50000}]),
        ("2025-01-30", "Sam's salary", "MEMO-013", [
            {"account": "6000", "debit": 10000}, {"account": "1000", "credit": 10000}]),
        ("2025-01-31", "Sale on account", "INV-1003", [
            {"account": "1100", "debit": 3000}, {"account": "4000", "credit": 3000}]),
    ]
    for d, desc, ref, lines in txns:
        books.record_entry(d, desc, lines, reference=ref)

    adjustments = [
        ("2025-01-31", "Adjust prepaid rent (1 month)", [
            {"account": "6100", "debit": 3000}, {"account": "1300", "credit": 3000}]),
        ("2025-01-31", "Depreciation - coffee machine", [
            {"account": "6400", "debit": 125}, {"account": "1510", "credit": 125}]),
        ("2025-01-31", "Depreciation - tables and chairs", [
            {"account": "6400", "debit": 125}, {"account": "1530", "credit": 125}]),
    ]
    for d, desc, lines in adjustments:
        books.record_entry(d, desc, lines, entry_type="ADJUSTING")

    books.set_setting("ending_inventory", "17200")