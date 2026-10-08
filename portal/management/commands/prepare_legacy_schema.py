from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder


class Command(BaseCommand):
    help = (
        'Prepare a pre-migration ScoutBox portal schema for adoption by the '
        'portal initial migration without deleting existing data.'
    )

    def handle(self, *args, **options):
        recorder = MigrationRecorder(connection)
        portal_migration_applied = recorder.migration_qs.filter(
            app='portal', name='0001_initial'
        ).exists()
        if portal_migration_applied:
            self.stdout.write('Portal migration history already initialized; no legacy adoption needed.')
            return

        portal_app = apps.get_app_config('portal')
        models = list(portal_app.get_models())
        expected_tables = {model._meta.db_table for model in models}
        existing_tables = set(connection.introspection.table_names())
        existing_portal = expected_tables & existing_tables

        if not existing_portal:
            self.stdout.write('No legacy portal tables detected; normal initial migration will create them.')
            return

        self.stdout.write(
            f'Legacy portal schema detected ({len(existing_portal)}/{len(expected_tables)} model tables present).'
        )

        missing_models = [m for m in models if m._meta.db_table not in existing_tables]
        while missing_models:
            progressed = False
            for model in list(missing_models):
                unresolved = []
                for field in model._meta.local_fields:
                    remote = getattr(field, 'remote_field', None)
                    target = getattr(remote, 'model', None) if remote else None
                    if not target or not hasattr(target, '_meta'):
                        continue
                    if target is model:
                        continue
                    target_table = target._meta.db_table
                    if target._meta.app_label == 'portal' and target_table not in existing_tables:
                        unresolved.append(target_table)
                if unresolved:
                    continue

                through_tables = []
                for field in model._meta.local_many_to_many:
                    through = field.remote_field.through
                    if through._meta.auto_created:
                        through_tables.append(through._meta.db_table)
                collisions = [t for t in through_tables if t in existing_tables]
                if collisions:
                    raise CommandError(
                        f'Cannot safely create missing {model._meta.db_table}: auto-created '
                        f'ManyToMany table(s) already exist: {", ".join(collisions)}.'
                    )

                with connection.schema_editor() as editor:
                    editor.create_model(model)
                existing_tables = set(connection.introspection.table_names())
                missing_models.remove(model)
                progressed = True
                self.stdout.write(self.style.SUCCESS(f'Created missing legacy table {model._meta.db_table}'))

            if not progressed:
                names = ', '.join(m._meta.db_table for m in missing_models)
                raise CommandError(
                    'Could not safely complete the legacy portal schema because table '
                    f'dependencies are unresolved: {names}'
                )

        # fake-initial checks CreateModel table names, but not the automatically
        # generated ManyToMany join tables. Ensure those exist before adoption.
        existing_tables = set(connection.introspection.table_names())
        for model in models:
            for field in model._meta.local_many_to_many:
                through = field.remote_field.through
                if not through._meta.auto_created:
                    continue
                table = through._meta.db_table
                if table in existing_tables:
                    continue
                with connection.schema_editor() as editor:
                    editor.create_model(through)
                existing_tables.add(table)
                self.stdout.write(self.style.SUCCESS(f'Created missing legacy join table {table}'))

        self.stdout.write(self.style.SUCCESS('Legacy portal schema is ready for --fake-initial adoption.'))
