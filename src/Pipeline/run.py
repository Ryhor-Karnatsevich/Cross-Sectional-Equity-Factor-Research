import os
import subprocess
import sys
from time import perf_counter


PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

PIPELINE_STAGES = (
    (
        "Data System",
        os.path.join(PROJECT_ROOT, "src", "Data_System", "pipeline.py"),
    ),
    (
        "Factor Layer",
        os.path.join(PROJECT_ROOT, "src", "Factors_Layer", "pipeline.py"),
    ),
    (
        "Factor Selection Layer",
        os.path.join(
            PROJECT_ROOT,
            "src",
            "Factor_Selection_Layer",
            "pipeline.py",
        ),
    ),
    (
        "General Research",
        os.path.join(PROJECT_ROOT, "src", "Research_Layer", "pipeline.py"),
    ),
    (
        "Low Volatility Research",
        os.path.join(
            PROJECT_ROOT,
            "src",
            "Research_Layer",
            "Low_Volatility",
            "pipeline.py",
        ),
    ),
)


def format_duration(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{seconds:05.2f}"


def run_stage(name, script_path):
    if not os.path.isfile(script_path):
        raise FileNotFoundError(f"Pipeline stage is missing: {script_path}")

    print(f"\n{'=' * 72}")
    print(f"Starting: {name}")
    print(f"{'=' * 72}")
    started = perf_counter()

    subprocess.run(
        [sys.executable, "-u", script_path],
        cwd=PROJECT_ROOT,
        check=True,
    )

    elapsed = perf_counter() - started
    print(f"Completed: {name} ({format_duration(elapsed)})")
    return elapsed


def run_complete_pipeline():
    started = perf_counter()
    stage_times = {}

    try:
        for name, script_path in PIPELINE_STAGES:
            stage_times[name] = run_stage(name, script_path)
    except subprocess.CalledProcessError as error:
        failed_stage = next(
            (
                name
                for name, script_path in PIPELINE_STAGES
                if os.path.abspath(script_path)
                == os.path.abspath(error.cmd[-1])
            ),
            "Unknown stage",
        )
        print(f"\nComplete pipeline stopped: {failed_stage} failed")
        raise

    total = perf_counter() - started
    print(f"\n{'=' * 72}")
    print("Complete project pipeline is ready")
    for name, elapsed in stage_times.items():
        print(f"{name}: {format_duration(elapsed)}")
    print(f"Total time: {format_duration(total)}")
    return stage_times


if __name__ == "__main__":
    run_complete_pipeline()
