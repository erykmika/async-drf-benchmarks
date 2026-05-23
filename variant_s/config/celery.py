"""
Celery configuration for Variant S (Synchronous)
"""

import os
from celery import Celery
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("drf_benchmark_s")

app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks from registered Django apps
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")

