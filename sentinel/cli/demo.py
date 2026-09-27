"""
Interactive Terminal Demo Runner for Sentinel.
Showcases the head-to-head live comparison for hackathon judges and evaluators.
"""

import argparse
import os
import sys
import time

from sentinel.benchmark.runner import run_comparative_benchmark
from sentinel.benchmark.scorecard import render_scorecard_table
from sentinel.benchmark.tasks import BENCHMARK_TASKS


def run_demo(fault_type: str = "truncated_diff"):
    print("\n" + "=" * 80)
    print("  SENTINEL — RELIABILITY & EVALUATION HARNESS FOR AI CODING AGENTS")
    print("  Hackathon Live Demonstration Engine")
    print("=" * 80)
    print(f"\n[INFO] Initializing comparative evaluation with fault injection: '{fault_type.upper()}'")
    print("[INFO] Total Benchmark Tasks:", len(BENCHMARK_TASKS))
    print("[INFO] Target Architecture: Small Open-Weight Model Scaffolding\n")

    time.sleep(0.5)

    print("-" * 80)
    print(">>> RUNNING HEAD-TO-HEAD COMPARATIVE BENCHMARK...")
    print("-" * 80)

    raw_results, sentinel_results = run_comparative_benchmark(
        tasks=BENCHMARK_TASKS,
        fault_type=fault_type,
    )

    for i, task in enumerate(BENCHMARK_TASKS):
        raw = raw_results[i]
        sent = sentinel_results[i]

        print(f"\n[TASK #{i+1}] {task.name}")
        print(f"  • Instruction: {task.instruction}")
        print(f"  • Fault Injected: {fault_type}")
        print(f"  • Raw Agent (No Harness):   Passed={raw['passed']} | False Claim={raw['false_claim']} | Recovered={raw['recovered']}")
        print(f"  • Sentinel (With Harness):  Passed={sent['passed']} | False Claim={sent['false_claim']} | Recovered={sent['recovered']} (Attempts={sent['attempts']})")

    # Render Grand Scorecard
    print("\n" + render_scorecard_table(raw_results, sentinel_results, fault_type=fault_type))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sentinel Live Demo Runner")
    parser.add_argument(
        "--fault",
        type=str,
        default="truncated_diff",
        choices=["truncated_diff", "syntax_corrupt", "none"],
        help="Type of fault to inject during benchmark",
    )
    args = parser.parse_args()
    run_demo(fault_type=args.fault)
