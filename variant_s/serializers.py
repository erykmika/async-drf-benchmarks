"""
Variant S (Synchronous) Serializers
Using Django REST Framework serializers for synchronous views
"""

from rest_framework import serializers

from shared.models import Article


class BaseSerializer(serializers.ModelSerializer):
    """
    Base serializer for Variant S (Sync) with common fields
    """

    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    class Meta:
        abstract = True
        fields = ["id", "created_at", "updated_at"]


class ArticleSerializer(BaseSerializer):
    """
    Serializer for Article model in Variant S
    """

    title = serializers.CharField(max_length=255)
    content = serializers.CharField()

    class Meta:
        model = Article
        fields = ["id", "title", "content", "created_at", "updated_at"]

    def update(self, instance, validated_data):
        """Update and return an `Article` instance, given the validated data."""
        instance.title = validated_data.get("title", instance.title)
        instance.content = validated_data.get("content", instance.content)
        instance.save()
        return instance
