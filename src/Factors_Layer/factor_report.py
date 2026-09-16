import os
import tempfile

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from factor_config import (
    FACTOR_CONFIGS,
    FACTOR_SUMMARY_PATH,
    FACTOR_VARIANT_COUNT,
    FORWARD_HORIZONS,
)


def readable_family_name(family):
    return family.replace("_", " ").title()


def family_summary(metadata):
    rows = []

    for family, configurations in FACTOR_CONFIGS.items():
        variants = [configuration["variant"] for configuration in configurations]
        saved_variants = metadata.loc[
            metadata["family"].eq(family),
            "variant",
        ].tolist()
        if set(saved_variants) != set(variants):
            raise ValueError(f"Factor metadata does not match configuration: {family}")
        rows.append(
            {
                "family": family,
                "factor_family": readable_family_name(family),
                "configurations": len(variants),
                "variants": ", ".join(variants),
            }
        )

    return pd.DataFrame(rows)


def build_factor_report(metadata, run_metadata):
    if len(metadata) != FACTOR_VARIANT_COUNT:
        raise ValueError("Factor report requires complete factor metadata")

    families = family_summary(metadata)
    hypotheses = FACTOR_VARIANT_COUNT * len(FORWARD_HORIZONS)
    lines = [
        "# Factor Layer Report",
        "",
        "![Factor Layer summary](Figures/factor_layer_summary.png)",
        "",
        "## Build Snapshot",
        "",
        "| Metric | Result |",
        "| --- | ---: |",
        (
            f"| Equity period | {run_metadata['data_start']} to "
            f"{run_metadata['data_end']} |"
        ),
        f"| Trading dates | {run_metadata['trading_dates']:,} |",
        f"| Historical ticker columns | {run_metadata['ticker_columns']:,} |",
        f"| Factor families | {len(families):,} |",
        f"| Factor configurations | {FACTOR_VARIANT_COUNT:,} |",
        f"| Forward-return horizons | {len(FORWARD_HORIZONS):,} |",
        f"| Factor-horizon hypotheses | {hypotheses:,} |",
        (
            "| Winsorization applied | "
            f"{'yes' if run_metadata['winsorization_applied'] else 'no'} |"
        ),
        (
            "| Factor cache reused | "
            f"{'yes' if run_metadata['factor_cache_reused'] else 'no'} |"
        ),
        "",
        "## Factor Families",
        "",
        "| Factor family | Configurations | Variants |",
        "| --- | ---: | --- |",
    ]

    for row in families.itertuples(index=False):
        lines.append(
            f"| {row.factor_family} | {row.configurations} | {row.variants} |"
        )

    lines.extend(
        [
            "",
            "## Complete Factor Configurations",
            "",
            "| # | Factor family | Variant | Parameters |",
            "| ---: | --- | --- | --- |",
        ]
    )
    for number, row in enumerate(metadata.itertuples(index=False), start=1):
        parameters = str(row.parameters).replace("|", "\\|")
        lines.append(
            f"| {number} | {readable_family_name(row.family)} | "
            f"{row.variant} | `{parameters}` |"
        )

    lines.extend(
        [
            "",
            "## Forward-Return Horizons",
            "",
            "`" + "`, `".join(str(value) for value in FORWARD_HORIZONS) + "` trading days.",
            "",
            "## Interpretation",
            "",
            "This report describes the complete Factor Layer research grid. "
            "It confirms which factor variants and forward-return horizons were created, "
            "but it does not evaluate whether any factor predicts returns or produces alpha.",
            "",
        ]
    )
    return "\n".join(lines)


def create_factor_summary(
    metadata,
    run_metadata,
    output_path=FACTOR_SUMMARY_PATH,
):
    families = family_summary(metadata)
    hypotheses = FACTOR_VARIANT_COUNT * len(FORWARD_HORIZONS)
    colors = {
        "blue": "#2B6CB0",
        "green": "#2F855A",
        "purple": "#805AD5",
        "gray": "#4A5568",
        "light_gray": "#E2E8F0",
        "dark": "#1A202C",
    }

    figure, axes = plt.subplots(1, 3, figsize=(16, 6.5), facecolor="white")
    figure.subplots_adjust(
        top=0.78,
        bottom=0.11,
        left=0.08,
        right=0.97,
        wspace=0.38,
    )
    figure.suptitle(
        "Factor Layer Summary",
        fontsize=20,
        fontweight="bold",
        color=colors["dark"],
        y=0.97,
    )
    figure.text(
        0.5,
        0.885,
        (
            f"{run_metadata['data_start']} to {run_metadata['data_end']}  |  "
            f"{run_metadata['trading_dates']:,} trading dates  |  "
            f"{run_metadata['ticker_columns']:,} historical tickers"
        ),
        ha="center",
        fontsize=10,
        color=colors["gray"],
    )

    family_axis = axes[0]
    ordered = families.iloc[::-1]
    bars = family_axis.barh(
        ordered["factor_family"],
        ordered["configurations"],
        color=colors["blue"],
    )
    family_axis.bar_label(bars, padding=3, fontsize=9)
    family_axis.set_title("Configurations by family", fontweight="bold")
    family_axis.set_xlabel("Factor configurations")
    family_axis.spines[["top", "right", "left"]].set_visible(False)
    family_axis.grid(axis="x", color=colors["light_gray"], linewidth=0.8)
    family_axis.set_axisbelow(True)

    horizon_axis = axes[1]
    horizon_axis.set_title("Forward-return horizons", fontweight="bold")
    horizon_axis.set_xlim(0, 4)
    horizon_axis.set_ylim(0, 2)
    horizon_axis.axis("off")
    for position, horizon in enumerate(FORWARD_HORIZONS):
        column = position % 4
        row = 1 - position // 4
        x = column + 0.08
        y = row + 0.20
        box = FancyBboxPatch(
            (x, y),
            0.82,
            0.58,
            boxstyle="round,pad=0.03,rounding_size=0.06",
            facecolor="#EBF8FF",
            edgecolor=colors["blue"],
            linewidth=1.2,
        )
        horizon_axis.add_patch(box)
        horizon_axis.text(
            x + 0.41,
            y + 0.34,
            str(horizon),
            ha="center",
            va="center",
            fontsize=15,
            fontweight="bold",
            color=colors["blue"],
        )
        horizon_axis.text(
            x + 0.41,
            y + 0.12,
            "days",
            ha="center",
            va="center",
            fontsize=8,
            color=colors["gray"],
        )

    grid_axis = axes[2]
    grid_axis.set_title("Research grid", fontweight="bold")
    grid_axis.axis("off")
    metrics = (
        ("Factor families", len(families), colors["green"]),
        ("Factor configurations", FACTOR_VARIANT_COUNT, colors["blue"]),
        ("Forward horizons", len(FORWARD_HORIZONS), colors["purple"]),
        ("Factor-horizon hypotheses", hypotheses, "#DD6B20"),
        (
            "Saved matrices",
            FACTOR_VARIANT_COUNT + len(FORWARD_HORIZONS),
            colors["gray"],
        ),
    )
    for position, (label, value, color) in enumerate(metrics):
        y = 0.89 - position * 0.17
        grid_axis.text(
            0.04,
            y,
            label,
            transform=grid_axis.transAxes,
            fontsize=10,
            color=colors["gray"],
            va="center",
        )
        grid_axis.text(
            0.96,
            y,
            f"{value:,}",
            transform=grid_axis.transAxes,
            fontsize=17,
            fontweight="bold",
            color=color,
            ha="right",
            va="center",
        )
        if position < len(metrics) - 1:
            grid_axis.plot(
                [0.04, 0.96],
                [y - 0.075, y - 0.075],
                transform=grid_axis.transAxes,
                color=colors["light_gray"],
                linewidth=0.8,
            )

    directory = os.path.dirname(output_path)
    os.makedirs(directory, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix="factor_layer_summary_",
        suffix=".png",
        dir=directory,
    )
    os.close(descriptor)
    try:
        figure.savefig(
            temporary,
            dpi=160,
            bbox_inches="tight",
            facecolor="white",
        )
        os.replace(temporary, output_path)
    finally:
        plt.close(figure)
        if os.path.exists(temporary):
            os.remove(temporary)

    return output_path
