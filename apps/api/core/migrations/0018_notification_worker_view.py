from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("core", "0017_contact_introduction_generation")]
    operations = [
        migrations.RunSQL(
            """CREATE VIEW haven_notification_targets WITH (security_barrier=true) AS
            SELECT o.id AS outbox_id, d.user_id
            FROM core_notificationoutbox o
            JOIN core_messageenvelope e ON e.id = o.envelope_id
            JOIN core_membership m ON m.conversation_id = e.conversation_id
            JOIN core_device d ON d.id = m.device_id
            WHERE o.sent_at IS NULL AND m.removed_at_epoch IS NULL""",
            "DROP VIEW haven_notification_targets",
        ),
    ]
