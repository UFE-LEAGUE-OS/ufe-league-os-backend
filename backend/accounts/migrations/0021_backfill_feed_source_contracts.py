from django.db import migrations


def copy_legacy_feed_sources_forward(apps, schema_editor):
    FeedItem = apps.get_model("accounts", "FeedItem")
    db_alias = schema_editor.connection.alias

    for item in FeedItem.objects.using(db_alias).iterator():
        update_fields = []
        if not item.source_content_type and item.content_type:
            item.source_content_type = item.content_type
            update_fields.append("source_content_type")
        if item.source_object_id is None and item.object_id > 0:
            item.source_object_id = item.object_id
            update_fields.append("source_object_id")
        if update_fields:
            item.save(using=db_alias, update_fields=update_fields)


def copy_typed_feed_sources_backward(apps, schema_editor):
    FeedItem = apps.get_model("accounts", "FeedItem")
    db_alias = schema_editor.connection.alias

    for item in FeedItem.objects.using(db_alias).iterator():
        update_fields = []
        if not item.content_type and item.source_content_type:
            item.content_type = item.source_content_type
            update_fields.append("content_type")
        if item.object_id == 0 and item.source_object_id is not None:
            item.object_id = item.source_object_id
            update_fields.append("object_id")
        if update_fields:
            item.save(using=db_alias, update_fields=update_fields)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0020_restore_role_follow_feed_schema"),
    ]

    operations = [
        migrations.RunPython(
            copy_legacy_feed_sources_forward,
            copy_typed_feed_sources_backward,
        ),
    ]
