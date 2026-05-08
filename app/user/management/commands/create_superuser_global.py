from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = "Creates a global superuser with no tenant"

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--password", required=True)
        parser.add_argument("--name", default="")

    def handle(self, *args, **options):
        user = User.objects.create_superuser(
            email=options["email"],
            password=options["password"],
            name=options["name"],
        )
        self.stdout.write(self.style.SUCCESS(f"Superuser created: {user.email}"))