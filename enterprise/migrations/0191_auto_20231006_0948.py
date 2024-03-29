# Generated by Django 3.2.21 on 2023-10-06 09:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0190_auto_20231003_0719'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='chatgptresponse',
            options={'verbose_name': 'ChatGPT Response', 'verbose_name_plural': 'ChatGPT Responses'},
        ),
        migrations.AddField(
            model_name='chatgptresponse',
            name='prompt_type',
            field=models.CharField(choices=[('learner_progress', 'Learner progress'), ('learner_engagement', 'Learner engagement')], help_text='Prompt type.', max_length=32, null=True),
        ),
    ]
