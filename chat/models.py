import uuid

from django.db import models, transaction
from django.db.models import F
from django.utils import timezone
from users.models import User

class Conversation(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations')
    title = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.title}"

class Message(models.Model):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."


class DailyQuota(models.Model):
    """A single row per day counting every message sent across all users."""

    date = models.DateField(unique=True)
    count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.date}: {self.count}"

    @classmethod
    def try_consume(cls, cap):
        """Count one message against today's quota, atomically.

        Returns True when the message is allowed and the counter was incremented,
        False when the cap is already reached.
        """
        today = timezone.localdate()
        with transaction.atomic():
            quota, _ = cls.objects.select_for_update().get_or_create(date=today)
            if quota.count >= cap:
                return False
            cls.objects.filter(pk=quota.pk).update(count=F('count') + 1)
            return True