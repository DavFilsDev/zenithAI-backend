from __future__ import annotations

from typing import Any, ClassVar, cast

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.db import models
from django.db.models.functions import Lower


class UserManager(DjangoUserManager):
    def get_by_natural_key(self, username: str | None) -> User:  # type: ignore[override]
        return cast(User, self.get(email__iexact=username))

class User(AbstractUser):
    email = models.EmailField(unique=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    objects: ClassVar[UserManager] = UserManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower('email'),
                name='users_email_case_insensitive_unique',
            ),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.email:
            self.email = self.email.lower()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.email
