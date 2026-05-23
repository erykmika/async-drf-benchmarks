"""
Shared base classes for models
Note: Serializers are variant-specific and located in:
  - variant_s/serializers.py (DRF serializers)
  - variant_a/serializers.py (ADRF serializers)
"""

from django.db import models


class TimestampedModel(models.Model):
    """
    Base model with created_at and updated_at timestamps.
    Used across both variants.
    """

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class Article(TimestampedModel):
    """
    Article model for storing articles with title and content.
    """

    title = models.CharField(max_length=255)
    content = models.TextField()

    class Meta:
        db_table = "articles"

    def __str__(self):
        return self.title
