from django.conf.urls import url, patterns
from django.contrib.auth.decorators import permission_required

from ikwen.billing.views import PaymentList
from econnect.views import AdminView, HomeView, PricingNumerilinkView, OrderList, CustomerRequestList, ChangeProduct, \
    ProductList, \
    ChangePackage, PackageList, EquipmentList, ChangeEquipment, ExtraList, ChangeExtra, PricingOfficelinkView, \
    PricingHomelinkView, PricingCorporatelinkView, MapsView, OrderConfirmView

urlpatterns = patterns(
    '',
    url(r'^$', HomeView.as_view(), name='home'),
    url(r'^numerilink$', PricingNumerilinkView.as_view(), name='numerilink'),
    url(r'^officelink$', PricingOfficelinkView.as_view(), name='officelink'),
    url(r'^homelink$', PricingHomelinkView.as_view(), name='homelink'),
    url(r'^corporatelink$', PricingCorporatelinkView.as_view(), name='corporatelink'),
    url(r'^order_confirm$', permission_required('econnect.ik_econnect_member')(OrderConfirmView.as_view()), name='order_confirm'),
    # url(r'^order_confirm/(?P<lat>.)/$', permission_required('econnect.ik_econnect_member')(OrderConfirmView.as_view()), name='order_confirm'),
    url(r'^admin/home$', permission_required('econnect.ik_econnect_admin')(AdminView.as_view()), name='admin'),
    url(r'^product_list/$', permission_required('econnect.ik_econnect_admin')(ProductList.as_view()), name='product_list'),
    url(r'^product/$', permission_required('econnect.ik_econnect_admin')(ChangeProduct.as_view()), name='change_product'),
    url(r'^product/(?P<object_id>[-\w]+)/$', permission_required('econnect.ik_econnect_admin')(ChangeProduct.as_view()), name='change_product'),
    url(r'^package_list/$', permission_required('econnect.ik_econnect_admin')(PackageList.as_view()), name='package_list'),
    url(r'^package/$', permission_required('econnect.ik_econnect_admin')(ChangePackage.as_view()), name='change_package'),
    url(r'^package/(?P<object_id>[-\w]+)/$', permission_required('econnect.ik_econnect_admin')(ChangePackage.as_view()), name='change_package'),
    url(r'^equipment_list/$', permission_required('econnect.ik_econnect_admin')(EquipmentList.as_view()), name='equipment_list'),
    url(r'^equipment/$', permission_required('econnect.ik_econnect_admin')(ChangeEquipment.as_view()), name='change_equipment'),
    url(r'^equipment/(?P<object_id>[-\w]+)/$', permission_required('econnect.ik_econnect_admin')(ChangeEquipment.as_view()), name='change_equipment'),
    url(r'^extra_list/$', permission_required('econnect.ik_econnect_admin')(ExtraList.as_view()), name='extra_list'),
    url(r'^extra/$', permission_required('econnect.ik_econnect_admin')(ChangeExtra.as_view()), name='change_extra'),
    url(r'^extra/(?P<object_id>[-\w]+)/$', permission_required('econnect.ik_econnect_admin')(ChangeExtra.as_view()), name='change_extra'),
    url(r'^admin/customer_order$', permission_required('econnect.ik_econnect_admin')(OrderList.as_view()), name='admin_order'),
    url(r'^admin/customer_request$', permission_required('econnect.ik_econnect_admin')(CustomerRequestList.as_view()), name='admin_request'),
    url(r'^admin/customer_payment$', permission_required('econnect.ik_econnect_admin')(PaymentList.as_view()), name='admin_payment'),
    url(r'^maps$', MapsView.as_view(), name='maps'),
)
