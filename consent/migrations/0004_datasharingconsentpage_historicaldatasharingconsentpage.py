# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import model_utils.fields
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0041_auto_20180212_1507'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('consent', '0003_historicaldatasharingconsent_history_change_reason'),
    ]

    operations = [
        migrations.CreateModel(
            name='DataSharingConsentPage',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('page_title', models.CharField(default='Data sharing consent required', help_text='Title of page', max_length=255)),
                ('left_sidebar_text', models.TextField(default="{enterprise_customer_name} has partnered with {platform_name} to offer you high-quality learning opportunities from the world's best universities.", help_text='Fill in a text for left sidebar paragraph. The following variables may be available:<br /><ul><li>enterprise_customer_name: A name of enterprise customer.</li><li>platform_name: Name of platform.</li></ul>', null=True, blank=True)),
                ('top_paragraph', models.TextField(default='First paragraph of page', help_text='Fill in a text for first paragraph of page. The following variables may be available:<br /><ul><li>enterprise_customer_name: A name of enterprise customer.</li><li>platform_name: Name of platform.</li></ul>', null=True, blank=True)),
                ('agreement_text', models.TextField(default='I agree to allow {platform_name} to share data about my enrollment, completion and performance in all {platform_name} courses and programs where my enrollment is sponsored by {enterprise_customer_name}.', help_text='Text next to agreement check mark', null=True, blank=True)),
                ('continue_text', models.CharField(default='Yes, continue', help_text='Text of agree button', max_length=255)),
                ('abort_text', models.CharField(default='No, take me back.', help_text='Text of decline link', max_length=255)),
                ('policy_dropdown_header', models.CharField(default='Data Sharing Policy', max_length=255, null=True, help_text='Text of policy drop down', blank=True)),
                ('policy_paragraph', models.TextField(default='Policy paragraph of page', help_text='Fill in a text for policy paragraph at the bottom of page. The following variables may be available:<br /><ul><li>enterprise_customer_name: A name of enterprise customer.</li><li>platform_name: Name of platform.</li></ul>', null=True, blank=True)),
                ('confirmation_modal_header', models.CharField(default='Are you aware...', help_text='Heading text of dialog box which appears when user decline to provide consent', max_length=255)),
                ('confirmation_modal_text', models.TextField(default='In order to start this {item} and use your discount, you must consent to share your {item} data with {enterprise_customer_name}.', help_text='Fill in a text for dialog which appears when user decline to provide consent. The following variables may be available:<br /><ul><li>enterprise_customer_name: A name of enterprise customer.</li><li>item: A string which is "course" or "program" depending on the type of consent.</li></ul>')),
                ('modal_affirm_decline_text', models.CharField(default='I decline', help_text='Text of decline button on confirmation dialog box', max_length=255)),
                ('modal_abort_decline_text', models.CharField(default='View the data sharing policy', help_text='Text of abort decline link on confirmation dialog box', max_length=255)),
                ('enterprise_customer', models.OneToOneField(related_name='enterprise_consent_page', to='enterprise.EnterpriseCustomer')),
            ],
        ),
        migrations.CreateModel(
            name='HistoricalDataSharingConsentPage',
            fields=[
                ('id', models.IntegerField(verbose_name='ID', db_index=True, auto_created=True, blank=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('page_title', models.CharField(default='Data sharing consent required', help_text='Title of page', max_length=255)),
                ('left_sidebar_text', models.TextField(default="{enterprise_customer_name} has partnered with {platform_name} to offer you high-quality learning opportunities from the world's best universities.", help_text='Fill in a text for left sidebar paragraph. The following variables may be available:<br /><ul><li>enterprise_customer_name: A name of enterprise customer.</li><li>platform_name: Name of platform.</li></ul>', null=True, blank=True)),
                ('top_paragraph', models.TextField(default='First paragraph of page', help_text='Fill in a text for first paragraph of page. The following variables may be available:<br /><ul><li>enterprise_customer_name: A name of enterprise customer.</li><li>platform_name: Name of platform.</li></ul>', null=True, blank=True)),
                ('agreement_text', models.TextField(default='I agree to allow {platform_name} to share data about my enrollment, completion and performance in all {platform_name} courses and programs where my enrollment is sponsored by {enterprise_customer_name}.', help_text='Text next to agreement check mark', null=True, blank=True)),
                ('continue_text', models.CharField(default='Yes, continue', help_text='Text of agree button', max_length=255)),
                ('abort_text', models.CharField(default='No, take me back.', help_text='Text of decline link', max_length=255)),
                ('policy_dropdown_header', models.CharField(default='Data Sharing Policy', max_length=255, null=True, help_text='Text of policy drop down', blank=True)),
                ('policy_paragraph', models.TextField(default='Policy paragraph of page', help_text='Fill in a text for policy paragraph at the bottom of page. The following variables may be available:<br /><ul><li>enterprise_customer_name: A name of enterprise customer.</li><li>platform_name: Name of platform.</li></ul>', null=True, blank=True)),
                ('confirmation_modal_header', models.CharField(default='Are you aware...', help_text='Heading text of dialog box which appears when user decline to provide consent', max_length=255)),
                ('confirmation_modal_text', models.TextField(default='In order to start this {item} and use your discount, you must consent to share your {item} data with {enterprise_customer_name}.', help_text='Fill in a text for dialog which appears when user decline to provide consent. The following variables may be available:<br /><ul><li>enterprise_customer_name: A name of enterprise customer.</li><li>item: A string which is "course" or "program" depending on the type of consent.</li></ul>')),
                ('modal_affirm_decline_text', models.CharField(default='I decline', help_text='Text of decline button on confirmation dialog box', max_length=255)),
                ('modal_abort_decline_text', models.CharField(default='View the data sharing policy', help_text='Text of abort decline link on confirmation dialog box', max_length=255)),
                ('history_id', models.AutoField(serialize=False, primary_key=True)),
                ('history_date', models.DateTimeField()),
                ('history_change_reason', models.CharField(max_length=100, null=True)),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('enterprise_customer', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='enterprise.EnterpriseCustomer', null=True)),
                ('history_user', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical data sharing consent page',
            },
        ),
    ]
