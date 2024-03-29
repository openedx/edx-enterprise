# Generated by Django 1.11.23 on 2019-09-25 07:30


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cornerstone', '0004_cornerstoneglobalconfiguration_languages'),
    ]

    operations = [
        migrations.AddField(
            model_name='cornerstoneenterprisecustomerconfiguration',
            name='channel_worker_username',
            field=models.CharField(blank=True, help_text='Enterprise channel worker username to get JWT tokens for authenticating LMS APIs.', max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='historicalcornerstoneenterprisecustomerconfiguration',
            name='channel_worker_username',
            field=models.CharField(blank=True, help_text='Enterprise channel worker username to get JWT tokens for authenticating LMS APIs.', max_length=255, null=True),
        ),
    ]
