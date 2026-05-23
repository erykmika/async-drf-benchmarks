"""
Views for Variant S (Synchronous)
Using Django REST Framework ViewSets for synchronous operations
"""

import time
import json
from typing import Any

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from shared.models import Article
from shared.utils import HTTPClient, CacheClient
from serializers import ArticleSerializer
from config.celery import app as celery_app


# Sample data for CPU-bound endpoints
SAMPLE_ARTICLES_SMALL = [
    {
        "id": i,
        "title": f"Sample Article {i}",
        "content": f"This is the content of sample article {i}. " * 10,
        "created_at": "2023-01-01T00:00:00Z",
        "updated_at": "2023-01-01T00:00:00Z",
    }
    for i in range(1, 51)
]

SAMPLE_ARTICLES_LARGE = [
    {
        "id": i,
        "title": f"Sample Article {i}",
        "content": f"This is the content of sample article {i}. " * 10,
        "created_at": "2023-01-01T00:00:00Z",
        "updated_at": "2023-01-01T00:00:00Z",
    }
    for i in range(1, 1001)
]

SAMPLE_ARTICLES_200 = [
    {
        "id": i,
        "title": f"External Article {i}",
        "content": f"Content from external service for article {i}. " * 5,
        "created_at": "2023-01-01T00:00:00Z",
        "updated_at": "2023-01-01T00:00:00Z",
    }
    for i in range(1, 201)
]


def analyze_text(content: str) -> dict[str, Any]:
    """Analyze text content for word statistics"""
    words = content.split()
    word_count = len(words)
    unique_words = len(set(words))
    avg_word_length = sum(len(word) for word in words) / word_count if word_count > 0 else 0
    return {
        "word_count": word_count,
        "unique_words": unique_words,
        "avg_word_length": round(avg_word_length, 2),
    }


@celery_app.task
def process_article_task(article_id: int):
    """Celery task to process an article"""
    # Simple task - just return the article_id
    return {"article_id": article_id, "status": "processed"}


class BenchmarkViewSet(ViewSet):
    """ViewSet for benchmark endpoints"""

    http_client = HTTPClient("S")
    cache_client = CacheClient("S")

    @action(detail=True, methods=["get"], url_path=r"articles/(?P<article_id>\d+)")
    def get_article(self, request, article_id=None):
        """IO-1: Read article from database"""
        try:
            article = Article.objects.get(id=article_id)
        except Article.DoesNotExist:
            return Response({"error": "Article not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = ArticleSerializer(article)
        return Response(serializer.data)

    @action(detail=True, methods=["put"], url_path=r"articles/(?P<article_id>\d+)")
    def update_article(self, request, article_id=None):
        """IO-2: Update article in database transaction"""
        try:
            article = Article.objects.get(id=article_id)
        except Article.DoesNotExist:
            return Response({"error": "Article not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = ArticleSerializer(article, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"], url_path="external")
    def external_call(self, request):
        """IO-3: Simulate external HTTP call with 100ms delay"""
        time.sleep(0.1)  # 100ms delay
        return Response({
            "status": "success",
            "data": {"external": "data", "timestamp": time.time()}
        })

    @action(detail=True, methods=["get"], url_path=r"cache/(?P<article_id>\d+)")
    def cache_or_db(self, request, article_id=None):
        """IO-4: Get from cache or database"""
        cache_key = f"article:{article_id}"
        cached_data = self.cache_client.get(cache_key)

        if cached_data:
            data = json.loads(cached_data)
        else:
            try:
                article = Article.objects.get(id=article_id)
            except Article.DoesNotExist:
                return Response({"error": "Article not found"}, status=status.HTTP_404_NOT_FOUND)

            serializer = ArticleSerializer(article)
            data = serializer.data
            self.cache_client.set(cache_key, json.dumps(data), ex=3600)

        return Response(data)

    @action(detail=False, methods=["post"], url_path="queue")
    def queue_task(self, request):
        """IO-5: Publish task to Celery queue"""
        article_id = request.data.get("article_id")
        if not article_id:
            return Response({"error": "article_id required"}, status=status.HTTP_400_BAD_REQUEST)

        task = process_article_task.delay(article_id)
        return Response({"task_id": task.id, "status": "queued"})

    @action(detail=False, methods=["get"], url_path="articles/list/small")
    def list_small(self, request):
        """CPU-1: Serialize 50 predefined articles"""
        serializer = ArticleSerializer(data=SAMPLE_ARTICLES_SMALL, many=True)
        if serializer.is_valid():
            return Response(serializer.validated_data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"], url_path="articles/list/large")
    def list_large(self, request):
        """CPU-2: Serialize 1000 predefined articles"""
        serializer = ArticleSerializer(data=SAMPLE_ARTICLES_LARGE, many=True)
        if serializer.is_valid():
            return Response(serializer.validated_data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"], url_path="articles/analyze")
    def analyze_article(self, request):
        """CPU-3: Analyze text content"""
        content = request.data.get("content", "")
        if not content:
            return Response({"error": "content required"}, status=status.HTTP_400_BAD_REQUEST)

        stats = analyze_text(content)
        return Response(stats)

    @action(detail=False, methods=["post"], url_path="articles/bulk")
    def bulk_create(self, request):
        """CPU-4: Validate 200 articles"""
        articles_data = request.data
        if not isinstance(articles_data, list) or len(articles_data) != 200:
            return Response({"error": "Exactly 200 articles required"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ArticleSerializer(data=articles_data, many=True)
        if serializer.is_valid():
            return Response({"count": 200, "status": "validated"})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"], url_path=r"mixed/db/(?P<article_id>\d+)")
    def mixed_db_analyze(self, request, article_id=None):
        """MIX-1: DB read + text analysis"""
        try:
            article = Article.objects.get(id=article_id)
        except Article.DoesNotExist:
            return Response({"error": "Article not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = ArticleSerializer(article)
        stats = analyze_text(article.content)
        return Response({
            "article": serializer.data,
            "stats": stats
        })

    @action(detail=False, methods=["get"], url_path="mixed/http")
    def mixed_http_serialize(self, request):
        """MIX-2: HTTP call + serialize 200 articles"""
        # Simulate external call
        time.sleep(0.1)
        articles_data = SAMPLE_ARTICLES_200

        serializer = ArticleSerializer(data=articles_data, many=True)
        if serializer.is_valid():
            return Response(serializer.validated_data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"], url_path=r"mixed/pipeline/(?P<article_id>\d+)")
    def mixed_pipeline(self, request, article_id=None):
        """MIX-3: Cache -> DB -> process -> cache"""
        cache_key = f"stats:{article_id}"
        cached_stats = self.cache_client.get(cache_key)

        if cached_stats:
            stats = json.loads(cached_stats)
            source = "cache"
        else:
            try:
                article = Article.objects.get(id=article_id)
            except Article.DoesNotExist:
                return Response({"error": "Article not found"}, status=status.HTTP_404_NOT_FOUND)

            stats = analyze_text(article.content)
            self.cache_client.set(cache_key, json.dumps(stats), ex=3600)
            source = "computed"

        return Response({
            "stats": stats,
            "source": source
        })

    @action(detail=False, methods=["get"], url_path="health")
    def health(self, request):
        return Response({"status": "healthy", "variant": "s"})

