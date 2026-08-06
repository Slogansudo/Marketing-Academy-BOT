from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("subscriptions", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="pendingcheckout",
            name="pending_card_token",
            field=models.CharField(max_length=255, blank=True, null=True),
        ),
        migrations.AddField(
            model_name="pendingcheckout",
            name="pending_masked_pan",
            field=models.CharField(max_length=25, blank=True, null=True),
        ),
        migrations.AddField(
            model_name="pendingcheckout",
            name="verify_attempts",
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
