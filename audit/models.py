from django.db import models


class AuditLog(models.Model):
    user = models.ForeignKey(
        "inventory.InventoryUser", on_delete=models.SET_NULL, null=True
    )
    action = models.CharField(max_length=255)
    model_name = models.CharField(max_length=255)
    object_id = models.PositiveIntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)
    changes = models.TextField(blank=True, null=True)
    branch = models.ForeignKey(
        "inventory.Branch", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"{self.user} {self.action} on {self.model_name}({self.object_id}) at {self.timestamp}"

    @staticmethod
    def log(user, action, instance=None, changes=None):
        branch = getattr(user, "branch", None)
        model_name = "System"
        object_id = 0

        if instance:
            # If the instance has a branch, use that instead (more accurate for objects)
            if hasattr(instance, "branch"):
                branch = instance.branch
            model_name = instance.__class__.__name__
            object_id = getattr(instance, "pk", 0) or 0

        AuditLog.objects.create(
            user=user,
            action=action,
            model_name=model_name,
            object_id=object_id,
            changes=changes or "",
            branch=branch,
        )
