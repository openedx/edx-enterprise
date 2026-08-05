import django.utils.timezone
from django.db import migrations, models

import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0001_squashed_0092_auto_20200312_1650'),
    ]

    operations = [
        migrations.CreateModel(
            name='XAPILRSConfiguration',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('created', model_utils.fields.AutoCreatedField(verbose_name='created', default=django.utils.timezone.now, editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(verbose_name='modified', default=django.utils.timezone.now, editable=False)),
                ('version', models.CharField(help_text='Version of X-API.', default='1.0.1', max_length=16)),
                ('endpoint', models.URLField(help_text='URL of the LRS.')),
                ('key', models.CharField(help_text='Key of X-API LRS.', verbose_name='Client ID', max_length=255)),
                ('secret', models.CharField(help_text='secret of X-API LRS.', verbose_name='Client Secret', max_length=255)),
                ('active', models.BooleanField(help_text='Is this configuration active?')),
                ('enterprise_customer', models.OneToOneField(to='enterprise.EnterpriseCustomer', help_text='Enterprise Customer associated with the configuration.', on_delete=models.CASCADE)),
            ],
        ),
    ]
