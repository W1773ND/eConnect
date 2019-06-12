__author__ = 'W1773ND (wilfriedwillend@gmail.com)'

from django.core.serializers import json
from django.core.urlresolvers import reverse
from django.forms import ModelForm
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import render
from django.template.defaultfilters import slugify
from django.utils.http import urlquote
from django_mongodb_engine.contrib import _compiler_for_queryset

from ikwen.accesscontrol.backends import UMBRELLA
from ikwen.accesscontrol.models import Member
from ikwen.core.views import HybridListView, ChangeObjectBase
from ikwen.core.utils import get_model_admin_instance
from ikwen.billing.models import Payment

from django.views.generic import TemplateView

from econnect.admin import ProductAdmin, PackageAdmin, EquipmentAdmin, ExtraAdmin
from econnect.forms import OrderForm
from econnect.models import Order, CustomerRequest, Product, Package, Equipment, EquipmentOrderEntry, Extra, RENTAL, \
    NUMERI, HOME, OFFICE, CORPORATE, OPTIONAL_TV_COST


class MapsView(TemplateView):
    template_name = 'econnect/maps.html'


class PostView(TemplateView):
    model = None

    def post(self, request, *args, **kwargs):
        form = OrderForm(request.POST)
        equipment_order_entry_list = []
        extra_list = []
        if form.is_valid():
            product_id = form.cleaned_data['product_id']
            customer_id = form.cleaned_data['customer_id']
            customer_lat = form.cleaned_data['customer_lat']
            customer_lng = form.cleaned_data['customer_lng']
            formatted_address = form.cleaned_data['formatted_address']
            pack_id = form.cleaned_data['pack_id']
            equipment_entry_list = request.POST['equipment'].strip(";").split(";")
            extra_id_list = request.POST.get('extra').strip(";").split(";")
            optional_tv = request.POST.get('optional_tv')
            try:
                product = Product.objects.get(pk=product_id)
            except Product.DoesNotExist:
                raise Http404
            order_cost = product.install_cost
            for equipment_entry in equipment_entry_list:
                tokens = equipment_entry.split("|")
                try:
                    equipment = Equipment.objects.get(pk=tokens[0])
                    if tokens[1] == RENTAL:
                        is_rent = True
                        cost = equipment.rent_cost
                        order_cost += cost
                    else:
                        is_rent = False
                        cost = equipment.purchase_cost
                        order_cost += cost
                    equipment_order_entry = EquipmentOrderEntry(equipment=equipment, cost=cost, is_rent=is_rent)
                    equipment_order_entry_list.append(equipment_order_entry)
                except Equipment.DoesNotExist:
                    raise Http404
            if extra_id_list != [u'']:
                for extra_id in extra_id_list:
                    try:
                        extra = Extra.objects.get(pk=extra_id)
                        extra_list.append(extra)
                        order_cost += extra.cost
                    except Extra.DoesNotExist:
                        raise Http404
            if optional_tv and optional_tv >= 2:
                optional_tv = int(optional_tv)
                optional_tv_cost = (optional_tv - 1) * OPTIONAL_TV_COST
                order_cost += optional_tv_cost
            try:
                member = Member.objects.get(pk=customer_id)
            except Member.DoesNotExist:
                raise Http404
            try:
                package = Package.objects.get(pk=pack_id)
                order_cost += package.cost
            except Package.DoesNotExist:
                raise Http404
            order = Order(member=member, package=package, extra_list=extra_list, optional_tv=optional_tv,
                          equipment_order_entry_list=equipment_order_entry_list, location_lat=customer_lat,
                          location_lng=customer_lng, formatted_address=formatted_address, cost=order_cost)
            order.save()
            return HttpResponseRedirect(reverse('econnect:home'))
        else:
            return render(request, self.template_name, {'form': form})


class Admin(TemplateView):
    template_name = 'econnect/admin/admin_home.html'


class OrderList(HybridListView):
    template_name = 'econnect/admin/order_list.html'
    html_results_template_name = 'econnect/admin/snippets/order_list_results.html'
    model = Order
    queryset = Order.objects.all()
    search_field = 'member'
    list_filter = ('created_on', 'status')
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

    def get_context_data(self, **kwargs):
        context = super(Home, self).get_context_data(**kwargs)
        product_list = []
        for product in Product.objects.all():
            product.url = reverse('econnect:' + product.slug)
            product_list.append(product)
        context['product_list'] = product_list
        return context


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


class EquipmentList(HybridListView):
    model = Equipment
    list_filter = ('product',)
    search_field = 'name'


class ChangeEquipment(ChangeObjectBase):
    model = Equipment
    model_admin = EquipmentAdmin


class ExtraList(HybridListView):
    model = Extra
    list_filter = ('product',)
    search_field = 'name'


class ChangeExtra(ChangeObjectBase):
    model = Extra
    model_admin = ExtraAdmin


class PricingNumerilink(PostView):
    template_name = 'econnect/pricing_numerilink.html'

    def get_context_data(self, **kwargs):
        context = super(PricingNumerilink, self).get_context_data(**kwargs)
        try:
            product = Product.objects.get(name=NUMERI)
        except Product.DoesNotExist:
            raise Http404
        equipment_purchase_cost = 0
        for equipment in product.equipment_set.all():
            equipment_purchase_cost += equipment.purchase_cost
            equipment.slug = slugify(equipment.name)
            equipment.save()
        for extra in product.extra_set.all():
            extra.slug = slugify(extra.name)
            extra.save()
        context['equipment_purchase_cost'] = equipment_purchase_cost
        context['default_equipment_cost'] = product.install_cost + equipment_purchase_cost
        context['product'] = product
        return context


class PricingHomelink(PostView):
    template_name = 'econnect/pricing_homelink.html'

    def get_context_data(self, **kwargs):
        context = super(PricingHomelink, self).get_context_data(**kwargs)
        try:
            product = Product.objects.get(name=HOME)
        except Product.DoesNotExist:
            raise Http404
        equipment_purchase_cost = 0
        for equipment in product.equipment_set.all():
            equipment_purchase_cost += equipment.purchase_cost
            equipment.slug = slugify(equipment.name)
            equipment.save()
        for extra in product.extra_set.all():
            extra.slug = slugify(extra.name)
            extra.save()
        context['equipment_purchase_cost'] = equipment_purchase_cost
        context['default_equipment_cost'] = product.install_cost + equipment_purchase_cost
        context['product'] = product
        return context


class PricingOfficelink(PostView):
    template_name = 'econnect/pricing_officelink.html'

    def get_context_data(self, **kwargs):
        context = super(PricingOfficelink, self).get_context_data(**kwargs)
        try:
            product = Product.objects.get(name=OFFICE)
        except Product.DoesNotExist:
            raise Http404
        equipment_list = Equipment.objects.filter(product=product)
        equipment_purchase_cost = 0
        for equipment in equipment_list:
            equipment_purchase_cost += equipment.purchase_cost
            equipment.slug = slugify(equipment.name)
            equipment.save()
        for extra in product.extra_set.all():
            extra.slug = slugify(extra.name)
            extra.save()
        context['equipment_purchase_cost'] = equipment_purchase_cost
        context['default_equipment_cost'] = product.install_cost + equipment_purchase_cost
        context['equipment_list'] = equipment_list
        context['product'] = product
        return context


class PricingCorporatelink(PostView):
    template_name = 'econnect/pricing_corporatelink.html'

    def get_context_data(self, **kwargs):
        context = super(PricingCorporatelink, self).get_context_data(**kwargs)
        try:
            product = Product.objects.get(name=CORPORATE)
        except Product.DoesNotExist:
            raise Http404
        equipment_list = Equipment.objects.filter(product=product)
        equipment_purchase_cost = 0
        for equipment in equipment_list:
            equipment_purchase_cost += equipment.purchase_cost
            equipment.slug = slugify(equipment.name)
            equipment.save()
        for extra in product.extra_set.all():
            extra.slug = slugify(extra.name)
            extra.save()
        context['equipment_purchase_cost'] = equipment_purchase_cost
        context['default_equipment_cost'] = product.install_cost + equipment_purchase_cost
        context['equipment_list'] = equipment_list
        context['product'] = product
        return context
