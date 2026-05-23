# Uvicorn configuration for Variant A (Asynchronous)
# Reference: https://www.uvicorn.org/settings/

import multiprocessing
import os

# Basic settings
host = os.environ.get("UVICORN_HOST", "0.0.0.0")
port = int(os.environ.get("UVICORN_PORT", 8001))
workers = int(os.environ.get("UVICORN_WORKERS", (2 * multiprocessing.cpu_count() + 1)))

# Logging
log_level = os.environ.get("UVICORN_LOG_LEVEL", "info").lower()
access_log = os.environ.get("UVICORN_ACCESS_LOG", "true").lower() == "true"

# Application
app = "config.asgi:application"
interface = "asgi3"

# ASGI settings
lifespan = "on"
loop = "uvloop"
http = "httptools"

# Connection settings
timeout_keep_alive = 5
timeout_notify = 30
timeout_graceful_shutdown = 15

# Reload (development only)
reload = False
reload_dirs = []

# Server header
server_header = False

# Proxy headers
proxy_headers = True
forwarded_allow_ips = os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1")

# Root path
root_path = ""

