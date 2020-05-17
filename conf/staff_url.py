from django.conf.urls import patterns, include, url

from django.contrib.auth.decorators import permission_required, user_passes_test

from ikwen.accesscontrol.utils import is_staff
from ikwen.flatpages.views import ChangeFlatPage
from ikwen.flatpages.views import FlatPageList

from ikwen.billing.invoicing.views import ChangeSubscription

from econnect.views import Dashboard, Admin, PendingOrderList, PaidOrderList, ReportedOrderList, CanceledOrderList, \
    CustomerRequestList

urlpatterns = patterns(
    '',
    url(r'^billing/changeSubscription/$', permission_required('billing.ik_manage_subscription')(ChangeSubscription.as_view()), name='change_subscription'),
    url(r'^billing/changeSubscription/(?P<object_id>[-\w]+)/$', permission_required('billing.ik_manage_subscription')(ChangeSubscription.as_view()), name='change_subscription'),
    url(r'^billing/', include('ikwen.billing.urls', namespace='billing')),

    url(r'^flatPages/$', permission_required('flatpages.ik_webmaster')(FlatPageList.as_view()), name='flatpage_list'),
    url(r'^flatPage/$', permission_required('flatpages.ik_webmaster')(ChangeFlatPage.as_view()), name='change_flatpage'),
    url(r'^flatPage/(?P<page_id>[-\w]+)/$', permission_required('flatpages.ik_webmaster')(ChangeFlatPage.as_view()), name='change_flatpage'),

    url(r'^home/$', user_passes_test(is_staff)(Admin.as_view()), name='admin'),
    url(r'^dashboard/$', permission_required('econnect.ik_view_dashboard')(Dashboard.as_view()), name='dashboard'),
    url(r'^pendingOrder$', permission_required('econnect.ik_manage_sales')(PendingOrderList.as_view()), name='pending_order'),
    url(r'^paidOrder$', permission_required('econnect.ik_manage_sales')(PaidOrderList.as_view()), name='paid_order'),
    url(r'^reportedOrder$', permission_required('econnect.ik_manage_sales')(ReportedOrderList.as_view()), name='reported_order'),
    url(r'^canceledOrder$', permission_required('econnect.ik_manage_sales')(CanceledOrderList.as_view()), name='canceled_order'),
    url(r'^customerRequest$', permission_required('econnect.ik_econnect_admin')(CustomerRequestList.as_view()), name='admin_request'),
)
