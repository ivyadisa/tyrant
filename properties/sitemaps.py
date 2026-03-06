# properties/sitemaps.py
from django.contrib.sitemaps import Sitemap
from .models import Apartment, Unit

class ApartmentSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        # include all apartments, no filter
        return Apartment.objects.all()

    def lastmod(self, obj):
        return obj.updated_at


class UnitSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.9

    def items(self):
        # include all units
        return Unit.objects.all()

    def lastmod(self, obj):
        return obj.updated_at
