# -*- coding: utf-8 -*-

__author__ = 'W1773ND (wilfriedwillend@gmail.com)'

from django import forms


class OrderForm(forms.Form):
    product_id = forms.CharField(max_length=35)
    customer_id = forms.CharField(max_length=35)
    pack_id = forms.CharField(max_length=35)
    customer_lat = forms.FloatField()
    customer_lng = forms.FloatField()
    formatted_address = forms.CharField(max_length=255)
    equipment = forms.CharField(max_length=255)
    extra = forms.CharField(max_length=255, required=False)
    optional_tv = forms.IntegerField(required=False)


class YUPCallbackForm(forms.Form):
    invoice_id = forms.CharField(max_length=60)
    amount = forms.IntegerField()
    transaction_id = forms.CharField(max_length=60)
