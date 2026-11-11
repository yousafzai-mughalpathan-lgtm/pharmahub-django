from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('admin_panel', '0007_alter_adminactivitylog_action'),
    ]

    operations = [
        migrations.AddField(
            model_name='pharmacy',
            name='rating',
            field=models.DecimalField(decimal_places=1, default=0.0, max_digits=3),
        ),
    ]

