"""
Performance Metrics Aggregator
aggregates results from multiple benchmark runs (3 repetitions)
performs statistical analysis and generates reports
"""

import csv
import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple
from scipy.stats import mannwhitneyu
import matplotlib.pyplot as plt


class MetricsAggregator:
    """Aggregates and analyzes benchmark metrics"""

    def __init__(self, results_dir: str = "benchmark_results"):
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(exist_ok=True, parents=True)
        self.aggregated = {
            "timestamp": datetime.now().isoformat(),
            "variants": {},
        }

    def load_response_times(self, variant: str, group: str, user_count: int) -> List[float]:
        """Load all response times from CSV files"""
        pattern = f"locust_responses_{variant}_{group}_{user_count}_users*.csv"
        files = list(self.results_dir.glob(pattern))

        response_times = []

        for file in files:
            try:
                with open(file, "r", newline="") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        rt = float(row["response_time_ms"])
                        response_times.append(rt)
            except Exception:
                continue

        return response_times

    def mann_whitney_test(self, group: str, user_count: int, alpha: float = 0.05) -> Dict[str, Any]:

        sync_times = self.load_response_times("s", group, user_count)
        async_times = self.load_response_times("a", group, user_count)

        if not sync_times or not async_times:
            return {"error": "Missing data"}

        statistic, p_value = mannwhitneyu(sync_times, async_times, alternative="two-sided")

        sync_median = statistics.median(sync_times)
        async_median = statistics.median(async_times)

        result = {
            "group": str(group),
            "user_count": int(user_count),
            "u_statistic": float(statistic),
            "p_value": float(p_value),
            "significant": bool(p_value < alpha),
            "alpha": float(alpha),
            "sync_median": float(sync_median),
            "async_median": float(async_median),
        }

        return result

    def run_hypothesis_tests(self):
        """Run Mann-Whitney tests for all scenarios"""

        groups = ["cpu", "io", "mixed"]
        user_counts = [10, 50, 200]

        self.aggregated["hypothesis_tests"] = {}

        for group in groups:
            self.aggregated["hypothesis_tests"][group] = {}

            for user_count in user_counts:
                result = self.mann_whitney_test(group, user_count)
                self.aggregated["hypothesis_tests"][group][user_count] = result

    def load_locust_metrics(self, variant: str, user_count: int, run_number: int = None) -> Dict[str, Any]:
        """Load Locust metrics from JSON file"""
        if run_number:
            pattern = f"locust_metrics_{variant}_*_{user_count}_users_run{run_number}.json"
        else:
            pattern = f"locust_metrics_{variant}_*_{user_count}_users.json"

        files = list(self.results_dir.glob(pattern))

        if files:
            with open(files[0], "r") as f:
                return json.load(f)
        return None

    def _discover_locust_files_by_group(self, variant: str, user_count: int) -> Dict[str, List[Path]]:
        """Discover locust metrics files for a variant/user_count and group them by endpoint type.

        Grouping rules (filename based):
        - locust_metrics_{variant}_{group}_{user_count}_users[_runX].json  -> group is the segment
        - locust_metrics_{variant}_{user_count}_users[_runX].json         -> group 'all' (no group segment)

        Returns a mapping group -> list[Path]
        """
        pattern = f"locust_metrics_{variant}_*_{user_count}_users*.json"
        files = list(self.results_dir.glob(pattern))

        groups: Dict[str, List[Path]] = {}

        for p in files:
            name = p.name
            parts = name.split("_")

            group = None
            # Expecting patterns like: locust_metrics_s_cpu_10_users_run1.json
            # parts -> ['locust','metrics','s','cpu','10','users','run1.json']
            if len(parts) >= 5:
                candidate = parts[3]
                # if candidate looks like a number, then no group segment was present
                if not candidate.isdigit():
                    group = candidate

            if not group:
                group = "all"

            groups.setdefault(group, []).append(p)

        return groups

    def _load_metrics_from_paths(self, paths: List[Path]) -> List[Dict[str, Any]]:
        """Load JSON metrics from a list of file paths. Returns list of parsed JSON dicts."""
        results = []
        for p in sorted(paths):
            try:
                with open(p, "r") as f:
                    results.append(json.load(f))
            except Exception:
                print(f"Unreadable file: {p}")
                continue
        return results

    def load_complexity_metrics(self, variant: str) -> Dict[str, Any]:
        """Load complexity metrics for variant"""
        files = list(self.results_dir.glob(f"complexity_metrics_{variant.upper()}_*.json"))
        if files:
            # Load the most recent
            files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            with open(files[0], "r") as f:
                return json.load(f)
        return None

    def aggregate_locust_runs(self, variant: str, user_counts: List[int] = None) -> Dict[str, Any]:
        """Aggregate Locust results across multiple runs"""
        if user_counts is None:
            user_counts = [10, 50, 200]

        variant_data = {
            "locust_metrics": {},
            "psutil_metrics": {},
            "complexity_metrics": None,
        }

        # Load complexity metrics once per variant
        complexity = self.load_complexity_metrics(variant)
        if complexity:
            variant_data["complexity_metrics"] = complexity

        # Aggregate for each user count
        for user_count in user_counts:
            # Discover files grouped by endpoint type (cpu/io/mixed or 'all')
            groups = self._discover_locust_files_by_group(variant, user_count)

            if not groups:
                print(f"No metrics found for {variant} with {user_count} users")
                continue

            # For each discovered group, load all matching files and aggregate
            per_group_aggregated: Dict[str, Any] = {}

            for group_name, paths in groups.items():
                runs = self._load_metrics_from_paths(paths)
                if not runs:
                    continue
                agg = self._aggregate_performance_metrics(runs, variant, user_count)
                per_group_aggregated[group_name] = agg

            # Also provide an "all" aggregation across all groups/files
            all_paths = [p for paths in groups.values() for p in paths]
            all_runs = self._load_metrics_from_paths(all_paths)
            if all_runs:
                per_group_aggregated["all"] = self._aggregate_performance_metrics(all_runs, variant, user_count)

            # Store grouped metrics; keep backwards-compatible access via ['all']
            variant_data["locust_metrics"][user_count] = per_group_aggregated

        return variant_data

    def _aggregate_performance_metrics(self, results_list: List[Dict], variant: str, user_count: int) -> Dict[str, Any]:
        """Aggregate performance metrics from multiple runs"""
        if not results_list:
            return {}

        # Extract metrics from each run
        throughputs = [r["performance_metrics"]["throughput_req_per_sec"] for r in results_list]
        p50s = [r["performance_metrics"]["response_time_p50_ms"] for r in results_list]
        p95s = [r["performance_metrics"]["response_time_p95_ms"] for r in results_list]
        p99s = [r["performance_metrics"]["response_time_p99_ms"] for r in results_list]
        error_rates = [r["performance_metrics"]["error_rate_percent"] for r in results_list]

        return {
            "run_count": len(results_list),
            "throughput": {
                "values": throughputs,
                "mean": round(statistics.mean(throughputs), 2),
                "median": round(statistics.median(throughputs), 2),
                "stdev": round(statistics.stdev(throughputs), 2) if len(throughputs) > 1 else 0,
            },
            "response_time_p50_ms": {
                "values": p50s,
                "mean": round(statistics.mean(p50s), 2),
                "median": round(statistics.median(p50s), 2),
                "stdev": round(statistics.stdev(p50s), 2) if len(p50s) > 1 else 0,
            },
            "response_time_p95_ms": {
                "values": p95s,
                "mean": round(statistics.mean(p95s), 2),
                "median": round(statistics.median(p95s), 2),
                "stdev": round(statistics.stdev(p95s), 2) if len(p95s) > 1 else 0,
            },
            "response_time_p99_ms": {
                "values": p99s,
                "mean": round(statistics.mean(p99s), 2),
                "median": round(statistics.median(p99s), 2),
                "stdev": round(statistics.stdev(p99s), 2) if len(p99s) > 1 else 0,
            },
            "error_rate_percent": {
                "values": error_rates,
                "mean": round(statistics.mean(error_rates), 2),
                "median": round(statistics.median(error_rates), 2),
                "stdev": round(statistics.stdev(error_rates), 2) if len(error_rates) > 1 else 0,
            },
        }

    def save_aggregated_json(self, filename: str = "aggregated_results.json") -> Path:
        """Save aggregated results to JSON"""
        filepath = self.results_dir / filename
        with open(filepath, "w") as f:
            json.dump(self.aggregated, f, indent=2)
        print(f"Aggregated results saved to {filepath}")
        return filepath

    def save_comparison_csv(self, filename: str = "comparison_results.csv") -> Path:
        """Save comparison table as CSV"""
        filepath = self.results_dir / filename
        user_counts = [10, 50, 200]

        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)

            # Header
            writer.writerow(
                [
                    "Liczba użytkowników",
                    "Wariant",
                    "Grupa punktu końcowego",
                    "Metryka",
                    "Średnia",
                    "Mediana",
                    "Odchylenie standardowe",
                    "Jednostka",
                ]
            )

            for user_count in user_counts:
                for variant in ["S", "A"]:
                    if variant in self.aggregated["variants"] and user_count in self.aggregated["variants"][
                        variant
                    ].get("locust_metrics", {}):
                        metrics = self.aggregated["variants"][variant]["locust_metrics"][user_count]

                        # Backwards compat: metrics may be an aggregation dict by group
                        metrics_all = metrics.get("all", metrics)

                        # Throughput row (all)
                        writer.writerow(
                            [
                                user_count,
                                f"Wariant {variant}",
                                "wszystko",
                                "Przepustowość",
                                metrics_all["throughput"]["mean"],
                                metrics_all["throughput"]["median"],
                                metrics_all["throughput"]["stdev"],
                                "req/s",
                            ]
                        )

                        # P50 row
                        writer.writerow(
                            [
                                "",
                                "",
                                "",
                                "Czas odpowiedzi P50",
                                metrics_all["response_time_p50_ms"]["mean"],
                                metrics_all["response_time_p50_ms"]["median"],
                                metrics_all["response_time_p50_ms"]["stdev"],
                                "ms",
                            ]
                        )

                        # P95 row
                        writer.writerow(
                            [
                                "",
                                "",
                                "",
                                "Czas odpowiedzi P95",
                                metrics_all["response_time_p95_ms"]["mean"],
                                metrics_all["response_time_p95_ms"]["median"],
                                metrics_all["response_time_p95_ms"]["stdev"],
                                "ms",
                            ]
                        )

                        # P99 row
                        writer.writerow(
                            [
                                "",
                                "",
                                "",
                                "Czas odpowiedzi P99",
                                metrics_all["response_time_p99_ms"]["mean"],
                                metrics_all["response_time_p99_ms"]["median"],
                                metrics_all["response_time_p99_ms"]["stdev"],
                                "ms",
                            ]
                        )

                        # Error rate row
                        writer.writerow(
                            [
                                "",
                                "",
                                "",
                                "Wskaźnik błędów",
                                metrics_all["error_rate_percent"]["mean"],
                                metrics_all["error_rate_percent"]["median"],
                                metrics_all["error_rate_percent"]["stdev"],
                                "%",
                            ]
                        )

                        # If grouped metrics exist, also write per-group rows
                        if isinstance(metrics, dict) and len(metrics) > 1:
                            for group_name, group_metrics in sorted(metrics.items()):
                                if group_name == "all":
                                    continue

                                # Throughput row (group)
                                writer.writerow(
                                    [
                                        user_count,
                                        f"Wariant {variant}",
                                        group_name,
                                        "Przepustowość",
                                        group_metrics["throughput"]["mean"],
                                        group_metrics["throughput"]["median"],
                                        group_metrics["throughput"]["stdev"],
                                        "req/s",
                                    ]
                                )

                                # P50 / P95 / P99 / Error rows for the group
                                writer.writerow(
                                    [
                                        "",
                                        "",
                                        "",
                                        "Czas odpowiedzi P50",
                                        group_metrics["response_time_p50_ms"]["mean"],
                                        group_metrics["response_time_p50_ms"]["median"],
                                        group_metrics["response_time_p50_ms"]["stdev"],
                                        "ms",
                                    ]
                                )
                                writer.writerow(
                                    [
                                        "",
                                        "",
                                        "",
                                        "Czas odpowiedzi P95",
                                        group_metrics["response_time_p95_ms"]["mean"],
                                        group_metrics["response_time_p95_ms"]["median"],
                                        group_metrics["response_time_p95_ms"]["stdev"],
                                        "ms",
                                    ]
                                )
                                writer.writerow(
                                    [
                                        "",
                                        "",
                                        "",
                                        "Czas odpowiedzi P99",
                                        group_metrics["response_time_p99_ms"]["mean"],
                                        group_metrics["response_time_p99_ms"]["median"],
                                        group_metrics["response_time_p99_ms"]["stdev"],
                                        "ms",
                                    ]
                                )
                                writer.writerow(
                                    [
                                        "",
                                        "",
                                        "",
                                        "Wskaźnik błędów",
                                        group_metrics["error_rate_percent"]["mean"],
                                        group_metrics["error_rate_percent"]["median"],
                                        group_metrics["error_rate_percent"]["stdev"],
                                        "%",
                                    ]
                                )

        print(f"Comparison CSV saved to {filepath}")
        return filepath

    def generate_charts(self) -> List[Path]:
        """Generate comparison charts"""

        charts = []
        user_counts = [10, 50, 200]
        metrics_to_plot = [
            ("throughput", "Przepustowość (req/s)", "Żądań na sekundę"),
            ("response_time_p50_ms", "Czas odpowiedzi P50 (ms)", "Milisekundy"),
            ("response_time_p95_ms", "Czas odpowiedzi P95 (ms)", "Milisekundy"),
            ("response_time_p99_ms", "Czas odpowiedzi P99 (ms)", "Milisekundy"),
        ]

        for metric_key, metric_label, unit in metrics_to_plot:
            # Determine available groups across variants (e.g., cpu, io, mixed, all)
            groups = set()
            for variant in ["S", "A"]:
                vdata = self.aggregated.get("variants", {}).get(variant, {})
                for uc, metrics in vdata.get("locust_metrics", {}).items():
                    if isinstance(metrics, dict) and "all" in metrics:
                        groups.update(metrics.keys())
                    else:
                        # legacy single-aggregation
                        groups.add("all")

            if not groups:
                groups = {"all"}

            for group in sorted(groups):
                fig, ax = plt.subplots(figsize=(12, 6))

                x_pos = 0
                x_labels = []
                x_ticks = []

                for user_count in user_counts:
                    for variant in ["S", "A"]:
                        vdata = self.aggregated.get("variants", {}).get(variant, {})
                        if user_count not in vdata.get("locust_metrics", {}):
                            continue

                        metrics = vdata["locust_metrics"][user_count]

                        # If metrics are grouped, pick the group's aggregation; otherwise use metrics directly
                        if isinstance(metrics, dict) and "all" in metrics:
                            group_metrics = metrics.get(group, {})
                        else:
                            group_metrics = metrics

                        value = group_metrics.get(metric_key, {}).get("median", 0)

                        bar = ax.bar(x_pos, value, width=0.35, label=f"Wariant {variant}")

                        for b in bar:
                            ax.text(
                                b.get_x() + b.get_width() / 2,
                                b.get_height(),
                                f"{b.get_height():.1f}",
                                ha="center",
                                va="bottom",
                                fontsize=9
                            )

                        x_labels.append(f"{user_count} użytkowników\n{variant}")
                        x_ticks.append(x_pos)
                        x_pos += 0.4

                    x_pos += 0.2  # Space between user count groups

                ax.set_xlabel("Liczba użytkowników", fontsize=12)
                ax.set_ylabel(unit, fontsize=12)
                ax.set_title(f"Porównanie wydajności: {metric_label} ({group})", fontsize=14)
                ax.set_xticks(x_ticks)
                ax.set_xticklabels(x_labels)
                ax.grid(True, alpha=0.3)

                # Keep original filename for the 'all' group for backward compatibility
                if group == "all":
                    chart_file = self.results_dir / f"chart_{metric_key}.png"
                else:
                    chart_file = self.results_dir / f"chart_{metric_key}_{group}.png"

                plt.tight_layout()
                plt.savefig(chart_file, dpi=100)
                plt.close()

                charts.append(chart_file)
                print(f"Chart saved to {chart_file}")

        # Ensure `groups` is defined for the per-request charts generation
        # Recompute available groups across variants in case the earlier loop didn't set `groups` in this scope
        groups = set()
        for variant in ["S", "A"]:
            vdata = self.aggregated.get("variants", {}).get(variant, {})
            for uc, metrics in vdata.get("locust_metrics", {}).items():
                if isinstance(metrics, dict) and "all" in metrics:
                    groups.update(metrics.keys())
                else:
                    groups.add("all")

        if not groups:
            groups = {"all"}

        # --- Detailed per-request response time charts ---
        # For each discovered endpoint group and user count produce bar charts
        # that show every recorded response time from the per-request CSV files
        # written by the Locust runner (files named like
        # locust_responses_{variant}_{group}_{user_count}_users[_runX].csv).
        for user_count in user_counts:
            for group in sorted(groups):
                per_variant_data = {}
                for variant in ["S", "A"]:
                    # Try group-specific files first
                    pattern = f"locust_responses_{variant.lower()}_{group}_{user_count}_users*.csv"
                    files = list(self.results_dir.glob(pattern))
                    # Fallback to legacy pattern without group
                    if not files:
                        files = list(
                            self.results_dir.glob(f"locust_responses_{variant.lower()}_{user_count}_users*.csv")
                        )

                    response_times = []
                    for p in sorted(files):
                        try:
                            with open(p, "r", newline="") as fh:
                                reader = csv.DictReader(fh)
                                for row in reader:
                                    try:
                                        rt = float(row.get("response_time_ms", "0") or 0)
                                        response_times.append(rt)
                                    except Exception:
                                        continue
                        except Exception:
                            continue

                    if response_times:
                        per_variant_data[variant] = response_times

                # Plot per-variant histograms: X = Response Time (ms), Y = Occurrences
                for variant, rts in per_variant_data.items():
                    fig, ax = plt.subplots(figsize=(12, 6))
                    # Use an automatic binning strategy but cap the number of bins for readability
                    try:
                        bins = min(100, max(10, int(len(rts) / 5)))
                    except Exception:
                        bins = 50

                    ax.hist(rts, bins=bins, color=("C0" if variant == "S" else "C1"), alpha=0.7)
                    ax.set_xlabel("Czas odpowiedzi (ms)", fontsize=12)
                    ax.set_ylabel("Występowania", fontsize=12)
                    ax.set_title(
                        f"Rozkład czasu odpowiedzi: Wariant {variant} - {group} - {user_count} użytkowników",
                        fontsize=14,
                    )
                    ax.grid(True, alpha=0.3)
                    chart_file = self.results_dir / f"chart_responses_{variant}_{group}_{user_count}_users.png"
                    plt.tight_layout()
                    plt.savefig(chart_file, dpi=100)
                    plt.close()
                    charts.append(chart_file)
                    print(f"Per-request histogram saved to {chart_file}")

                # Combined overlay if both variants present
                if "S" in per_variant_data and "A" in per_variant_data:
                    fig, ax = plt.subplots(figsize=(12, 6))
                    # Overlay histograms for both variants using semi-transparent bars
                    s_rts = per_variant_data["S"]
                    a_rts = per_variant_data["A"]

                    # Determine shared bins based on combined data for fair comparison
                    combined = s_rts + a_rts
                    try:
                        bins = min(100, max(10, int(len(combined) / 5)))
                    except Exception:
                        bins = 50

                    ax.hist(s_rts, bins=bins, color="C0", alpha=0.5, label="Wariant S")
                    ax.hist(a_rts, bins=bins, color="C1", alpha=0.5, label="Wariant A")
                    ax.set_xlabel("Czas odpowiedzi (ms)", fontsize=12)
                    ax.set_ylabel("Występowania", fontsize=12)
                    ax.set_title(
                        f"Porównanie rozkładu czasu odpowiedzi ({group}) - {user_count} użytkowników", fontsize=14
                    )
                    ax.legend()
                    ax.grid(True, alpha=0.3)
                    chart_file = self.results_dir / f"chart_responses_compare_{group}_{user_count}_users.png"
                    plt.tight_layout()
                    plt.savefig(chart_file, dpi=100)
                    plt.close()
                    charts.append(chart_file)
                    print(f"Per-request comparison histogram saved to {chart_file}")

        return charts

    def print_summary(self):
        """Print summary to console"""
        print("\n" + "=" * 80)
        print("PODSUMOWANIE AGREGACJI PORÓWNANIA WYDAJNOŚCI")
        print("=" * 80)

        print("\nTESTY HIPOTEZ (Mann-Whitney U, alfa=0,05)")
        print("-" * 80)

        tests = self.aggregated.get("hypothesis_tests", {})

        for group, results in tests.items():
            print(f"\nScenariusz: {group}")

            for users, result in results.items():
                if "error" in result:
                    print(f"  {users} użytkowników: brakujące dane")
                    continue

                significance = "ISTOTNE" if result["significant"] else "NIE ISTOTNE"

                print(
                    f"  {users} użytkowników | "
                    f"p={result['p_value']:.6f} | "
                    f"{significance} | "
                    f"S mediana={result['sync_median']:.2f}ms | "
                    f"A mediana={result['async_median']:.2f}ms"
                )

        for variant in ["S", "A"]:
            if variant not in self.aggregated["variants"]:
                continue

            print(f"\nWariant {variant}:")
            print("-" * 80)

            variant_data = self.aggregated["variants"][variant]

            # Print complexity metrics
            if variant_data.get("complexity_metrics"):
                complexity = variant_data["complexity_metrics"]["summary"]
                print(f"  Złożoność kodu:")
                print(f"    - Średni CC: {complexity['avg_cc']}")
                print(f"    - Średni MI: {complexity['avg_mi']}")
                print(f"    - Przeanalizowane pliki: {complexity['total_files']}")

            # Print performance metrics
            print(f"\n  Metryki wydajności:")
            for user_count, metrics in sorted(variant_data.get("locust_metrics", {}).items()):
                if isinstance(metrics, dict) and "all" in metrics:
                    metrics_all = metrics.get("all", {})
                else:
                    metrics_all = metrics

                print(f"\n    {user_count} równoczesnych użytkowników:")
                print(f"      Przepustowość: {metrics_all.get('throughput', {}).get('median', 0)} req/s")
                print(f"      Czas odpowiedzi (P50): {metrics_all.get('response_time_p50_ms', {}).get('median', 0)}ms")
                print(f"      Czas odpowiedzi (P95): {metrics_all.get('response_time_p95_ms', {}).get('median', 0)}ms")
                print(f"      Czas odpowiedzi (P99): {metrics_all.get('response_time_p99_ms', {}).get('median', 0)}ms")
                print(f"      Wskaźnik błędów: {metrics_all.get('error_rate_percent', {}).get('median', 0)}%")

                if isinstance(metrics, dict) and len(metrics) > 1:
                    print(f"\n      Podział na punkt końcowy:")
                    for group_name, group_metrics in sorted(metrics.items()):
                        if group_name == "all":
                            continue
                        print(f"        - {group_name}:")
                        print(
                            f"            Przepustowość: {group_metrics.get('throughput', {}).get('median', 0)} req/s"
                        )
                        print(
                            f"            P50: {group_metrics.get('response_time_p50_ms', {}).get('median', 0)}ms, P95: {group_metrics.get('response_time_p95_ms', {}).get('median', 0)}ms, P99: {group_metrics.get('response_time_p99_ms', {}).get('median', 0)}ms"
                        )
                        print(
                            f"            Wskaźnik błędów: {group_metrics.get('error_rate_percent', {}).get('median', 0)}%"
                        )

        print("\n" + "=" * 80)


def run_aggregation(results_dir: str = "benchmark_results"):
    """Run metrics aggregation"""
    aggregator = MetricsAggregator(results_dir)

    # Aggregate results for both variants
    for variant in ["s", "a"]:
        variant_data = aggregator.aggregate_locust_runs(variant)
        aggregator.aggregated["variants"][variant.upper()] = variant_data

    # Save results
    aggregator.run_hypothesis_tests()
    aggregator.save_aggregated_json()
    aggregator.save_comparison_csv()
    aggregator.generate_charts()
    aggregator.print_summary()

    return aggregator


if __name__ == "__main__":
    import sys

    results_dir = sys.argv[1] if len(sys.argv) > 1 else "benchmark_results"
    run_aggregation(results_dir)
