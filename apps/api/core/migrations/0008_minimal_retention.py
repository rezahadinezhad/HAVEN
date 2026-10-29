from django.db import migrations, models
from django.db.models.functions import Least
from datetime import timedelta


def retain_consumption(apps, schema_editor):
    # Preserve one-opening enforcement before removing the identifying timestamp.
    View = apps.get_model("core", "AttachmentView")
    View.objects.using(schema_editor.connection.alias).filter(opened_at__isnull=False).update(consumed=True)
    Attachment = apps.get_model("core", "EncryptedAttachment")
    # Existing uploads follow the same disclosed seven-day policy as new ones.
    Attachment.objects.using(schema_editor.connection.alias).update(
        expires_at=Least(models.F("expires_at"), models.F("created_at") + timedelta(days=7))
    )


class Migration(migrations.Migration):
    dependencies = [("core", "0007_attachmenttombstone")]
    operations = [
        migrations.AddField("attachmentview", "consumed", models.BooleanField(default=False)),
        # Irreversible: reopening old consumption records during rollback is unsafe.
        migrations.RunPython(retain_consumption),
        migrations.RemoveField("attachmentview", "opened_at"),
        migrations.AddField("messageenvelope", "ciphertext_retired", models.BooleanField(default=False)),
        migrations.AlterField(
            "messageenvelope", "received_at", models.DateTimeField(auto_now_add=True, null=True)
        ),
    ]
