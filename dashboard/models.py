from django.db import models
from decimal import Decimal
from django.contrib.auth.models import User
from django.db.models import Sum
from datetime import datetime, timedelta, date
import calendar



class Account(models.Model):
    acc_user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True)
    acc_name = models.CharField(max_length=50)
    acc_date_open = models.DateField()
    acc_open_balance = models.DecimalField(max_digits=7, decimal_places=2)
    acc_type = models.CharField(max_length=50)
    acc_curr_balance = models.DecimalField(max_digits=7, decimal_places=2, blank=True)

    def __str__(self):
        return self.acc_name

    def print_date(self):
        return self.acc_date_open.__format__('%m/%d/%Y')


class Category(models.Model):
    cat_user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True)
    cat_name = models.CharField(max_length=50)
    # cat_balance = models.DecimalField(max_digits=7, decimal_places=2, blank=True)

    def __str__(self):
        return self.cat_name



# If a category gets deleted, don't delete its expenses. Change the category type to 'deleted'
def get_sentinel_category():
    return Category.objects.filter(cat_name='DELETED')[0]

class Transaction(models.Model):
    tran_user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True)
    tran_date = models.DateField()
    tran_payee = models.CharField(max_length=50)
    tran_account = models.ForeignKey(Account, on_delete=models.CASCADE)
    tran_category = models.ForeignKey(Category, on_delete=models.SET(get_sentinel_category))
    tran_memo = models.CharField(max_length=50, blank=True)
    tran_outflow = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0'), blank=True)
    tran_inflow = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0'), blank=True)

    def __str__(self):
        return self.tran_payee

    def print_date(self):
        return self.tran_date.__format__('%m/%d/%Y')





class Budget(models.Model):
    bud_user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True)
    bud_date = models.DateField()
    bud_category = models.ForeignKey(Category, on_delete=models.CASCADE)
    bud_budgeted = models.DecimalField(max_digits=7, decimal_places=2)
    bud_outflows = models.DecimalField(max_digits=7, decimal_places=2, blank=True, default=Decimal('0'))
    bud_balance = models.DecimalField(max_digits=7, decimal_places=2, blank=True, default=Decimal('0'))

    def __str__(self):
        return self.bud_date.__format__('%m/%d/%Y') + '-' +  self.bud_category.cat_name

    def print_transactions_table_body(self):
        result = ''
        from_date = self.bud_date
        days = calendar.monthrange(int(from_date.year), int(from_date.month))[1]
        to_date = datetime.strptime(str(from_date.year) + '-' + str(from_date.month).zfill(2) + '-' + str(days), '%Y-%m-%d')
        relevant_transactions = Transaction.objects.filter(tran_user=self.bud_user).filter(tran_date__range=[from_date, to_date]).filter(tran_category=self.bud_category).order_by('-tran_date')

        for t in relevant_transactions:
            row = '<tr>'
            row += '<td>' + t.tran_date.__format__('%m/%d/%Y') + '</td>'
            row += '<td>' + t.tran_account.acc_name + '</td>'
            row += '<td>' + t.tran_payee + '</td>'
            row += '<td style="text-align: right;">' + str(t.tran_outflow) + '</td>'
            row += '</tr>'
            result += row

        return result


