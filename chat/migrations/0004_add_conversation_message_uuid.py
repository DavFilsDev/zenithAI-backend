import uuid

from django.db import migrations, models


def assign_conversation_uuids(apps, schema_editor):
    Conversation = apps.get_model('chat', 'Conversation')
    for conversation in Conversation.objects.all():
        conversation.uuid = uuid.uuid4()
        conversation.save(update_fields=['uuid'])


def assign_message_uuids(apps, schema_editor):
    Message = apps.get_model('chat', 'Message')
    for message in Message.objects.all():
        message.uuid = uuid.uuid4()
        message.save(update_fields=['uuid'])


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0003_remove_message_tokens'),
    ]

    operations = [
        migrations.AddField(
            model_name='conversation',
            name='uuid',
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name='message',
            name='uuid',
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(assign_conversation_uuids, migrations.RunPython.noop),
        migrations.RunPython(assign_message_uuids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='conversation',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='message',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]