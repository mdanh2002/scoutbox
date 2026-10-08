import os
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Reset the portal administrator password to the configured development default.'

    def add_arguments(self, parser):
        parser.add_argument('--email', default=os.getenv('PORTAL_ADMIN_EMAIL', 'admin@portal.test'))
        parser.add_argument('--password', default=os.getenv('PORTAL_ADMIN_PASSWORD', 'ChangeMe-Portal-123!'))

    def handle(self, *args, **opts):
        email=(opts['email'] or 'admin@portal.test').strip()
        password=opts['password'] or 'ChangeMe-Portal-123!'
        user=User.objects.filter(username=email).first() or User.objects.filter(email__iexact=email).first()
        created=False
        if not user:
            user=User(username=email,email=email,first_name='Portal Admin',is_staff=True,is_superuser=True,is_active=True)
            created=True
        user.username=email
        if not user.email:
            user.email=email
        user.is_active=True; user.is_staff=True; user.is_superuser=True
        user.set_password(password); user.save()
        self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Reset'} administrator: {email}"))
        self.stdout.write(f'Default password: {password}')
        self.stdout.write(self.style.WARNING('Change this password after signing in if the portal is reachable by anyone else.'))
