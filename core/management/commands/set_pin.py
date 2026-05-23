import getpass

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Hash a PIN for use in GYM_PIN_HASH env variable'

    def handle(self, *args, **options):
        pin = getpass.getpass('Enter PIN (input hidden): ')
        if not pin.strip():
            self.stderr.write(self.style.ERROR('PIN cannot be empty.'))
            return
        confirm = getpass.getpass('Confirm PIN: ')
        if pin != confirm:
            self.stderr.write(self.style.ERROR('PINs do not match.'))
            return
        pin_hash = make_password(pin)
        self.stdout.write('\nAdd this to your .env file:')
        self.stdout.write(self.style.SUCCESS(f'GYM_PIN_HASH={pin_hash}'))
        self.stdout.write('\nThen restart the server.')
