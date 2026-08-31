from django.contrib import admin

from apps.advertising.models import (
    AdvertisingAccount, AdCampaign, AdMetric, AdClickToken,
    AdLeadAttribution, AdEvent, AdConversionUpload, AdvertisingSettings,
)

admin.site.register(AdvertisingAccount)
admin.site.register(AdCampaign)
admin.site.register(AdMetric)
admin.site.register(AdClickToken)
admin.site.register(AdLeadAttribution)
admin.site.register(AdEvent)
admin.site.register(AdConversionUpload)
admin.site.register(AdvertisingSettings)
