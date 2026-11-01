import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from .managers import LocalUserManager


class User(AbstractUser):
    objects = LocalUserManager()
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = None
    display_name = models.CharField(max_length=80)
    role = models.CharField(
        max_length=20, choices=[(x, x) for x in ("superadmin", "community_admin", "member")], default="member"
    )
    security_generation = models.PositiveIntegerField(default=1)
    device_bootstrapped = models.BooleanField(default=False)
    recovery_public_key = models.BinaryField(default=bytes)


class Invitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token_hash = models.CharField(max_length=64, unique=True)
    intended_username = models.CharField(max_length=150, blank=True)
    creator = models.ForeignKey(User, on_delete=models.PROTECT)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True)
    revoked_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Device(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    label = models.CharField(max_length=80)
    identity = models.CharField(max_length=200)
    public_key = models.BinaryField()
    credential = models.BinaryField(default=bytes)
    trust_state = models.CharField(max_length=20, default="pending")
    challenge = models.CharField(max_length=64)
    approved_by = models.ForeignKey("self", null=True, on_delete=models.PROTECT)
    approval_signature = models.BinaryField(default=bytes)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True)


class Session(models.Model):
    token_hash = models.CharField(max_length=64, unique=True)
    auth_hash = models.CharField(max_length=64, default="")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    device = models.ForeignKey(Device, null=True, on_delete=models.PROTECT)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True)
    device_challenge = models.CharField(max_length=64, blank=True)

    def save(self, *args, **kwargs):
        # Bind only at creation. An unrelated session update must never refresh
        # a binding invalidated by a password change. Bulk-created/unmigrated
        # sessions without a binding deliberately fail authentication.
        if self._state.adding and not self.auth_hash:
            self.auth_hash = self.user.get_session_auth_hash()
        return super().save(*args, **kwargs)


class DeviceKeyPackage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # After expiry only the globally unique digest is needed to reject reuse.
    device = models.ForeignKey(Device, null=True, on_delete=models.PROTECT)
    package = models.BinaryField()
    digest = models.CharField(max_length=64, unique=True)
    cipher_suite = models.PositiveIntegerField(default=1)
    protocol_version = models.PositiveIntegerField(default=1)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True)
    claimed_by = models.ForeignKey(Device, null=True, related_name="+", on_delete=models.PROTECT)

    class Meta:
        indexes = [
            models.Index(
                fields=["expires_at", "id"],
                condition=(
                    ~models.Q(package=b"")
                    | models.Q(device__isnull=False)
                    | models.Q(claimed_by__isnull=False)
                    | models.Q(consumed_at__isnull=False)
                ),
                name="keypackage_privacy_expiry",
            )
        ]


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=10, choices=[("direct", "direct"), ("group", "group")])
    creator = models.ForeignKey(Device, on_delete=models.PROTECT)
    group_id = models.CharField(max_length=100, unique=True)
    protocol_version = models.PositiveIntegerField(default=1)
    epoch = models.PositiveBigIntegerField(default=0)
    last_seq = models.PositiveBigIntegerField(default=0)
    status = models.CharField(max_length=20, default="active")
    genesis = models.JSONField(default=dict)
    genesis_signature = models.BinaryField(default=bytes)
    head_hash = models.CharField(max_length=64, blank=True)
    receipt_version = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["-created_at", "-id"], name="conversation_page_order")]


class Membership(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.PROTECT)
    device = models.ForeignKey(Device, on_delete=models.PROTECT)
    role = models.CharField(max_length=10, default="member")
    valid_from_epoch = models.PositiveBigIntegerField()
    removed_at_epoch = models.PositiveBigIntegerField(null=True)
    start_seq = models.PositiveBigIntegerField(default=0)
    leave_signature = models.BinaryField(default=bytes)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["conversation", "device"], name="unique_membership")]


class MessageEnvelope(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.PROTECT)
    sender_device = models.ForeignKey(Device, on_delete=models.PROTECT)
    protocol_version = models.PositiveIntegerField(default=1)
    server_seq = models.PositiveBigIntegerField()
    client_message_id = models.UUIDField()
    group_epoch = models.PositiveBigIntegerField()
    kind = models.CharField(max_length=15, default="application")
    ciphertext = models.BinaryField()
    request_digest = models.CharField(max_length=64)
    received_at = models.DateTimeField(auto_now_add=True, null=True)
    ciphertext_retired = models.BooleanField(default=False)
    header = models.JSONField(default=dict)
    signature = models.BinaryField(default=bytes)
    chain_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["sender_device", "client_message_id"], name="idempotent_send"),
            models.UniqueConstraint(fields=["conversation", "server_seq"], name="causal_order"),
        ]
        indexes = [models.Index(fields=["conversation", "server_seq"])]


class CryptoControlEvent(models.Model):
    envelope = models.OneToOneField(MessageEnvelope, primary_key=True, on_delete=models.PROTECT)
    transition = models.JSONField(default=dict)
    signature = models.BinaryField()
    welcome_device = models.ForeignKey(Device, null=True, on_delete=models.PROTECT)
    welcome = models.BinaryField(default=bytes)


class DeliveryCursor(models.Model):
    device = models.ForeignKey(Device, on_delete=models.PROTECT)
    conversation = models.ForeignKey(Conversation, on_delete=models.PROTECT)
    last_acked_seq = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["device", "conversation"], name="device_cursor")]


class NotificationOutbox(models.Model):
    envelope = models.OneToOneField(MessageEnvelope, on_delete=models.CASCADE)
    sent_at = models.DateTimeField(null=True)
    attempts = models.PositiveIntegerField(default=0)


class AttachmentTombstone(models.Model):
    # Never recycle a view-once ID after TTL cleanup. No accounts or opening times.
    id = models.UUIDField(primary_key=True, editable=False)


class EncryptedAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    uploader_device = models.ForeignKey(Device, on_delete=models.PROTECT)
    conversation = models.ForeignKey(Conversation, on_delete=models.PROTECT)
    epoch = models.PositiveBigIntegerField()
    ciphertext_size = models.PositiveBigIntegerField()
    chunk_count = models.PositiveIntegerField()
    view_once = models.BooleanField(default=False)
    status = models.CharField(max_length=15, default="uploading")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()


class AttachmentView(models.Model):
    # One recipient ACCOUNT, regardless of how many approved devices it has.
    attachment = models.ForeignKey(EncryptedAttachment, on_delete=models.CASCADE, related_name="views")
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    consumed = models.BooleanField(default=False)
    opened_by = models.ForeignKey(Device, null=True, on_delete=models.PROTECT)
    token_hash = models.CharField(max_length=64, blank=True)
    lease_expires_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["attachment", "user"], name="attachment_recipient_once")
        ]


class AttachmentChunk(models.Model):
    attachment = models.ForeignKey(EncryptedAttachment, on_delete=models.CASCADE)
    chunk_index = models.PositiveIntegerField()
    content_hash = models.CharField(max_length=64)
    byte_length = models.PositiveIntegerField()
    ciphertext = models.BinaryField()  # v1 self-hosted PostgreSQL blobs; bounded <= 1MiB/chunk.

    class Meta:
        constraints = [models.UniqueConstraint(fields=["attachment", "chunk_index"], name="chunk_once")]


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    category = models.CharField(max_length=40)
    target_opaque_id = models.CharField(max_length=64, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    # No free-form audit payload: secrets cannot accidentally be copied from requests.


class BootstrapEndpoint(models.Model):
    url = models.URLField(unique=True)
    tls_profile = models.CharField(max_length=30)
    priority = models.PositiveIntegerField(default=0)
    last_validated = models.DateTimeField(null=True)


class SoftwareRelease(models.Model):
    version = models.CharField(max_length=40, unique=True)
    manifest_hash = models.CharField(max_length=64)
    signing_public_key_ref = models.CharField(max_length=100)
    build_timestamp = models.DateTimeField()
    status = models.CharField(max_length=30)


class BackupManifest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encrypted_checksum = models.CharField(max_length=64)
    location = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    tested_restore_at = models.DateTimeField(null=True)


class RecoveryChallenge(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, null=True, on_delete=models.CASCADE)
    nonce_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True)


class ServerPolicy(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    invitations_paused = models.BooleanField(default=False)
    member_invitations = models.BooleanField(default=True)
    maintenance = models.CharField(max_length=300, blank=True)


class StorageUsage(models.Model):
    key = models.CharField(primary_key=True, max_length=80)
    used_bytes = models.PositiveBigIntegerField(default=0)
    pending_bytes = models.PositiveBigIntegerField(default=0)
    envelope_count = models.PositiveBigIntegerField(default=0)
    conversation_count = models.PositiveBigIntegerField(default=0)
