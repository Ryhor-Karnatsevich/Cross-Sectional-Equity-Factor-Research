"""Declared rules for the S&P500 factor study, separate from extraction settings.

This module defines methodology only. Importing it performs no extraction,
portfolio calculation, filesystem mutation or regression. See METHODOLOGY.md.
"""
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ACCEPTED_INPUT_DIR = PROJECT_ROOT / "Data/Fama and french/Consolidated"
MARKET_DATA_DIR = PROJECT_ROOT / "Data/Data_System"
MODEL_DATA_DIR = PROJECT_ROOT / "Data/Fama and french/Models"
MODEL_RESULTS_DIR = PROJECT_ROOT / "Results/Fama_French/Models"

# -------------------------
# STUDY SCOPE
METHODOLOGY_VERSION = "sp500_ff_v1"
RULES_DEFINED_ON = "2026-11-23"
STUDY_START = "2009-07-01"
STUDY_END = "2026-06-30"
RETURN_FREQUENCY = "monthly"
BASE_CURRENCY = "USD"
UNIVERSE = "historical_sp500_members"
UNIVERSE_INFORMATION_LAG_SESSIONS = 1
COMPARISON_SAMPLE = "same_test_returns_and_intersection_of_valid_model_months"

# -------------------------
# ACCOUNTING DEFINITIONS
BOOK_EQUITY = {
    "metric": "common_equity",
    "positive_required": True,
    "parent_equity_fallback": False,
    "subtract_preferred_again": False,
    "add_deferred_taxes": False,
}
CHARACTERISTICS = {
    "size": {
        "metric": "market_cap",
        "formation_month": 6,
    },
    "book_to_market": {
        "numerator": "common_equity_fiscal_year_t_minus_1",
        "denominator": "market_cap_december_t_minus_1",
    },
    "operating_profitability": {
        "numerator_fields": ("revenue", "cost_of_sales", "sga", "interest_expense"),
        "formula": "(revenue - cost_of_sales - sga - interest_expense) / common_equity",
        "denominator_convention": "original_paper_book_equity_only",
        "all_expense_fields_required": True,
        "same_exact_fiscal_period_required": True,
    },
    "investment": {
        "formula": "total_assets_t_minus_1 / total_assets_t_minus_2 - 1",
        "positive_assets_required": True,
        "annual_period_spacing_days": (330, 400),
    },
    "momentum": {
        "formula": "product(1 + monthly_return[t-12:t-2]) - 1",
        "included_return_month_lags": tuple(range(2, 13)),
        "required_price_month_lags": tuple(range(2, 14)),
        "all_required_month_ends_observed": True,
        "formation_frequency": "monthly",
    },
}

# -------------------------
# INFORMATION DATES
ACCOUNTING_TIMING = {
    "fiscal_calendar_year_lag": 1,
    "minimum_publication_lag_calendar_days": 1,
    "cutoff": "available_from_on_or_before_last_june_trading_close",
    "vintage_selection": "latest_accepted_vintage_available_at_cutoff",
    "source_preference_on_same_publication_date": ("SEC", "LSEG"),
    "source_records": "observations_all.parquet",
    "allow_later_filings_to_rewrite_past_sort": False,
    "allow_fiscal_end_as_publication_date": False,
    "allow_undated_full_statement_values": False,
}

# -------------------------
# ELIGIBILITY AND SORTING
ELIGIBILITY = {
    "scope": "separate_for_each_sort_family",
    "book_to_market_required": ("common_equity", "december_market_cap", "june_market_cap"),
    "profitability_required": ("common_equity", "revenue", "cost_of_sales", "sga", "interest_expense", "june_market_cap"),
    "investment_required": ("total_assets_t_minus_1", "total_assets_t_minus_2", "june_market_cap"),
    "momentum_required": ("prior_2_to_12_month_returns", "previous_month_end_market_cap"),
    "minimum_accounting_firm_age_years": None,
    "require_survival_to_study_end": False,
}
SORTING = {
    "annual_formation_month": 6,
    "annual_hold_start_month": 7,
    "size_quantile": 0.50,
    "characteristic_quantiles": (0.30, 0.70),
    "quantile_interpolation": "linear",
    "breakpoint_universe": "eligible_sp500_issuers_for_each_sort_family",
    "independent_size_and_characteristic_sorts": True,
    "size_boundary": "small_if_size_le_median_else_big",
    "characteristic_boundary": "low_le_q30_middle_le_q70_else_high",
    "annual_characteristic_updates_between_june_sorts": False,
    "winsorize": False,
    "zscore": False,
    "empty_group_policy": "factor_month_missing_no_forced_rank_split",
}
ISSUER_POLICY = {
    "deduplicate_share_classes": True,
    "issuer_key_priority": ("accepted_CIK", "explicit_verified_same_issuer_crosswalk"),
    "unresolved_issuer_link": "exclude_and_log",
    "representative_security": "highest_trailing_60_session_valid_mean_dollar_volume",
    "minimum_liquidity_history_sessions": 20,
    "representative_tie_breaker": "ticker_ascending",
    "all_missing_liquidity_fallback": "ticker_ascending_among_current_eligible_securities",
    "capitalization": "company_level_once_per_issuer",
    "security_switching": "formation_or_verified_direct_rename_only",
}

# -------------------------
# PORTFOLIO RETURNS
PORTFOLIO_RULES = {
    "weights": "positive_previous_month_end_company_market_cap_normalized_within_group",
    "weight_reset": "monthly",
    "within_month_weights": "drift_with_realized_total_returns",
    "return_source": "existing_adjusted_price_total_return_proxy_after_price_quality_mask",
    "enter_new_index_members": "next_scheduled_sort_only",
    "exit_index_members": "first_close_after_membership_exit_is_observed_effective_next_session",
    "exit_proceeds": "risk_free_cash_until_next_scheduled_monthly_weight_reset",
    "missing_exit_price": "affected_leg_return_missing_and_log_unresolved_return",
    "missing_held_return": "affected_leg_return_missing_no_survivor_renormalization",
    "terminal_payout": "only_verified_explicit_total_return_or_payout_no_assumed_zero",
    "calendar_aggregation": "compound_daily_leg_returns_then_form_monthly_leg_differences",
    "stock_weight_cap": None,
    "sector_neutralization": False,
    "transaction_costs": "excluded_from_primary_gross_factor_returns",
    "concentration_check": "report_constituent_count_max_weight_hhi_effective_count_no_return_based_filter",
}
MISSING_DATA_RULES = {
    "accepted_inputs_only": True,
    "missing_accounting_value": "exclude_from_affected_sort_only",
    "missing_expense_is_zero": False,
    "negative_reported_expense": "retain_as_reported",
    "accounting_forward_fill_across_fiscal_years": False,
    "price_forward_fill": False,
    "cap_forward_fill": False,
    "currency_inference_or_conversion": False,
    "outcome_based_exclusions": False,
    "exclude_whole_month_for_all_models": "only_when_building_common_comparison_sample",
}

# -------------------------
# MARKET AND RISK-FREE RETURN
MARKET_RULES = {
    "universe": "historical_sp500_members_at_previous_close",
    "accounting_data_required": False,
    "weights": "previous_month_end_company_market_cap",
    "membership_updates": "at_each_observed_close_effective_next_session",
    "new_members_between_weight_resets": "enter_at_next_monthly_reset",
    "same_market_factor_in_all_models": True,
}
RISK_FREE_SOURCE = "KEN_FRENCH_MONTHLY_RF"
RISK_FREE_PATH = MODEL_DATA_DIR / "Inputs/french_monthly_rf.parquet"
RISK_FREE_RULES = {
    "unit": "monthly_decimal_return_convert_downloaded_percent_by_dividing_by_100",
    "missing_month": "model_month_missing_no_zero_fill",
    "dgs3mo_fallback": False,
    "source_url": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip",
    "download_during_configuration": False,
}

# -------------------------
# FACTOR FORMULAS AND MODEL SPECIFICATIONS
FACTOR_FORMULAS = {
    "SMB_BM": "mean(SL,SN,SH) - mean(BL,BN,BH)",
    "HML": "mean(SH,BH) - mean(SL,BL)",
    "SMB_OP": "mean(SW,SN,SR) - mean(BW,BN,BR)",
    "RMW": "mean(SR,BR) - mean(SW,BW)",
    "SMB_INV": "mean(SC,SN,SA) - mean(BC,BN,BA)",
    "CMA": "mean(SC,BC) - mean(SA,BA)",
    "SMB_5": "mean(SMB_BM,SMB_OP,SMB_INV)",
    "MOM": "mean(SWinner,BWinner) - mean(SLoser,BLoser)",
    "MKT_RF": "sp500_value_weight_market_return - monthly_RF",
}
MODEL_FACTORS = {
    "FF3_SP500": ("MKT_RF", "SMB_BM", "HML"),
    "CARHART4_SP500": ("MKT_RF", "SMB_BM", "HML", "MOM"),
    "FF5_SP500": ("MKT_RF", "SMB_5", "HML", "RMW", "CMA"),
}
