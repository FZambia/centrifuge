from django.conf import settings


def main(request):

    return {
        "WEATHER_CITY": settings.WEATHER_CITY
    }