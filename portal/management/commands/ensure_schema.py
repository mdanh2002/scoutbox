from django.core.management.base import BaseCommand
from django.db import connection
from portal.models import Application, ImportCandidate, PortalSettings


class Command(BaseCommand):
    help = 'Apply small backward-compatible schema additions for upgrades from pre-migration MVP builds.'

    additions = [
        (Application, 'notes'),
        (ImportCandidate, 'outcome_status'),
        (ImportCandidate, 'notes'),
        (ImportCandidate, 'inference_method'),
        (ImportCandidate, 'inference_metadata'),
        (PortalSettings, 'company_reapply_window_days'),
        (PortalSettings, 'same_company_fit_penalty'),
        (PortalSettings, 'same_company_unknown_date_penalty'),
        (PortalSettings, 'discovery_mode'),
    ]

    def handle(self, *args, **options):
        existing_tables=set(connection.introspection.table_names())
        with connection.schema_editor() as editor:
            for model, field_name in self.additions:
                table=model._meta.db_table
                if table not in existing_tables:
                    continue
                with connection.cursor() as cursor:
                    cols={c.name for c in connection.introspection.get_table_description(cursor, table)}
                if field_name in cols:
                    continue
                field=model._meta.get_field(field_name)
                editor.add_field(model, field)
                self.stdout.write(self.style.SUCCESS(f'Added {table}.{field_name}'))
