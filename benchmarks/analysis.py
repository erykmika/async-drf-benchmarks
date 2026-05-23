"""
Benchmark results collection and analysis utilities
"""

import json
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any


class BenchmarkResults:
    """
    Utility class for collecting and analyzing benchmark results
    """

    def __init__(self, variant: str, output_dir: str = "benchmark_results"):
        self.variant = variant
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.results: Dict[str, Any] = {
            "variant": variant,
            "timestamp": datetime.now().isoformat(),
            "metrics": [],
        }

    def add_metric(self, name: str, value: float, unit: str = "ms"):
        """Add a metric to the results"""
        self.results["metrics"].append({"name": name, "value": value, "unit": unit})

    def save_json(self, filename: str = None):
        """Save results as JSON"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"benchmark_{self.variant}_{timestamp}.json"

        filepath = self.output_dir / filename
        with open(filepath, "w") as f:
            json.dump(self.results, f, indent=2)
        return filepath

    def save_csv(self, filename: str = None):
        """Save results as CSV"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"benchmark_{self.variant}_{timestamp}.csv"

        filepath = self.output_dir / filename
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Metric", "Value", "Unit"])
            for metric in self.results["metrics"]:
                writer.writerow([metric["name"], metric["value"], metric["unit"]])
        return filepath


class ComplexityAnalyzer:
    """
    Utility class for analyzing code complexity using Radon
    """

    def __init__(self, output_dir: str = "complexity_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def analyze_file(self, filepath: str, variant: str):
        """Analyze complexity of a Python file"""
        try:
            import radon.complexity as complexity
            import radon.metrics as metrics

            with open(filepath, "r") as f:
                code = f.read()

            cc = complexity.cc_visit(code)

            # Handle different radon versions
            try:
                mi = metrics.mi_visit(code, multi=False)
            except TypeError:
                # Fallback for different radon versions
                mi = metrics.mi_visit(code)

            results = {
                "file": filepath,
                "variant": variant,
                "cyclomatic_complexity": cc,
                "maintainability_index": mi,
                "timestamp": datetime.now().isoformat(),
            }

            return results
        except ImportError:
            return None


def compare_variants(variant_s_results: Dict, variant_a_results: Dict) -> Dict:
    """
    Compare benchmark results between two variants
    """
    comparison = {
        "variant_s": variant_s_results,
        "variant_a": variant_a_results,
        "timestamp": datetime.now().isoformat(),
    }

    # Calculate performance difference
    for metric_s, metric_a in zip(variant_s_results.get("metrics", []), variant_a_results.get("metrics", [])):
        if metric_s["name"] == metric_a["name"]:
            diff = metric_a["value"] - metric_s["value"]
            percent_diff = (diff / metric_s["value"]) * 100 if metric_s["value"] != 0 else 0
            comparison[f"{metric_s['name']}_diff"] = {
                "absolute": diff,
                "percentage": percent_diff,
            }

    return comparison
