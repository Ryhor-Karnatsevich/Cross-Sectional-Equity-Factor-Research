from Low_Volatility.config import (
    LOW_VOLATILITY_CACHE_DIR,
    LOW_VOLATILITY_RESULTS_DIR,
)
from research_storage import clear_current_research_outputs


def delete_research_layer_outputs():
    clear_current_research_outputs(
        (
            LOW_VOLATILITY_CACHE_DIR,
            LOW_VOLATILITY_RESULTS_DIR,
        )
    )
    print("Current Research Layer data and results deleted")


if __name__ == "__main__":
    delete_research_layer_outputs()
