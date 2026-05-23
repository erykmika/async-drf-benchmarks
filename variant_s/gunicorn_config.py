# Gunicorn configuration for Variant S (Synchronous)
# Reference: https://docs.gunicorn.org/en/stable/settings.html

import multiprocessing
import os

# Server mechanics
bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8000")
workers = int(os.environ.get("GUNICORN_WORKERS", (2 * multiprocessing.cpu_count() + 1)))
worker_class = "sync"  # Synchronous worker

# Server hooks
preload_app = True

# Logging
accesslog = os.environ.get("GUNICORN_ACCESS_LOG", "-")
errorlog = os.environ.get("GUNICORN_ERROR_LOG", "-")
loglevel = os.environ.get("GUNICORN_LOGLEVEL", "info")
access_log_format = (
    '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'
)

# Process naming
proc_name = "drf-benchmark-variant-s"

# Application
raw_env = [
    f"DJANGO_SETTINGS_MODULE=config.settings",
]

# Timeouts
timeout = 30
graceful_timeout = 30

# Keep-alive
keepalive = 2

# Miscellaneous
statsd_prefix = "gunicorn"
