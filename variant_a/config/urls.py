"""
URL Configuration for Variant A (Asynchronous)
"""

from django.contrib import admin
from django.urls import path, include

from apps.views import BenchmarkViewSet

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("rest_framework.urls")),
    # Benchmark endpoints
    path("api/articles/<int:article_id>/", BenchmarkViewSet.as_view({"get": "get_article", "put": "update_article"}), name="article-detail"),
    path("api/external/", BenchmarkViewSet.as_view({"get": "external_call"}), name="external"),
    path("api/cache/<int:article_id>/", BenchmarkViewSet.as_view({"get": "cache_or_db"}), name="cache"),
    path("api/queue/", BenchmarkViewSet.as_view({"post": "queue_task"}), name="queue"),
    path("api/articles/list/small/", BenchmarkViewSet.as_view({"get": "list_small"}), name="list-small"),
    path("api/articles/list/large/", BenchmarkViewSet.as_view({"get": "list_large"}), name="list-large"),
    path("api/articles/analyze/", BenchmarkViewSet.as_view({"post": "analyze_article"}), name="analyze"),
    path("api/articles/bulk/", BenchmarkViewSet.as_view({"post": "bulk_create"}), name="bulk"),
    path("api/mixed/db/<int:article_id>/", BenchmarkViewSet.as_view({"get": "mixed_db_analyze"}), name="mixed-db"),
    path("api/mixed/http/", BenchmarkViewSet.as_view({"get": "mixed_http_serialize"}), name="mixed-http"),
    path("api/mixed/pipeline/<int:article_id>/", BenchmarkViewSet.as_view({"get": "mixed_pipeline"}), name="mixed-pipeline"),
    path("api/health/", BenchmarkViewSet.as_view({"get": "health"}), name="health"),
]
