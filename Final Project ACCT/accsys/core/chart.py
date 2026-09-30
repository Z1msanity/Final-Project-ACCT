# default chart of accounts
# codes: 1xxx assets, 2xxx liabs, 3xxx equity, 4xxx income, 5xxx/6xxx expenses

from .constants import INCOME_SUMMARY, RETAINED_EARNINGS

DEFAULT_CHART = [
    ("1000", "Cash", "ASSET", "CURRENT", "DEBIT", "CASH"),
    ("1010", "Petty Cash", "ASSET", "CURRENT", "DEBIT", "CASH"),
    ("1100", "Accounts Receivable", "ASSET", "CURRENT", "DEBIT", "OPERATING"),
    ("1200", "Inventory", "ASSET", "CURRENT", "DEBIT", "OPERATING"),
    ("1300", "Prepaid Rent", "ASSET", "CURRENT", "DEBIT", "OPERATING"),
    ("1310", "Prepaid Expenses", "ASSET", "CURRENT", "DEBIT", "OPERATING"),
    ("1400", "Office Supplies", "ASSET", "CURRENT", "DEBIT", "OPERATING"),

    ("1500", "Equipment - Coffee Machine", "ASSET", "NONCURRENT", "DEBIT", "INVESTING"),
    ("1510", "Accumulated Depreciation - Coffee Machine", "ASSET", "CONTRA", "CREDIT", "NONCASH"),
    ("1520", "Equipment - Tables and Chairs", "ASSET", "NONCURRENT", "DEBIT", "INVESTING"),
    ("1530", "Accumulated Depreciation - Tables and Chairs", "ASSET", "CONTRA", "CREDIT", "NONCASH"),
    ("1600", "Building", "ASSET", "NONCURRENT", "DEBIT", "INVESTING"),
    ("1610", "Accumulated Depreciation - Building", "ASSET", "CONTRA", "CREDIT", "NONCASH"),
    ("1700", "Land", "ASSET", "NONCURRENT", "DEBIT", "INVESTING"),

    ("1800", "Trademarks", "ASSET", "INTANGIBLE", "DEBIT", "INVESTING"),
    ("1810", "Brand Name", "ASSET", "INTANGIBLE", "DEBIT", "INVESTING"),

    ("2000", "Accounts Payable", "LIABILITY", "CURRENT", "CREDIT", "OPERATING"),
    ("2100", "Salaries Payable", "LIABILITY", "CURRENT", "CREDIT", "OPERATING"),
    ("2200", "Taxes Payable", "LIABILITY", "CURRENT", "CREDIT", "OPERATING"),
    ("2300", "Utilities Payable", "LIABILITY", "CURRENT", "CREDIT", "OPERATING"),
    ("2400", "Unearned Income", "LIABILITY", "CURRENT", "CREDIT", "OPERATING"),
    ("2500", "Short-term Loans Payable", "LIABILITY", "CURRENT", "CREDIT", "FINANCING"),

    ("2600", "Loans Payable", "LIABILITY", "NONCURRENT", "CREDIT", "FINANCING"),
    ("2700", "Mortgage Payable", "LIABILITY", "NONCURRENT", "CREDIT", "FINANCING"),

    ("3000", "Owner's Capital", "EQUITY", "CAPITAL", "CREDIT", "FINANCING"),
    ("3100", "Drawings", "EQUITY", "DRAWING", "DEBIT", "FINANCING"),
    ("3200", "Common Stock", "EQUITY", "CAPITAL", "CREDIT", "FINANCING"),
    ("3300", "Additional Paid-In Capital", "EQUITY", "CAPITAL", "CREDIT", "FINANCING"),
    (RETAINED_EARNINGS, "Retained Earnings", "EQUITY", "RETAINED", "CREDIT", "NONCASH"),
    ("3800", "Dividends", "EQUITY", "DISTRIBUTION", "DEBIT", "FINANCING"),
    (INCOME_SUMMARY, "Income Summary", "EQUITY", "RETAINED", "CREDIT", "NONCASH"),

    ("4000", "Sales", "INCOME", "OPERATING", "CREDIT", "OPERATING"),
    ("4100", "Service Income", "INCOME", "OPERATING", "CREDIT", "OPERATING"),
    ("4200", "Professional Fees", "INCOME", "OPERATING", "CREDIT", "OPERATING"),
    ("4900", "Sales Returns and Allowances", "INCOME", "CONTRA", "DEBIT", "OPERATING"),
    ("4910", "Sales Discounts", "INCOME", "CONTRA", "DEBIT", "OPERATING"),

    # periodic purchases
    ("5000", "Cost of Goods Sold", "EXPENSE", "COGS", "DEBIT", "OPERATING"),
    ("5010", "Purchases", "EXPENSE", "PURCHASES", "DEBIT", "OPERATING"),
    ("5020", "Purchase Returns and Allowances", "EXPENSE", "CONTRA_PURCH", "CREDIT", "OPERATING"),
    ("5030", "Purchase Discount", "EXPENSE", "CONTRA_PURCH", "CREDIT", "OPERATING"),
    ("5040", "Freight-in", "EXPENSE", "PURCHASES", "DEBIT", "OPERATING"),

    ("6000", "Salaries Expense", "EXPENSE", "OPERATING", "DEBIT", "OPERATING"),
    ("6100", "Rent Expense", "EXPENSE", "OPERATING", "DEBIT", "OPERATING"),
    ("6200", "Utilities Expense", "EXPENSE", "OPERATING", "DEBIT", "OPERATING"),
    ("6300", "Supplies Expense", "EXPENSE", "OPERATING", "DEBIT", "OPERATING"),
    ("6400", "Depreciation Expense", "EXPENSE", "DEPRECIATION", "DEBIT", "NONCASH"),
    ("6500", "Insurance Expense", "EXPENSE", "OPERATING", "DEBIT", "OPERATING"),
    ("6600", "Advertising Expense", "EXPENSE", "OPERATING", "DEBIT", "OPERATING"),
    ("6610", "Freight-out", "EXPENSE", "SELLING", "DEBIT", "OPERATING"),
    ("6700", "Taxes and Licenses", "EXPENSE", "TAX", "DEBIT", "OPERATING"),
    ("6800", "Interest Expense", "EXPENSE", "OPERATING", "DEBIT", "OPERATING"),
    ("6900", "Income Tax Expense", "EXPENSE", "TAX", "DEBIT", "OPERATING"),
]