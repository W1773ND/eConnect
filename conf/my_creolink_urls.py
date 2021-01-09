from django.conf.urls import patterns, url, include

from django.contrib.auth.decorators import login_required

from econnect.navision import CustomInvoiceList


from econnect.views import SiteList, ChangeSite
from econnect.my_creolink import ProfileList, ChangeProfile, UncompletedOrderList


urlpatterns = patterns(
    '',
    url(r'^$', login_required(CustomInvoiceList.as_view()), name='my_creolink'),
    url(r'^UncompleteOrder/$', login_required(UncompletedOrderList.as_view()), name='uncompleted_order'),
    url(r'^console/$', login_required(CustomInvoiceList.as_view()), name='console'),
    url(r'^profiles/$', login_required(ProfileList.as_view()), name='profile_list'),
    url(r'^profile/(?P<object_id>[-\w]+)/$', login_required(ChangeProfile.as_view()), name='change_profile'),
    url(r'^services/$', login_required(SiteList.as_view()), name='site_list'),
    url(r'^service/(?P<object_id>[-\w]+)/$', login_required(ChangeSite.as_view()), name='change_site'),
    url(r'^service/$', login_required(ChangeSite.as_view()), name='change_site'),

    url(r'^STAFF/', include('ikwen.core.urls', namespace='ikwen')),
)
