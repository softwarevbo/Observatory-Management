from rest_framework import serializers

from .models import AuditLog

"""
This module defines Serializers for Django REST Framework (DRF).
Serializers control how database model instances are converted to/from JSON 
representation for API HTTP request and response payloads.
"""

class AuditLogSerializer(serializers.ModelSerializer):
    """
    ModelSerializer for the AuditLog model.
    A ModelSerializer automatically inspects fields defined on the AuditLog database model,
    mapping and validating them automatically without manual field definitions.
    """
    class Meta:
        model = AuditLog
        # Includes all model database fields in the serialized API JSON output
        fields = "__all__"
