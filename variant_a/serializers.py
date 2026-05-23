"""
Variant A (Asynchronous) Serializers
Using ADRF (Async Django REST Framework) serializers for asynchronous views
"""

from adrf.serializers import ModelSerializer

from shared.models import Article


class BaseSerializer(ModelSerializer):
    """
    Base serializer for Variant A (Async) using ADRF
    Note: ADRF serializers support async operations and must be used with async views
    """

    class Meta:
        abstract = True
        fields = ["id", "created_at", "updated_at"]


class ArticleSerializer(BaseSerializer):
    """
    Serializer for Article model in Variant A
    """

    class Meta:
        model = Article
        fields = ["id", "title", "content", "created_at", "updated_at"]

    def update(self, instance, validated_data):
        """Update and return an `Article` instance, given the validated data."""
        instance.title = validated_data.get("title", instance.title)
        instance.content = validated_data.get("content", instance.content)
        instance.save()
        return instance
