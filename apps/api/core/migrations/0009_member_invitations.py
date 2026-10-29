from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0008_minimal_retention")]
    operations = [
        migrations.AddField("serverpolicy", "member_invitations", models.BooleanField(default=True))
    ]
