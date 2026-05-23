"""
Complexity Metrics Collector
Measures cyclomatic complexity (CC) and maintainability index (MI)
for views and serializers only (excluding config, migrations, tests)
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
from radon.complexity import cc_visit, cc_rank
from radon.metrics import mi_visit


class ComplexityMetrics:
    """Collects and analyzes complexity metrics for variant code"""

    def __init__(self, variant: str, output_dir: str = "benchmark_results"):
        self.variant = variant.upper()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        self.metrics = {
            "variant": self.variant,
            "timestamp": datetime.now().isoformat(),
            "files": [],
            "summary": {
                "total_files": 0,
                "avg_cc": 0,
                "avg_mi": 0,
                "total_functions": 0,
            },
        }

    def analyze_file(self, filepath: str) -> Dict[str, Any]:
        """Analyze complexity of a single Python file"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                code = f.read()

            # Get CC
            cc_results = cc_visit(code)

            # Get MI
            mi_result = mi_visit(code, multi=False)

            file_data = {
                "path": str(filepath),
                "maintainability_index": round(mi_result, 2),
                "functions": [],
            }

            total_cc = 0
            for func in cc_results:
                classname = getattr(func, "classname", None)
                func_data = {
                    "name": func.name,
                    "complexity": func.complexity,
                    "rank": cc_rank(func.complexity),
                    "classname": classname,
                }
                file_data["functions"].append(func_data)
                total_cc += func.complexity

            if cc_results:
                file_data["avg_complexity"] = round(total_cc / len(cc_results), 2)
            else:
                file_data["avg_complexity"] = 0

            return file_data

        except Exception as e:
            print(f"Error analyzing {filepath}: {e}")
            return None

    def scan_variant(self):
        """Scan variant-specific directories for views and serializers"""
        variant_path = Path(f"variant_{self.variant.lower()}")

        if not variant_path.exists():
            variant_path = Path(f"/app/variant_{self.variant.lower()}")

        if not variant_path.exists():
            import os

            cwd = Path.cwd()
            variant_path = cwd / f"variant_{self.variant.lower()}"

        if not variant_path.exists():
            print(f"Variant path {variant_path} does not exist")
            print(f"Current directory: {Path.cwd()}")
            print(f"Available directories: {list(Path.cwd().glob('variant_*'))}")
            return

        target_files = []

        # scan for views.py
        for file in variant_path.rglob("views*.py"):
            if "migration" not in str(file) and "__pycache__" not in str(file):
                target_files.append(file)

        # scan for serializers.py
        for file in variant_path.rglob("serializers.py"):
            if "migration" not in str(file) and "__pycache__" not in str(file):
                target_files.append(file)

        print(f"Found {len(target_files)} target files in {variant_path}")

        total_cc = 0
        total_functions = 0

        for filepath in target_files:
            print(f"Analyzing {filepath}...")
            file_metrics = self.analyze_file(filepath)

            if file_metrics:
                self.metrics["files"].append(file_metrics)
                total_cc += file_metrics.get("avg_complexity", 0)
                total_functions += len(file_metrics.get("functions", []))

        # Calculate summary statistics
        if self.metrics["files"]:
            self.metrics["summary"]["total_files"] = len(self.metrics["files"])
            self.metrics["summary"]["avg_cc"] = round(total_cc / len(self.metrics["files"]), 2)
            self.metrics["summary"]["total_functions"] = total_functions

            # Calculate average MI
            mis = [f.get("maintainability_index", 0) for f in self.metrics["files"]]
            if mis:
                self.metrics["summary"]["avg_mi"] = round(sum(mis) / len(mis), 2)

    def save_results(self, filename: str = None) -> Path:
        """Save complexity metrics to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"complexity_metrics_{self.variant}_{timestamp}.json"

        filepath = self.output_dir / filename
        with open(filepath, "w") as f:
            json.dump(self.metrics, f, indent=2)

        print(f"Complexity metrics saved to {filepath}")
        return filepath

    def print_summary(self):
        """Print summary to console"""
        summary = self.metrics["summary"]
        print("\n" + "=" * 60)
        print(f"Podsumowanie Metryk Złożoności dla Wariantu {self.variant}")
        print("=" * 60)
        print(f"Razem przeanalizowanych plików: {summary['total_files']}")
        print(f"Razem funkcji: {summary['total_functions']}")
        print(f"Średnia złożoność cyklomatyczna: {summary['avg_cc']}")
        print(f"Średni wskaźnik utrzymywalności: {summary['avg_mi']}")
        print("=" * 60 + "\n")


def run_complexity_analysis(variant: str, output_dir: str = "benchmark_results"):
    """Run complexity analysis for specified variant"""
    analyzer = ComplexityMetrics(variant, output_dir)
    analyzer.scan_variant()
    analyzer.save_results()
    analyzer.print_summary()
    return analyzer.metrics


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        variant = sys.argv[1].lower()
        if variant in ["s", "a"]:
            run_complexity_analysis(variant)
        else:
            print("Usage: python complexity_metrics.py [s|a]")
    else:
        print("Running complexity analysis for both variants...")
        run_complexity_analysis("s")
        run_complexity_analysis("a")
