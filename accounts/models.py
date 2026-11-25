from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """A login account. Every user has exactly one role."""

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrator"
        MANAGER = "MANAGER", "Cooperative Manager"
        STAFF = "STAFF", "Staff Member"
        FARMER = "FARMER", "Farmer"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STAFF)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"