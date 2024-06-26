# Generated by Django 4.2.13 on 2024-05-09 18:15

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0206_auto_20240408_1344'),
    ]

    operations = [
        migrations.AlterField(
            model_name='enterprisegroupmembership',
            name='enterprise_customer_user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='memberships', to='enterprise.enterprisecustomeruser'),
        ),
        migrations.AlterField(
            model_name='enterprisegroupmembership',
            name='pending_enterprise_customer_user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='memberships', to='enterprise.pendingenterprisecustomeruser'),
        ),
    ]
