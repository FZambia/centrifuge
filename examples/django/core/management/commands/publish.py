from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from adjacent import Client


class Command(BaseCommand):

    option_list = BaseCommand.option_list + (
        make_option('--lat', default=0, dest='lat', type='float', help='Latitude'),
        make_option('--long', default=0, dest='long', type='float', help='Longitude'),
        make_option('--content', default='', dest='content', help='Content'),
    )

    help = 'Publish new event on map'

    def handle(self, *args, **options):
        client = Client()
        client.publish('map', {
            "lat": options.get("lat"),
            "long": options.get("long"),
            "content": options.get("content")
        })
        client.send()
