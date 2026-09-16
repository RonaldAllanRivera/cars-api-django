from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Token accounting for the Claude Messages API, which reports cache writes and
    cache reads as separate counts beside input tokens rather than inside them.
    Renames keep existing rows' values; the two added columns default to zero.
    """

    dependencies = [
        ("publishing", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(model_name="aiusage", old_name="prompt_tokens", new_name="input_tokens"),
        migrations.RenameField(
            model_name="aiusage", old_name="cached_prompt_tokens", new_name="cache_read_input_tokens"
        ),
        migrations.RenameField(model_name="aiusage", old_name="completion_tokens", new_name="output_tokens"),
        migrations.RenameField(
            model_name="aiusage", old_name="cached_input_usd_per_1m", new_name="cache_read_usd_per_1m"
        ),
        migrations.RenameField(model_name="aiusage", old_name="finish_reason", new_name="stop_reason"),
        migrations.AddField(
            model_name="aiusage",
            name="cache_creation_input_tokens",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="aiusage",
            name="cache_write_usd_per_1m",
            field=models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=10),
        ),
    ]
