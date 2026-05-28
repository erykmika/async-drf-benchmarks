"""
Locust load testing scenario for DRF Benchmarks

Benchmark Rules:
- Each virtual user sends requests in a loop with random 1-3 second delays
- Prevents request overlap and reflects realistic traffic distribution
- Three concurrency levels: 10, 50, and 200 concurrent virtual users
- Allows observation of system behavior under low and high load
- Test duration: 120 seconds total with 30-second warmup phase
- Warmup results are excluded from analysis

Usage:
   Variant S (Sync): locust -f benchmarks/locustfile.py --host http://localhost:8000 \\
      --users 10 --spawn-rate 1 --run-time 120s
   Variant A (Async): locust -f benchmarks/locustfile.py --host http://localhost:8001 \\
      --users 10 --spawn-rate 1 --run-time 120s
"""

import csv
import json
import logging
import os
import random
from datetime import datetime
from pathlib import Path

from locust import HttpUser, between, events, task
from gevent import spawn, sleep

logger = logging.getLogger(__name__)

# Configuration
WARMUP_DURATION = 30  # seconds
TEST_DURATION = 120  # seconds total
METRICS_DIR = Path(os.getenv("OUTPUT_DIR", "/app/benchmark_results"))
METRICS_DIR.mkdir(exist_ok=True, parents=True)

# Metrics collection
test_start_time = None
warmup_end_time = None
metrics_file = None
# Per-request recording globals
per_request_file = None
per_request_handle = None
per_request_writer = None
per_request_lock = None
# Snapshot taken at the end of the warmup period so we can exclude warmup
# requests from the final throughput calculation.
warmup_snapshot = {"num_requests": 0, "num_failures": 0, "time": None}


class APIUser(HttpUser):
    """
    Simulates a user making requests to the API with realistic delays
    """

    wait_time = between(1, 3)  # Random 1-3 second delay between requests

    # Sample data for POST/PUT requests
    sample_content = "This is a sample article content for analysis. It contains multiple words and sentences to test the text analysis functionality. The analysis should count words, unique words, and calculate average word length."

    update_data = {"title": "Updated Article Title", "content": "Updated content for the article."}

    queue_data = {"article_id": 1}

    bulk_data = [
        {"title": f"Bulk Article {i}", "content": f"Content for bulk article {i}. " * 5} for i in range(1, 201)
    ]

    def io_1_get_article(self):
        """IO-1: GET /api/articles/{id}/"""
        with self.client.get("/api/articles/1/", catch_response=True) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"IO-1 failed: {response.status_code}")

    def io_2_update_article(self):
        """IO-2: PUT /api/articles/{id}/"""
        with self.client.put("/api/articles/1/", json=self.update_data, catch_response=True) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"IO-2 failed: {response.status_code}")

    def io_3_external_call(self):
        """IO-3: GET /api/external/"""
        with self.client.get("/api/external/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"IO-3 failed: {response.status_code}")

    def io_4_cache_get(self):
        """IO-4: GET /api/cache/{id}/"""
        with self.client.get("/api/cache/1/", catch_response=True) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"IO-4 failed: {response.status_code}")

    def io_5_queue_task(self):
        """IO-5: POST /api/queue/"""
        with self.client.post("/api/queue/", json=self.queue_data, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"IO-5 failed: {response.status_code}")

    def cpu_1_list_small(self):
        """CPU-1: GET /api/articles/list/small/"""
        with self.client.get("/api/articles/list/small/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"CPU-1 failed: {response.status_code}")

    def cpu_2_list_large(self):
        """CPU-2: GET /api/articles/list/large/"""
        with self.client.get("/api/articles/list/large/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"CPU-2 failed: {response.status_code}")

    def cpu_3_analyze_text(self):
        """CPU-3: POST /api/articles/analyze/"""
        data = {"content": self.sample_content}
        with self.client.post("/api/articles/analyze/", json=data, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"CPU-3 failed: {response.status_code}")

    def cpu_4_bulk_validate(self):
        """CPU-4: POST /api/articles/bulk/"""
        with self.client.post("/api/articles/bulk/", json=self.bulk_data, catch_response=True) as response:
            if response.status_code in [200, 400]:
                response.success()
            else:
                response.failure(f"CPU-4 failed: {response.status_code}")

    def mix_1_db_analyze(self):
        """MIX-1: GET /api/mixed/db/{id}/"""
        with self.client.get("/api/mixed/db/1/", catch_response=True) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"MIX-1 failed: {response.status_code}")

    def mix_2_http_serialize(self):
        """MIX-2: GET /api/mixed/http/"""
        with self.client.get("/api/mixed/http/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"MIX-2 failed: {response.status_code}")

    def mix_3_pipeline(self):
        """MIX-3: GET /api/mixed/pipeline/{id}/"""
        with self.client.get("/api/mixed/pipeline/1/", catch_response=True) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"MIX-3 failed: {response.status_code}")

    def on_start(self):
        """Called when a simulated user starts

        Build the list of enabled endpoint callables based on ENDPOINT_GROUP.
        This lets a single locustfile drive per-group benchmarks by setting
        the ENDPOINT_GROUP environment variable (cpu, io, mixed, or all).
        """
        logger.info("User started")
        group = os.getenv("ENDPOINT_GROUP", "all").lower()
        enabled = []

        if group in ("all", "io"):
            enabled.extend(
                [
                    self.io_1_get_article,
                    self.io_2_update_article,
                    self.io_3_external_call,
                    self.io_4_cache_get,
                    self.io_5_queue_task,
                ]
            )

        if group in ("all", "cpu"):
            enabled.extend(
                [
                    self.cpu_1_list_small,
                    self.cpu_2_list_large,
                    self.cpu_3_analyze_text,
                    self.cpu_4_bulk_validate,
                ]
            )

        if group in ("all", "mixed"):
            enabled.extend(
                [
                    self.mix_1_db_analyze,
                    self.mix_2_http_serialize,
                    self.mix_3_pipeline,
                ]
            )

        # Fallback: if no tasks selected, default to all tasks
        if not enabled:
            enabled = [
                self.io_1_get_article,
                self.io_2_update_article,
                self.io_3_external_call,
                self.io_4_cache_get,
                self.io_5_queue_task,
                self.cpu_1_list_small,
                self.cpu_2_list_large,
                self.cpu_3_analyze_text,
                self.cpu_4_bulk_validate,
                self.mix_1_db_analyze,
                self.mix_2_http_serialize,
                self.mix_3_pipeline,
            ]

        self._enabled_tasks = enabled

    def on_stop(self):
        """Called when a simulated user stops"""
        logger.info("User stopped")

    @task(1)
    def _run_enabled_task(self):
        """Run one of the enabled endpoint tasks chosen at random."""
        if not hasattr(self, "_enabled_tasks") or not self._enabled_tasks:
            return
        task_callable = random.choice(self._enabled_tasks)
        try:
            task_callable()
        except Exception:
            # Let Locust record exceptions via the client context in the task
            raise


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when load test starts"""
    global \
        test_start_time, \
        warmup_end_time, \
        metrics_file, \
        per_request_file, \
        per_request_handle, \
        per_request_writer, \
        per_request_lock

    test_start_time = datetime.now()
    warmup_end_time = test_start_time + __import__("datetime").timedelta(seconds=WARMUP_DURATION)

    # Extract variant from host
    variant = "unknown"
    if "8000" in environment.host or "variant-s" in environment.host:
        variant = "s"
    elif "8001" in environment.host or "variant-a" in environment.host:
        variant = "a"

    # Get number of users
    num_users = environment.runner.target_user_count or 10

    # Check for run number and endpoint group in environment variables (set by Makefile)
    run_num = os.getenv("RUN_NUM", "")
    group = os.getenv("ENDPOINT_GROUP", "all").lower()
    if run_num:
        metrics_file = METRICS_DIR / f"locust_metrics_{variant}_{group}_{num_users}_users_run{run_num}.json"
    else:
        metrics_file = METRICS_DIR / f"locust_metrics_{variant}_{group}_{num_users}_users.json"

    logger.info(f"Load test started at {test_start_time}")
    logger.info(f"Warmup duration: {WARMUP_DURATION}s")
    logger.info(f"Total test duration: {TEST_DURATION}s")
    logger.info(f"Variant: {variant}, Users: {num_users}")
    logger.info(f"Metrics will be saved to: {metrics_file}")

    # Prepare per-request response CSV file (records each request's response_time)
    per_request_lock = __import__("threading").Lock()

    if run_num:
        per_request_file = METRICS_DIR / f"locust_responses_{variant}_{group}_{num_users}_users_run{run_num}.csv"
    else:
        per_request_file = METRICS_DIR / f"locust_responses_{variant}_{group}_{num_users}_users.csv"

    try:
        new_file = not per_request_file.exists()
        per_request_handle = open(per_request_file, "a", newline="")
        per_request_writer = csv.writer(per_request_handle)
        if new_file:
            # Header: timestamp, method, name, response_time_ms, response_length, failed, error
            per_request_writer.writerow(
                [
                    "timestamp",
                    "method",
                    "name",
                    "response_time_ms",
                    "response_length",
                    "failed",
                    "error",
                ]
            )
            per_request_handle.flush()
        logger.info(f"Per-request responses will be saved to: {per_request_file}")
    except Exception as e:
        logger.warning(f"Could not open per-request response file: {e}")

    # Schedule a background snapshot after warmup so we can subtract warmup
    # counts from the final metrics. Use gevent to schedule the delayed task
    # inside the same process where Locust is running.
    def _record_warmup_snapshot(env=environment):
        try:
            sleep(WARMUP_DURATION)
            warmup_snapshot["num_requests"] = getattr(env.stats.total, "num_requests", 0) or 0
            warmup_snapshot["num_failures"] = getattr(env.stats.total, "num_failures", 0) or 0
            warmup_snapshot["time"] = datetime.now()
            logger.info(
                f"Warmup snapshot recorded at {warmup_snapshot['time']}: "
                f"requests={warmup_snapshot['num_requests']}, failures={warmup_snapshot['num_failures']}"
            )
        except Exception as e:
            logger.warning(f"Failed to record warmup snapshot: {e}")

    try:
        spawn(_record_warmup_snapshot)
    except Exception:
        # If gevent.spawn not available for some reason, continue without snapshot.
        logger.warning("Could not schedule warmup snapshot; warmup will not be excluded")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when load test stops - aggregates and exports metrics"""
    global test_start_time, warmup_end_time, metrics_file

    if not metrics_file:
        return

    test_end_time = datetime.now()

    # Extract metrics from Locust stats
    stats = environment.stats
    total_requests = stats.total.num_requests
    total_failures = stats.total.num_failures
    total_success = stats.total.num_requests - stats.total.num_failures

    # Calculate error rate
    error_rate = (total_failures / total_requests * 100) if total_requests > 0 else 0

    # Calculate throughput (requests per second). Exclude warmup
    total_duration = (test_end_time - test_start_time).total_seconds()
    throughput_including_warmup = total_requests / total_duration if total_duration > 0 else 0

    # Compute post-warmup deltas
    if warmup_snapshot.get("time") and warmup_snapshot["time"] < test_end_time:
        post_warmup_requests = max(0, total_requests - warmup_snapshot.get("num_requests", 0))
        post_warmup_failures = max(0, total_failures - warmup_snapshot.get("num_failures", 0))
        post_warmup_success = max(0, post_warmup_requests - post_warmup_failures)
        post_warmup_duration = (test_end_time - warmup_snapshot["time"]).total_seconds()
        throughput = post_warmup_requests / post_warmup_duration if post_warmup_duration > 0 else 0
    else:
        post_warmup_requests = total_requests
        post_warmup_failures = total_failures
        post_warmup_success = total_success
        post_warmup_duration = total_duration
        throughput = throughput_including_warmup

    p50 = stats.total.get_response_time_percentile(0.5)
    p95 = stats.total.get_response_time_percentile(0.95)
    p99 = stats.total.get_response_time_percentile(0.99)

    # Prepare aggregated metrics
    metrics = {
    "timestamp": test_end_time.isoformat(),
        "duration_seconds": total_duration,
        "post_warmup_duration_seconds": post_warmup_duration,
        "test_period_seconds": TEST_DURATION,
        "warmup_duration_seconds": WARMUP_DURATION,
        "performance_metrics": {
            "throughput_req_per_sec": round(throughput, 2),
            "throughput_including_warmup_req_per_sec": round(throughput_including_warmup, 2),
            "response_time_p50_ms": round(p50, 2),
            "response_time_p95_ms": round(p95, 2),
            "response_time_p99_ms": round(p99, 2),
            "error_rate_percent": round(error_rate, 2),
        },
        "request_summary": {
            "total_requests": total_requests,
            "successful_requests": total_success,
            "failed_requests": total_failures,
            "post_warmup_requests": post_warmup_requests,
            "post_warmup_successful_requests": post_warmup_success,
            "post_warmup_failed_requests": post_warmup_failures,
        },
    }

    # Save metrics to JSON
    try:
        with open(metrics_file, "w") as f:
            json.dump(metrics, f, indent=2)
        logger.info(f"Metrics exported to {metrics_file}")
        logger.info(f"Throughput: {metrics['performance_metrics']['throughput_req_per_sec']} req/s")
        logger.info(f"P50: {metrics['performance_metrics']['response_time_p50_ms']}ms")
        logger.info(f"P95: {metrics['performance_metrics']['response_time_p95_ms']}ms")
        logger.info(f"P99: {metrics['performance_metrics']['response_time_p99_ms']}ms")
        logger.info(f"Error rate: {metrics['performance_metrics']['error_rate_percent']}%")
    except Exception as e:
        logger.error(f"Error saving metrics: {e}")

    # Close per-request file handle if open
    global per_request_handle, per_request_writer
    try:
        if per_request_handle:
            per_request_handle.close()
            per_request_handle = None
            per_request_writer = None
            logger.info("Per-request response file closed")
    except Exception:
        pass


@events.request.add_listener
def _record_request(request_type, name, response_time, response_length, response, context, exception, **kwargs):
    """Listener for each request emitted by Locust. Writes to CSV file.

    Excludes requests during warmup (if warmup snapshot recorded).
    """
    global per_request_file, per_request_handle, per_request_writer, per_request_lock

    if not per_request_handle or per_request_writer is None:
        return

    try:
        ts = datetime.now()
        # Exclude warmup period (use warmup_end_time set at test start)
        if warmup_end_time and ts < warmup_end_time:
            return

        failed = 1 if exception else 0
        err = str(exception) if exception else ""

        try:
            rt = float(response_time)
        except Exception:
            rt = 0.0

        try:
            rlen = int(response_length) if response_length is not None else 0
        except Exception:
            rlen = 0

        # Write row: timestamp, method, name, response_time_ms, response_length, failed, error
        try:
            with per_request_lock:
                per_request_writer.writerow(
                    [
                        ts.isoformat(),
                        request_type,
                        name,
                        round(rt, 2),
                        rlen,
                        failed,
                        err,
                    ]
                )
                try:
                    per_request_handle.flush()
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Failed to write per-request row: {e}")
    except Exception as e:
        logger.debug(f"Failed to record request: {e}")
