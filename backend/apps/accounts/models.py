from __future__ import annotations

import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class AdminRole(models.TextChoices):
    SUPER_ADMIN = "SUPER_ADMIN", "Super Administrator"
    ADMIN = "ADMIN", "Ordinary Administrator"


class UserManager(BaseUserManager["User"]):
    def normalize_email_address(self, email: str) -> str:
        return self.normalize_email(email.strip()).lower()

    def create_user(
        self,
        email: str,
        password: str | None = None,
        display_name: str = "",
        **extra_fields,
    ) -> User:
        if not email:
            raise ValueError("Administrator email address is required.")
        normalized = self.normalize_email_address(email)
        user = self.model(
            email=normalized,
            display_name=(display_name or normalized.split("@")[0]).strip(),
            **extra_fields,
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email: str,
        password: str | None = None,
        display_name: str = "Super Administrator",
        **extra_fields,
    ) -> User:
        extra_fields.setdefault("role", AdminRole.SUPER_ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if not password:
            raise ValueError("Superuser password is required.")
        return self.create_user(email=email, password=password, display_name=display_name, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, max_length=254)
    display_name = models.CharField(max_length=120)
    role = models.CharField(
        max_length=20,
        choices=AdminRole.choices,
        default=AdminRole.ADMIN,
        db_index=True,
    )
    invitation_limit = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    is_staff = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["display_name"]

    class Meta:
        ordering = ["display_name", "email"]

    @property
    def is_super_admin(self) -> bool:
        return bool(self.is_active and (self.role == AdminRole.SUPER_ADMIN or self.is_superuser))

    def save(self, *args, **kwargs) -> None:
        if self.email:
            self.email = self.email.strip().lower()
        if self.role == AdminRole.SUPER_ADMIN:
            self.is_superuser = True
            self.is_staff = True
        else:
            self.is_superuser = False
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.display_name} <{self.email}>"


class PasswordResetToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_reset_tokens")
    token_digest = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class RateLimitBucket(models.Model):
    scope = models.CharField(max_length=64)
    identifier = models.CharField(max_length=64)
    window_start = models.DateTimeField(db_index=True)
    hit_count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["scope", "identifier", "window_start"],
                name="uniq_accounts_ratelimit_bucket",
            )
        ]
