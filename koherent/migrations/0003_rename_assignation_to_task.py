from django.db import migrations, models


class Migration(migrations.Migration):
    """Rename the Task identifier fields from the legacy "assignation" name.

    The columns carry the same values; only the names change
    (assignation_id -> task_id, and the parent/root variants), so a plain
    RenameField preserves all existing rows. The AlterFields only refresh the
    help_text wording to match.
    """

    dependencies = [
        ("koherent", "0002_reshape_task_to_provenance"),
    ]

    operations = [
        migrations.RenameField(
            model_name="task",
            old_name="assignation_id",
            new_name="task_id",
        ),
        migrations.RenameField(
            model_name="task",
            old_name="parent_assignation_id",
            new_name="parent_task_id",
        ),
        migrations.RenameField(
            model_name="task",
            old_name="root_assignation_id",
            new_name="root_task_id",
        ),
        migrations.AlterField(
            model_name="task",
            name="task_id",
            field=models.CharField(
                help_text="This task id (provenance tsk).", max_length=1000, unique=True
            ),
        ),
        migrations.AlterField(
            model_name="task",
            name="parent_task_id",
            field=models.CharField(
                blank=True,
                help_text="The immediate parent task id, if any.",
                max_length=1000,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="task",
            name="root_task_id",
            field=models.CharField(
                help_text="The root task id of the whole causal tree.", max_length=1000
            ),
        ),
    ]
