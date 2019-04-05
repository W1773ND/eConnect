from django.shortcuts import render
from django_mongodb_engine.contrib import _compiler_for_queryset

from ikwen.accesscontrol.backends import UMBRELLA
from ikwen.core.views import HybridListView, ChangeObjectBase
from ikwen.billing.models import Payment

from django.views.generic import TemplateView

from econnect.admin import ProductAdmin, PackageAdmin, AddOnAdmin
from econnect.models import Order, CustomerRequest, Product, Package, AddOn


class Admin(TemplateView):
    template_name = 'econnect/admin/admin_home.html'


class OrderList(HybridListView):
    template_name = 'econnect/admin/order_list.html'
    html_results_template_name = 'econnect/admin/snippets/order_list_result.html'
    model = Order
    queryset = Order.objects.using(UMBRELLA).all()
    search_field = 'member'
    context_object_name = 'order'


class CustomerRequestList(HybridListView):
    template_name = 'econnect/admin/request_list.html'
    html_results_template_name = 'econnect/admin/snippets/request_list_result.html'
    model = CustomerRequest
    queryset = CustomerRequest.objects.using(UMBRELLA).all()
    search_field = 'member'
    context_object_name = 'customerRequest'


class Home(TemplateView):
    template_name = 'econnect/homepage.html'


class ProductList(HybridListView):
    model = Product
    search_field = 'name'


class ChangeProduct(ChangeObjectBase):
    model = Product
    model_admin = ProductAdmin


class PackageList(HybridListView):
    model = Package
    list_filter = ('product',)
    search_field = 'name'


class ChangePackage(ChangeObjectBase):
    model = Package
    model_admin = PackageAdmin


class AddOnList(HybridListView):
    model = AddOn
    list_filter = ('product',)
    search_field = 'name'


class ChangeAddOn(ChangeObjectBase):
    model = AddOn
    model_admin = AddOnAdmin


class PricingNumerilink(TemplateView):
    template_name = 'econnect/pricing_numerilink.html'

    def get_context_data(self, **kwargs):
        context = super(PricingNumerilink, self).get_context_data(**kwargs)
        product = Product.objects.get(name='NumeriLink')
        package_list = Package.objects.filter(product=product)
        addon_list = AddOn.objects.filter(product=product)
        context['product'] = product
        context['package_list'] = package_list
        context['add-on_list'] = addon_list
        context['defaultEquipment_cost'] = AddOn.objects.get(type='Installation').cost + AddOn.objects.get(name='Decodeur', is_cyclic=False).cost
        return context
