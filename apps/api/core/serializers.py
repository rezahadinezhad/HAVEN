import base64
import binascii
from rest_framework import serializers as s


class StrictSerializer(s.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise s.ValidationError({"non_field_errors": ["Unknown or invalid fields"]})
        return super().to_internal_value(data)


class Base64(s.CharField):
    def __init__(self, **kwargs):
        kwargs.setdefault("max_length", 1400000)
        kwargs.setdefault("trim_whitespace", False)
        super().__init__(**kwargs)

    def to_internal_value(self, value):
        value = super().to_internal_value(value)
        try:
            result = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError):
            raise s.ValidationError("Invalid encoding") from None
        if not result:
            raise s.ValidationError("Empty bytes")
        return result


class Login(StrictSerializer):
    username = s.RegexField(r"^[a-zA-Z0-9_.-]{3,64}$")
    password = s.CharField(max_length=256, trim_whitespace=False)


class Redeem(Login):
    token = s.CharField(min_length=40, max_length=100, trim_whitespace=False)
    display_name = s.CharField(min_length=1, max_length=80)


class Invite(StrictSerializer):
    intended_username = s.RegexField(r"^[a-zA-Z0-9_.-]{3,64}$", required=False, allow_blank=True)
    hours = s.IntegerField(min_value=1, max_value=72, default=24)


class Password(StrictSerializer):
    old_password = s.CharField(max_length=256, trim_whitespace=False)
    new_password = s.CharField(max_length=256, trim_whitespace=False)


class UserPatch(StrictSerializer):
    is_active = s.BooleanField(required=False)
    role = s.ChoiceField(choices=["member", "community_admin"], required=False)


class Enrollment(StrictSerializer):
    id = s.UUIDField()
    label = s.CharField(max_length=80)
    public_key = Base64(max_length=44)
    identity = s.CharField(max_length=200)


class Approval(StrictSerializer):
    device_id = s.UUIDField()
    signature = Base64(max_length=88)


class Package(StrictSerializer):
    package = Base64(max_length=30000)


class SignedHeader(StrictSerializer):
    header = s.JSONField()

    def validate_header(self, value):
        from .protocol import canonical

        if not isinstance(value, dict) or len(canonical(value)) > 65536:
            raise s.ValidationError("Invalid or oversized authenticated header")
        transition = value.get("transition")
        if transition is not None and not isinstance(transition, dict):
            raise s.ValidationError("Invalid transition")
        return value

    signature = Base64(max_length=88)


class CreateConversation(SignedHeader):
    id = s.UUIDField()
    kind = s.ChoiceField(choices=["direct", "group"])
    group_id = s.CharField(max_length=100)


class Envelope(SignedHeader):
    v = s.IntegerField(min_value=1, max_value=1)
    client_message_id = s.UUIDField()
    epoch = s.IntegerField(min_value=0, max_value=2**53 - 1)
    ciphertext = Base64(max_length=200000)


class Control(Envelope):
    action = s.ChoiceField(choices=["add", "remove", "update", "transfer", "role"])
    role = s.ChoiceField(choices=["member", "moderator"], required=False)
    device_id = s.UUIDField(required=False)
    key_package_id = s.UUIDField(required=False)
    welcome = Base64(max_length=200000, required=False)


class Ack(StrictSerializer):
    seq = s.IntegerField(min_value=0, max_value=2**53 - 1)


class AttachmentInit(StrictSerializer):
    id = s.UUIDField()
    conversation_id = s.UUIDField()
    ciphertext_size = s.IntegerField(min_value=16, max_value=25 * 1024 * 1024 + 128 * 64)
    chunk_count = s.IntegerField(min_value=1, max_value=64)
    view_once = s.BooleanField(default=False)


class AttachmentViewToken(StrictSerializer):
    token = s.RegexField(r"^[0-9a-f]{64}$", min_length=64, max_length=64)


class RecoveryKey(StrictSerializer):
    public_key = Base64(max_length=44)


class RecoveryStart(StrictSerializer):
    user_id = s.UUIDField()


class RecoveryReset(StrictSerializer):
    challenge_id = s.UUIDField()
    nonce = s.CharField(min_length=64, max_length=64)
    new_password = s.CharField(max_length=256, trim_whitespace=False)
    device = Enrollment()
    recovery_public_key = Base64(max_length=44)
    signature = Base64(max_length=88)
    device_signature = Base64(max_length=88)


class Leave(StrictSerializer):
    action = s.ChoiceField(choices=["leave"])
    signature = Base64(max_length=88)


class ServerPolicy(StrictSerializer):
    invitations_paused = s.BooleanField(required=False)
    member_invitations = s.BooleanField(required=False)
    maintenance = s.CharField(max_length=300, allow_blank=True, required=False)


class DisableAccount(StrictSerializer):
    password = s.CharField(max_length=256, trim_whitespace=False)
    confirmation = s.ChoiceField(choices=["DISABLE"])
