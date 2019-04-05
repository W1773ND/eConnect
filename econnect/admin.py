from django.contrib import admin


class ProductAdmin(admin.ModelAdmin):
    fields = ('name', 'summary', 'description', 'installation_cost', )


class PackageAdmin(admin.ModelAdmin):
    fields = ('product', 'name', 'description', 'cost',)


class EquipmentAdmin(admin.ModelAdmin):
    fields = ('product', 'name', 'purchase_cost', 'rent_cost', 'is_purchased',)


class ExtraAdmin(admin.ModelAdmin):
    fields = ('product', 'name', 'cost',)

