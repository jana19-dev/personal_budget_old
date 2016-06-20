from django.contrib import admin
from .models import Transaction, Category, Account, Budget

admin.site.register(Transaction)
admin.site.register(Category)
admin.site.register(Account)
admin.site.register(Budget)
