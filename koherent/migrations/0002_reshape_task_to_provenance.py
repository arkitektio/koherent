import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """Reshape Task from the legacy Rekuest task header to the provenance token.

    The legacy columns (app/action/args, task_id/parent_id) have no mapping onto
    the new provenance-token claims, and the new unique columns (token_id) cannot
    be backfilled, so the table is dropped and recreated. The `task` FK on host
    history tables is SET_NULL by id, so existing history links orphan to NULL.
    This is intentional, documented provenance loss for a breaking major bump.
    """

    dependencies = [
        ("koherent", "0001_initial"),
        ("authentikate", "0005_alter_client_client_id"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.DeleteModel(name="Task"),
        migrations.CreateModel(
            name="Task",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("assignation_id", models.CharField(help_text="This assignation id (provenance tsk).", max_length=1000, unique=True)),
                ("parent_assignation_id", models.CharField(blank=True, help_text="The immediate parent assignation id, if any.", max_length=1000, null=True)),
                ("root_assignation_id", models.CharField(help_text="The root assignation id of the whole causal tree.", max_length=1000)),
                ("assigner_sub", models.CharField(help_text="The raw root human causer sub (rcb claim).", max_length=1000)),
                ("caller_sub", models.CharField(help_text="The immediate causer of this hop (sub claim).", max_length=1000)),
                ("agent_sub", models.CharField(help_text="The executing agent user sub (act.sub claim).", max_length=1000)),
                ("agent_client_id", models.CharField(help_text="The executing agent OAuth client id (act.cid claim).", max_length=1000)),
                ("issuer", models.CharField(help_text="The provenance issuer id (iss claim).", max_length=1000)),
                ("token_id", models.CharField(help_text="The unique single-use token id (jti claim).", max_length=1000, unique=True)),
                ("args_hash", models.CharField(help_text="The SHA-256 of the canonicalized args (ahs claim).", max_length=1000)),
                ("args_hash_algorithm", models.CharField(help_text="The args canonicalization algorithm/version (aha claim).", max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("assigner", models.ForeignKey(blank=True, help_text="The root human causer (resolved from the rcb claim).", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assigned_tasks", to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(help_text="The organization the task ran in", on_delete=django.db.models.deletion.CASCADE, related_name="tasks", to="authentikate.organization")),
            ],
        ),
    ]
