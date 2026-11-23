"""Copy this file to the university PC; open/sign in to LSEG Workspace and run.

Uses the historical CELG/ATVI RICs already used in successful price recovery.
Tests the old price-download interface first, then one historical annual input.
No project imports, header options, cache, downloads to disk or accounting cleanup.
Install dependencies into the selected interpreter: python -m pip install lseg-data
"""

import sys
import time
import traceback

print("LSEG SIMPLE TEST v2 - recovered CELG and ATVI", flush=True)
print("Python:", sys.executable, flush=True)

import lseg.data as ld

print("LSEG library:", getattr(ld, "__version__", "unknown"), flush=True)
started = time.perf_counter()

try:
    print("Opening Workspace session...", flush=True)
    ld.open_session()

    for ric in ["CELG.O^K19", "ATVI.O^J23"]:
        print(f"\n{ric}: historical prices, 2-10 January 2018", flush=True)
        before = time.perf_counter()
        try:
            prices = ld.get_history(
                universe=ric,
                fields=["TRDPRC_1", "ACVOL_UNS"],
                interval="1D",
                start="2018-01-02",
                end="2018-01-10",
                count=10000,
                adjustments="unadjusted",
            )
            print(prices, flush=True)
        except Exception:
            traceback.print_exc()
        print(f"Price request elapsed: {time.perf_counter() - before:.1f} seconds", flush=True)

        print(f"\n{ric}: annual revenue, fiscal year 2018", flush=True)
        before = time.perf_counter()
        try:
            revenue = ld.get_data(
                universe=[ric],
                fields=["TR.TotalRevenue"],
                parameters={"Period": "FY2018"},
            )
            print(revenue, flush=True)
        except Exception:
            traceback.print_exc()
        print(f"Revenue request elapsed: {time.perf_counter() - before:.1f} seconds", flush=True)
    print("\nRequests returned. Check the printed tables for actual values.", flush=True)
except Exception:
    traceback.print_exc()
finally:
    print(f"\nTotal elapsed: {time.perf_counter() - started:.1f} seconds", flush=True)
    try:
        ld.close_session()
    except Exception as error:
        print("Session close:", error, flush=True)
