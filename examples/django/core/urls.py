from django.conf.urls import url
from django.conf.urls import patterns
from django.views.generic import TemplateView

urlpatterns = patterns(
    '',
    url('^$', TemplateView.as_view(template_name='core/index.html'), name="core_index"),
)
