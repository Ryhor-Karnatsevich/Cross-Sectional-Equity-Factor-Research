from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "Data" / "Fama and french"
UNIVERSE_PATH = PROJECT_ROOT / "Data" / "Data_System" / "Raw" / "universe.csv"
FIRST_FISCAL_YEAR = 2006  # Two preceding years for research beginning in 2008.
LAST_FISCAL_YEAR = 2025
REQUEST_INTERVAL_SECONDS = 0.35

# These are source concepts, not a final Fama-French book-equity definition.
# All candidate values, dates, units and filing vintages are retained.
CONCEPTS = {
    "total_assets": {"us-gaap": ("Assets",), "ifrs-full": ("Assets",)},
    "equity_parent": {
        "us-gaap": ("StockholdersEquity",),
        "ifrs-full": ("EquityAttributableToOwnersOfParent",),
    },
    "equity_including_minority": {
        "us-gaap": ("StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",),
        "ifrs-full": ("Equity",),
    },
    "common_equity": {"us-gaap": ("CommonStockholdersEquity",)},
    "preferred_equity": {"us-gaap": (
        "PreferredStockValue", "PreferredStockCarryingValue", "PreferredStockRedemptionValue",
    )},
    "minority_interest": {
        "us-gaap": ("MinorityInterest",),
        "ifrs-full": ("NoncontrollingInterests",),
    },
    "deferred_tax_and_credits": {"us-gaap": ("DeferredIncomeTaxesAndTaxCredits",)},
    "revenue": {
        "us-gaap": ("RevenueFromContractWithCustomerExcludingAssessedTax",
                    "RevenueFromContractWithCustomerIncludingAssessedTax", "Revenues", "SalesRevenueNet"),
        "ifrs-full": ("Revenue",),
    },
    "cost_of_sales": {
        "us-gaap": ("CostOfGoodsAndServicesSold", "CostOfRevenue", "CostOfGoodsSold"),
        "ifrs-full": ("CostOfSales",),
    },
    "sga": {
        "us-gaap": ("SellingGeneralAndAdministrativeExpense",),
        "ifrs-full": ("SellingGeneralAndAdministrativeExpense",),
    },
    "interest_expense": {
        "us-gaap": ("InterestExpenseNonOperating", "InterestExpenseNonoperating",
                    "InterestExpense", "InterestAndDebtExpense"),
        "ifrs-full": ("InterestExpense", "FinanceCosts"),
    },
    # Share observations support later investigation; they are not market cap.
    "shares_outstanding": {
        "us-gaap": ("CommonStockSharesOutstanding",),
        "dei": ("EntityCommonStockSharesOutstanding",),
        "ifrs-full": ("NumberOfSharesOutstanding",),
    },
}
FLOW_METRICS = {"revenue", "cost_of_sales", "sga", "interest_expense"}
ANNUAL_FORMS = {"10-K", "10-K/A", "10-KT", "10-KT/A", "20-F", "20-F/A", "40-F", "40-F/A"}
