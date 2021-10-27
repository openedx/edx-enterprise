from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('degreed', '0002_auto_20180104_0103'),
    ]

    operations = [
        migrations.AlterField(
            model_name='degreedenterprisecustomerconfiguration',
            name='active',
            field=models.BooleanField(help_text='Is this configuration active?'),
        ),
        migrations.AlterField(
            model_name='historicaldegreedenterprisecustomerconfiguration',
            name='active',
            field=models.BooleanField(help_text='Is this configuration active?'),
        ),
    ]
