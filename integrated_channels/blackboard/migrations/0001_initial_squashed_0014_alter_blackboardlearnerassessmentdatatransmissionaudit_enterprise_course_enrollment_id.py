# Generated by Django 3.2.11 on 2022-02-10 15:47

from django.conf import settings
from django.db import migrations, models
import django.db.migrations.operations.special
import django.db.models.deletion
import django.utils.timezone
import model_utils.fields
import simple_history.models
import uuid


def create_uuid(apps, schema_editor):
    BlackboardEnterpriseCustomerConfiguration = apps.get_model('blackboard', 'BlackboardEnterpriseCustomerConfiguration')
    for config in BlackboardEnterpriseCustomerConfiguration.objects.all():
        config.uuid = uuid.uuid4()
        config.save()


class Migration(migrations.Migration):

    replaces = [('blackboard', '0001_initial'), ('blackboard', '0002_auto_20200930_1723'), ('blackboard', '0003_blackboardlearnerdatatransmissionaudit'), ('blackboard', '0004_blackboard_tx_chunk_size_default_1'), ('blackboard', '0005_blackboardlearnerassessmentdatatransmissionaudit'), ('blackboard', '0006_auto_20210708_1446'), ('blackboard', '0007_auto_20210909_1536'), ('blackboard', '0008_auto_20210923_1727'), ('blackboard', '0009_alter_blackboardenterprisecustomerconfiguration_enterprise_customer'), ('blackboard', '0010_auto_20211221_1532'), ('blackboard', '0011_auto_20220126_1837'), ('blackboard', '0012_auto_20220131_1539'), ('blackboard', '0013_blacboardglobalconfiguration'), ('blackboard', '0014_alter_blackboardlearnerassessmentdatatransmissionaudit_enterprise_course_enrollment_id')]

    dependencies = [
        ('enterprise', '0151_add_is_active_to_invite_key'),
        ('enterprise', '0113_auto_20200914_2054'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BlackboardLearnerDataTransmissionAudit',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('blackboard_user_email', models.EmailField(help_text='The learner`s Blackboard email. This must match the email on edX in order for both learner and content metadata integrations.', max_length=255)),
                ('completed_timestamp', models.CharField(help_text='Represents the Blackboard representation of a timestamp: yyyy-mm-dd, which is always 10 characters.', max_length=10)),
                ('course_id', models.CharField(max_length=255)),
                ('course_completed', models.BooleanField(default=True, help_text="The learner's course completion status transmitted to Blackboard.")),
                ('enterprise_course_enrollment_id', models.PositiveIntegerField(db_index=True)),
                ('grade', models.DecimalField(blank=True, decimal_places=2, max_digits=3, null=True)),
                ('total_hours', models.FloatField(blank=True, null=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('error_message', models.TextField(blank=True)),
                ('status', models.CharField(max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name='BlackboardLearnerAssessmentDataTransmissionAudit',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('blackboard_user_email', models.CharField(max_length=255)),
                ('enterprise_course_enrollment_id', models.IntegerField(db_index=True)),
                ('course_id', models.CharField(help_text="The course run's key which is used to uniquely identify the course for blackboard.", max_length=255)),
                ('subsection_id', models.CharField(db_index=True, help_text="The course's subsections's key.", max_length=255)),
                ('grade_point_score', models.FloatField(help_text='The amount of points that the learner scored on the subsection.')),
                ('grade_points_possible', models.FloatField(help_text='The total amount of points that the learner could score on the subsection.')),
                ('grade', models.FloatField(help_text='The grade an enterprise learner received on the reported subsection.')),
                ('subsection_name', models.CharField(help_text="The name given to the subsection being reported. Used for displaying on external LMS'.", max_length=255)),
                ('status', models.CharField(max_length=100)),
                ('error_message', models.TextField(blank=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='BlackboardEnterpriseCustomerConfiguration',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('active', models.BooleanField(help_text='Is this configuration active?')),
                ('transmission_chunk_size', models.IntegerField(default=1, help_text='The maximum number of data items to transmit to the integrated channel with each request.')),
                ('channel_worker_username', models.CharField(blank=True, help_text='Enterprise channel worker username to get JWT tokens for authenticating LMS APIs.', max_length=255, null=True)),
                ('catalogs_to_transmit', models.TextField(blank=True, help_text='A comma-separated list of catalog UUIDs to transmit. If blank, all customer catalogs will be transmitted. If there are overlapping courses in the customer catalogs, the overlapping course metadata will be selected from the newest catalog.', null=True)),
                ('client_id', models.CharField(help_text='The API Client ID provided to edX by the enterprise customer to be used to make API calls on behalf of the customer. Called Application Key in Blackboard', max_length=255, null=True, verbose_name='API Client ID or Blackboard Application Key')),
                ('client_secret', models.CharField(help_text='The API Client Secret provided to edX by the enterprise customer to be used to make  API calls on behalf of the customer. Called Application Secret in Blackboard', max_length=255, null=True, verbose_name='API Client Secret or Application Secret')),
                ('blackboard_base_url', models.CharField(help_text='The base URL used for API requests to Blackboard, i.e. https://blackboard.com.', max_length=255, null=True, verbose_name='Base URL')),
                ('refresh_token', models.CharField(blank=True, help_text='The refresh token provided by Blackboard along with the access token request,used to re-request the access tokens over multiple client sessions.', max_length=255, verbose_name='Oauth2 Refresh Token')),
                ('enterprise_customer', models.ForeignKey(help_text='Enterprise Customer associated with the configuration.', on_delete=django.db.models.deletion.CASCADE, to='enterprise.enterprisecustomer')),
                ('idp_id', models.CharField(blank=True, help_text='If provided, will be used as IDP slug to locate remote id for learners', max_length=255, null=True)),
                ('disable_learner_data_transmissions', models.BooleanField(default=False, help_text='When set to True, the configured customer will no longer receive learner data transmissions, both scheduled and signal based', verbose_name='Disable Learner Data Transmission')),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, help_text='A UUID for use in public-facing urls such as oauth state variables.', null=True)),
            ],
        ),
        migrations.CreateModel(
            name='HistoricalBlackboardEnterpriseCustomerConfiguration',
            fields=[
                ('id', models.IntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False, verbose_name='created')),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, editable=False, verbose_name='modified')),
                ('active', models.BooleanField(help_text='Is this configuration active?')),
                ('transmission_chunk_size', models.IntegerField(default=1, help_text='The maximum number of data items to transmit to the integrated channel with each request.')),
                ('channel_worker_username', models.CharField(blank=True, help_text='Enterprise channel worker username to get JWT tokens for authenticating LMS APIs.', max_length=255, null=True)),
                ('catalogs_to_transmit', models.TextField(blank=True, help_text='A comma-separated list of catalog UUIDs to transmit. If blank, all customer catalogs will be transmitted. If there are overlapping courses in the customer catalogs, the overlapping course metadata will be selected from the newest catalog.', null=True)),
                ('client_id', models.CharField(help_text='The API Client ID provided to edX by the enterprise customer to be used to make API calls on behalf of the customer. Called Application Key in Blackboard', max_length=255, null=True, verbose_name='API Client ID or Blackboard Application Key')),
                ('client_secret', models.CharField(help_text='The API Client Secret provided to edX by the enterprise customer to be used to make  API calls on behalf of the customer. Called Application Secret in Blackboard', max_length=255, null=True, verbose_name='API Client Secret or Application Secret')),
                ('blackboard_base_url', models.CharField(help_text='The base URL used for API requests to Blackboard, i.e. https://blackboard.com.', max_length=255, null=True, verbose_name='Base URL')),
                ('refresh_token', models.CharField(blank=True, help_text='The refresh token provided by Blackboard along with the access token request,used to re-request the access tokens over multiple client sessions.', max_length=255, verbose_name='Oauth2 Refresh Token')),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_change_reason', models.CharField(max_length=100, null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('enterprise_customer', models.ForeignKey(blank=True, db_constraint=False, help_text='Enterprise Customer associated with the configuration.', null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='enterprise.enterprisecustomer')),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('idp_id', models.CharField(blank=True, help_text='If provided, will be used as IDP slug to locate remote id for learners', max_length=255, null=True)),
                ('disable_learner_data_transmissions', models.BooleanField(default=False, help_text='When set to True, the configured customer will no longer receive learner data transmissions, both scheduled and signal based', verbose_name='Disable Learner Data Transmission')),
                ('uuid', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, help_text='A UUID for use in public-facing urls such as oauth state variables.')),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical blackboard enterprise customer configuration',
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.RunPython(
            code=create_uuid,
            reverse_code=django.db.migrations.operations.special.RunPython.noop,
        ),
        migrations.AlterField(
            model_name='blackboardenterprisecustomerconfiguration',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, help_text='A UUID for use in public-facing urls such as oauth state variables.', unique=True),
        ),
        migrations.AlterField(
            model_name='blackboardenterprisecustomerconfiguration',
            name='blackboard_base_url',
            field=models.CharField(blank=True, default='', help_text='The base URL used for API requests to Blackboard, i.e. https://blackboard.com.', max_length=255, verbose_name='Base URL'),
        ),
        migrations.AlterField(
            model_name='blackboardenterprisecustomerconfiguration',
            name='catalogs_to_transmit',
            field=models.TextField(blank=True, default='', help_text='A comma-separated list of catalog UUIDs to transmit. If blank, all customer catalogs will be transmitted. If there are overlapping courses in the customer catalogs, the overlapping course metadata will be selected from the newest catalog.'),
        ),
        migrations.AlterField(
            model_name='blackboardenterprisecustomerconfiguration',
            name='channel_worker_username',
            field=models.CharField(blank=True, default='', help_text='Enterprise channel worker username to get JWT tokens for authenticating LMS APIs.', max_length=255),
        ),
        migrations.AlterField(
            model_name='blackboardenterprisecustomerconfiguration',
            name='client_id',
            field=models.CharField(blank=True, default='', help_text='The API Client ID provided to edX by the enterprise customer to be used to make API calls on behalf of the customer. Called Application Key in Blackboard', max_length=255, verbose_name='API Client ID or Blackboard Application Key'),
        ),
        migrations.AlterField(
            model_name='blackboardenterprisecustomerconfiguration',
            name='client_secret',
            field=models.CharField(blank=True, default='', help_text='The API Client Secret provided to edX by the enterprise customer to be used to make  API calls on behalf of the customer. Called Application Secret in Blackboard', max_length=255, verbose_name='API Client Secret or Application Secret'),
        ),
        migrations.AlterField(
            model_name='blackboardenterprisecustomerconfiguration',
            name='idp_id',
            field=models.CharField(blank=True, default='', help_text='If provided, will be used as IDP slug to locate remote id for learners', max_length=255),
        ),
        migrations.AlterField(
            model_name='historicalblackboardenterprisecustomerconfiguration',
            name='blackboard_base_url',
            field=models.CharField(blank=True, default='', help_text='The base URL used for API requests to Blackboard, i.e. https://blackboard.com.', max_length=255, verbose_name='Base URL'),
        ),
        migrations.AlterField(
            model_name='historicalblackboardenterprisecustomerconfiguration',
            name='catalogs_to_transmit',
            field=models.TextField(blank=True, default='', help_text='A comma-separated list of catalog UUIDs to transmit. If blank, all customer catalogs will be transmitted. If there are overlapping courses in the customer catalogs, the overlapping course metadata will be selected from the newest catalog.'),
        ),
        migrations.AlterField(
            model_name='historicalblackboardenterprisecustomerconfiguration',
            name='channel_worker_username',
            field=models.CharField(blank=True, default='', help_text='Enterprise channel worker username to get JWT tokens for authenticating LMS APIs.', max_length=255),
        ),
        migrations.AlterField(
            model_name='historicalblackboardenterprisecustomerconfiguration',
            name='client_id',
            field=models.CharField(blank=True, default='', help_text='The API Client ID provided to edX by the enterprise customer to be used to make API calls on behalf of the customer. Called Application Key in Blackboard', max_length=255, verbose_name='API Client ID or Blackboard Application Key'),
        ),
        migrations.AlterField(
            model_name='historicalblackboardenterprisecustomerconfiguration',
            name='client_secret',
            field=models.CharField(blank=True, default='', help_text='The API Client Secret provided to edX by the enterprise customer to be used to make  API calls on behalf of the customer. Called Application Secret in Blackboard', max_length=255, verbose_name='API Client Secret or Application Secret'),
        ),
        migrations.AlterField(
            model_name='historicalblackboardenterprisecustomerconfiguration',
            name='idp_id',
            field=models.CharField(blank=True, default='', help_text='If provided, will be used as IDP slug to locate remote id for learners', max_length=255),
        ),
        migrations.AddField(
            model_name='blackboardenterprisecustomerconfiguration',
            name='display_name',
            field=models.CharField(blank=True, default='', help_text='A configuration nickname.', max_length=30),
        ),
        migrations.AddField(
            model_name='historicalblackboardenterprisecustomerconfiguration',
            name='display_name',
            field=models.CharField(blank=True, default='', help_text='A configuration nickname.', max_length=30),
        ),
        migrations.CreateModel(
            name='BlackboardGlobalConfiguration',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('change_date', models.DateTimeField(auto_now_add=True, verbose_name='Change date')),
                ('enabled', models.BooleanField(default=False, verbose_name='Enabled')),
                ('app_key', models.CharField(blank=True, default='', help_text='The application API key identifying the edX integration application to be used in the API oauth handshake.', max_length=255, verbose_name='Blackboard Application Key')),
                ('app_secret', models.CharField(blank=True, default='', help_text='The application API secret used to make to identify ourselves as the edX integration app to customer instances. Called Application Secret in Blackboard', max_length=255, verbose_name='API Client Secret or Application Secret')),
                ('changed_by', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, verbose_name='Changed by')),
            ],
        ),
    ]
