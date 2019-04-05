from django.conf.urls import url, patterns
from django.contrib.auth.decorators import permission_required

from ikwen.billing.views import PaymentList
from econnect.views import Admin, Home, PricingNumerilink, OrderList, CustomerRequestList, ChangeProduct, ProductList, \
    ChangePackage, PackageList, EquipmentList, ChangeEquipment, ExtraList, ChangeExtra

urlpatterns = patterns(
    '',
    url(r'^$', Home.as_view(), name='home'),
    url(r'^numerilink$', PricingNumerilink.as_view(), name='numerilink'),
    url(r'^admin/home$', permission_required('econnect.ik_econnect_admin')(Admin.as_view()), name='admin'),
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
)
