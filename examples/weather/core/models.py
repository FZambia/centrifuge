from django.db import models


class Data(models.Model):

    weather_id = models.IntegerField("weather id")
    weather_type = models.CharField("weather type", max_length=30)
    weather_description = models.CharField("weather description", max_length=255)
    temperature = models.FloatField("temperature")
    wind_speed = models.FloatField("wind speed")
    humidity = models.FloatField("humidity")
    pressure = models.FloatField("pressure")

