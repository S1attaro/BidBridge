from django.db import migrations, models


def copy_states(apps, schema_editor):
    Profile = apps.get_model("matches", "ContractorProfile")
    for p in Profile.objects.all():
        p.states = [p.home_state] + [s for s in p.other_states if s != p.home_state]
        p.save(update_fields=["states"])


class Migration(migrations.Migration):
    dependencies = [("matches", "0001_initial")]

    operations = [
        migrations.AddField(model_name="contractorprofile", name="states", field=models.JSONField(default=list)),
        migrations.RunPython(copy_states, migrations.RunPython.noop),
        migrations.RemoveField(model_name="contractorprofile", name="home_state"),
        migrations.RemoveField(model_name="contractorprofile", name="other_states"),
    ]
