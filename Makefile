.PHONY: run-s-benchmark run-a-benchmark benchmark-all \
		run-s-benchmark-cpu run-s-benchmark-io run-s-benchmark-mixed \
		run-a-benchmark-cpu run-a-benchmark-io run-a-benchmark-mixed \
		_benchmark-setup _run-variant-benchmark \
		_aggregate-results _final-teardown

GROUPS := cpu io mixed
ENDPOINT_GROUP ?= all
USE_PGBOUNCER ?= true

ifeq ($(USE_PGBOUNCER),true)
	DB_HOST := pgbouncer
	DB_PORT := 6432
	DOCKER_PROFILE := pgbouncer
	PROFILE_FLAG := --profile pgbouncer
else
	DB_HOST := postgres
	DB_PORT := 5432
	DOCKER_PROFILE :=
	PROFILE_FLAG :=
endif

export DB_HOST
export DB_PORT

# Benchmarking

run-s-benchmark: _benchmark-setup
	@echo ""
	@echo "=========================================="
	@echo "Starting Variant S Benchmark Suite (per-group)"
	@echo "=========================================="
	@echo ""
	@bash -c 'for g in $(GROUPS); do \
		echo "\n--- Running Variant S group: $$g ---"; \
		$(MAKE) _run-variant-benchmark VARIANT=S ENDPOINT_GROUP=$$g HOST=http://variant-s-server:8000; \
	done'

run-a-benchmark: _benchmark-setup
	@echo ""
	@echo "=========================================="
	@echo "Starting Variant A Benchmark Suite (per-group)"
	@echo "=========================================="
	@echo ""
	@bash -c 'for g in $(GROUPS); do \
		echo "\n--- Running Variant A group: $$g ---"; \
		$(MAKE) _run-variant-benchmark VARIANT=A ENDPOINT_GROUP=$$g HOST=http://variant-a-server:8001; \
	done'

run-s-benchmark-cpu:
	@$(MAKE) _run-variant-benchmark VARIANT=S ENDPOINT_GROUP=cpu HOST=http://variant-s-server:8000

run-s-benchmark-io:
	@$(MAKE) _run-variant-benchmark VARIANT=S ENDPOINT_GROUP=io HOST=http://variant-s-server:8000

run-s-benchmark-mixed:
	@$(MAKE) _run-variant-benchmark VARIANT=S ENDPOINT_GROUP=mixed HOST=http://variant-s-server:8000

run-a-benchmark-cpu:
	@$(MAKE) _run-variant-benchmark VARIANT=A ENDPOINT_GROUP=cpu HOST=http://variant-a-server:8001

run-a-benchmark-io:
	@$(MAKE) _run-variant-benchmark VARIANT=A ENDPOINT_GROUP=io HOST=http://variant-a-server:8001

run-a-benchmark-mixed:
	@$(MAKE) _run-variant-benchmark VARIANT=A ENDPOINT_GROUP=mixed HOST=http://variant-a-server:8001

benchmark-all: _benchmark-setup run-s-benchmark run-a-benchmark _aggregate-results _final-teardown

_benchmark-setup:
	@echo "Setting up benchmark environment..."
	@echo "Cleaning up any existing containers..."
	docker compose $(PROFILE_FLAG) down --remove-orphans

	mkdir -p benchmark_results

	@echo "Building Docker images..."
	docker compose $(PROFILE_FLAG) build variant-s-server variant-a-server locust

	@echo "Starting infrastructure services..."
	docker compose $(PROFILE_FLAG) up -d postgres redis $(if $(filter pgbouncer,$(DOCKER_PROFILE)),pgbouncer)

	@echo "Waiting for services to be healthy..."
	@bash -c '\
	for i in {1..30}; do \
		if docker compose exec -T postgres pg_isready -U postgres >/dev/null 2>&1 && \
		   docker compose exec -T redis redis-cli ping >/dev/null 2>&1; then \
			echo "Services are healthy"; \
			exit 0; \
		fi; \
		echo "Attempt $$i/30: Waiting for services..."; \
		sleep 2; \
	done; \
	echo "Warning: Services may not be fully ready, proceeding anyway..."; \
	exit 0'

	@echo "Applying migrations..."
	docker compose $(PROFILE_FLAG) run --rm variant-s-server sh -c "cd variant_s && python manage.py migrate"
	docker compose $(PROFILE_FLAG) run --rm variant-a-server sh -c "cd variant_a && python manage.py migrate"

	@echo "Seeding benchmark data..."
	docker compose $(PROFILE_FLAG) run --rm variant-s-server sh -c "cd variant_s && python manage.py shell -c \"from shared.models import Article; Article.objects.get_or_create(id=1, defaults={'title':'Seed Article','content':'Seed content'})\""

_run-variant-benchmark:
	@echo "Collecting complexity metrics for Variant $(VARIANT)..."
	@docker compose run --rm locust python /app/benchmarks/complexity_metrics.py $(shell echo $(VARIANT) | tr A-Z a-z)

	@echo ""
	@echo "Starting server..."
	docker compose $(PROFILE_FLAG) up -d \
	postgres \
	redis \
	$(if $(filter pgbouncer,$(DOCKER_PROFILE)),pgbouncer) \
	variant-$(shell echo $(VARIANT) | tr A-Z a-z)-server

	@echo "Waiting for server health check..."
	@bash -c '\
	if [ "$(VARIANT)" = "S" ]; then LOCAL_HOST="http://localhost:8000"; else LOCAL_HOST="http://localhost:8001"; fi; \
	for i in {1..30}; do \
		if curl -sS --fail $$LOCAL_HOST/api/health/ >/dev/null 2>&1; then \
			echo "$$LOCAL_HOST ready"; \
			exit 0; \
		fi; \
		echo "Attempt $$i/30: waiting for $$LOCAL_HOST..."; \
		sleep 2; \
	done; \
	echo "Timed out waiting for $$LOCAL_HOST"; \
	exit 1'

	@echo ""
	@echo "Running Locust benchmarks (3 repetitions)..."
	@for run in 1 ; do \
		echo ""; \
		echo "Run $$run/3 - 10 users"; \
		RUN_NUM=$$run docker compose run --rm -e RUN_NUM=$$run -e ENDPOINT_GROUP=$(ENDPOINT_GROUP) \
			locust locust -f /app/benchmarks/locustfile.py --host $(HOST) \
			--users 10 --spawn-rate 1 --run-time 120 --headless; \
# 		echo ""; \
# 		echo "Run $$run/3 - 50 users"; \
# 		RUN_NUM=$$run docker compose run --rm -e RUN_NUM=$$run -e ENDPOINT_GROUP=$(ENDPOINT_GROUP) \
# 			locust locust -f /app/benchmarks/locustfile.py --host $(HOST) \
# 			--users 50 --spawn-rate 5 --run-time 120 --headless; \
# 		echo ""; \
# 		echo "Run $$run/3 - 200 users"; \
# 		RUN_NUM=$$run docker compose run --rm -e RUN_NUM=$$run -e ENDPOINT_GROUP=$(ENDPOINT_GROUP) \
# 			locust locust -f /app/benchmarks/locustfile.py --host $(HOST) \
# 			--users 200 --spawn-rate 20 --run-time 120 --headless; \
	done

	@echo ""
	@echo "Stopping services..."
	docker compose $(PROFILE_FLAG) down

_aggregate-results:
	@echo ""
	@echo "=========================================="
	@echo "Aggregating and analyzing results"
	@echo "=========================================="
	@echo ""

	@docker compose run --rm -v ./benchmark_results:/app/benchmark_results \
		locust python /app/benchmarks/aggregator.py /app/benchmark_results

	@echo ""
	@echo "Results available in: ./benchmark_results/"
	@ls -lh benchmark_results/*.json benchmark_results/*.csv benchmark_results/*.png 2>/dev/null || true

_final-teardown:
	@echo "Tearing down benchmark environment..."
	docker compose $(PROFILE_FLAG) down --remove-orphans
	@echo "Teardown complete"

run-complexity-both:
	@echo ""
	@echo "=========================================="
	@echo "Running Complexity Analysis (S + A)"
	@echo "=========================================="
	@echo ""

	@echo "--- Variant S ---"
	@docker compose run --rm locust python /app/benchmarks/complexity_metrics.py s

	@echo ""
	@echo "--- Variant A ---"
	@docker compose run --rm locust python /app/benchmarks/complexity_metrics.py a

	@echo ""
	@echo "Complexity analysis completed"