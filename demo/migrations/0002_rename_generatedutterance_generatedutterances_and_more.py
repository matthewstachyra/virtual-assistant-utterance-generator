# Generated by Django 4.0.5 on 2022-07-07 03:17

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('demo', '0001_initial'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='GeneratedUtterance',
            new_name='GeneratedUtterances',
        ),
        migrations.RenameField(
            model_name='generatedutterances',
            old_name='seed_text',
            new_name='seed_utterance',
        ),
    ]
