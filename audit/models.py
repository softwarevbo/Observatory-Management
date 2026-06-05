from django.db import models

"""
This module defines database models for system audit logging.
Audit logging records a chronological history of user actions within the inventory platform.
It documents who performed what action, when it occurred, what database model/object was affected,
and details of the specific field modifications made.
"""

class AuditLog(models.Model):
    """
    Model representing a single audit log entry.
    Tracks user operations, actions, model references, changed fields list, and branch context.
    """
    
    # Links to the inventory user who initiated the action.
    # We reference the string 'inventory.InventoryUser' to avoid circular dependencies.
    # on_delete=models.SET_NULL preserves audit records even if user accounts are deleted.
    user = models.ForeignKey(
        "inventory.InventoryUser", on_delete=models.SET_NULL, null=True
    )
    
    # Brief description of the action performed (e.g. 'Create', 'Update', 'Delete', 'Approve Transfer')
    action = models.CharField(max_length=255)
    
    # Stores the Python class name of the target database model (e.g. 'InventoryItem', 'StockTransfer')
    model_name = models.CharField(max_length=255)
    
    # Stores the database Primary Key (ID) of the affected object record
    object_id = models.PositiveIntegerField()
    
    # Automatically populated timestamp of when the audit log record was created
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Stores details of changed attributes, typically represented as serialized JSON or text
    changes = models.TextField(blank=True, null=True)
    
    # Link to physical branch warehouse context associated with the audited action
    branch = models.ForeignKey(
        "inventory.Branch", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        """String representation of the log entry, useful for listings."""
        return f"{self.user} {self.action} on {self.model_name}({self.object_id}) at {self.timestamp}"

    @staticmethod
    def log(user, action, instance=None, changes=None):
        """
        Static helper method to easily write audit records in one line of code.
        Can be invoked from anywhere like so:
        AuditLog.log(request.user, "Updated Stock", item_instance, changes="qty: 10 -> 15")

        Parameters:
        - user: The InventoryUser instance triggering the operation.
        - action: Text action identifier description.
        - instance: (Optional) The database object being affected.
        - changes: (Optional) Description text list detailing updated fields.
        """
        # Retrieve the branch from user metadata as fallback default
        branch = getattr(user, "branch", None)
        model_name = "System"
        object_id = 0

        # If an affected model instance is passed in, extract its details
        if instance:
            # If the object itself is linked to a branch, use that to keep logs precise
            if hasattr(instance, "branch"):
                branch = instance.branch
            model_name = instance.__class__.__name__
            object_id = getattr(instance, "pk", 0) or 0

        # Create and persist the AuditLog entry in the database
        AuditLog.objects.create(
            user=user,
            action=action,
            model_name=model_name,
            object_id=object_id,
            changes=changes or "",
            branch=branch,
        )
