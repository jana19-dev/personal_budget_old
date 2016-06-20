from django.contrib.auth.models import User
from django import forms
from .models import Transaction, Category, Account, Budget
from decimal import Decimal
from .fields import ListTextWidget
from datetime import date


# Login Form
class UserLoginForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['username', 'password']



# New Transaction Form
class TransactionForm(forms.ModelForm):
    tran_date = forms.DateField(initial=date.today().__format__('%m/%d/%Y'), widget=forms.TextInput(attrs={'class':"form-control pull-right", 'id':"datepicker"}))

    ALL_ACCOUNTS = Account.objects.all().order_by('acc_name')
    tran_account = forms.ModelChoiceField(queryset=ALL_ACCOUNTS, widget=forms.Select(attrs={'class':"form-control", 'style':"width: 100%;"}))

    ALL_CATEGORIES = Category.objects.all().exclude(cat_name='DELETED').order_by('cat_name')
    tran_category = forms.ModelChoiceField(queryset=ALL_CATEGORIES, widget=forms.Select(attrs={'class':"form-control", 'style':"width: 100%;"}))

    tran_payee = forms.CharField()

    tran_memo = forms.CharField(required=False,
        widget=forms.TextInput(attrs={'class': "form-control", 'style': "width: 100%;"}))

    tran_outflow = forms.DecimalField(max_digits=7, decimal_places=2, min_value=Decimal('0.00'), widget=forms.TextInput(
        attrs={'class': "form-control", 'type':"number", 'step':"0.01", 'min':"0", 'value':"0.00"}))

    tran_inflow = forms.DecimalField(max_digits=7, decimal_places=2, min_value=Decimal('0.00'), widget=forms.TextInput(
        attrs={'class': "form-control", 'type':"number", 'step':"0.01", 'min':"0", 'value':"0.00"}))

    class Meta:
        model = Transaction
        fields = ['tran_account', 'tran_date', 'tran_category', 'tran_payee', 'tran_memo', 'tran_outflow', 'tran_inflow']

    def __init__(self, *args, **kwargs):
        _payee_list = kwargs.pop('data_list', None)
        self.user = kwargs.pop('user', None)
        super(TransactionForm, self).__init__(*args, **kwargs)

        ALL_ACCOUNTS = Account.objects.filter(acc_user=self.user).order_by('acc_name')
        self.fields['tran_account'] = forms.ModelChoiceField(queryset=ALL_ACCOUNTS, widget=forms.Select(attrs={'class':"form-control", 'style':"width: 100%;"}))

        ALL_CATEGORIES = Category.objects.filter(cat_user=self.user).exclude(cat_name='DELETED').order_by('cat_name')
        self.fields['tran_category'] = forms.ModelChoiceField(queryset=ALL_CATEGORIES, widget=forms.Select(attrs={'class': "form-control", 'style': "width: 100%;"}))

        self.fields['tran_payee'].widget = ListTextWidget(data_list=_payee_list, name='country-list',attrs={'class':"form-control", 'style':"width: 100%;"} )



# New Transaction Form FOR ACCOUNT VIEW
class TransactionAccountForm(forms.ModelForm):
    tran_date = forms.DateField(initial=date.today().__format__('%m/%d/%Y'), widget=forms.TextInput(attrs={'class':"form-control pull-right", 'id':"datepicker"}))

    ALL_CATEGORIES = Category.objects.all().exclude(cat_name='DELETED').order_by('cat_name')
    tran_category = forms.ModelChoiceField(queryset=ALL_CATEGORIES, widget=forms.Select(attrs={'class':"form-control", 'style':"width: 100%;"}))

    tran_payee = forms.CharField()

    tran_memo = forms.CharField(required=False,
        widget=forms.TextInput(attrs={'class': "form-control", 'style': "width: 100%;"}))

    tran_outflow = forms.DecimalField(max_digits=7, decimal_places=2, min_value=Decimal('0.00'), widget=forms.TextInput(
        attrs={'class': "form-control", 'type':"number", 'step':"0.01", 'min':"0", 'value':"0.00"}))

    tran_inflow = forms.DecimalField(max_digits=7, decimal_places=2, min_value=Decimal('0.00'), widget=forms.TextInput(
        attrs={'class': "form-control", 'type':"number", 'step':"0.01", 'min':"0", 'value':"0.00"}))

    class Meta:
        model = Transaction
        fields = ['tran_date', 'tran_category', 'tran_payee', 'tran_memo', 'tran_outflow', 'tran_inflow']

    def __init__(self, *args, **kwargs):
        _payee_list = kwargs.pop('data_list', None)
        self.user = kwargs.pop('user', None)
        super(TransactionAccountForm, self).__init__(*args, **kwargs)

        ALL_CATEGORIES = Category.objects.filter(cat_user=self.user).exclude(cat_name='DELETED').order_by('cat_name')
        self.fields['tran_category'] = forms.ModelChoiceField(queryset=ALL_CATEGORIES, widget=forms.Select(attrs={'class': "form-control", 'style': "width: 100%;"}))

        self.fields['tran_payee'].widget = ListTextWidget(data_list=_payee_list, name='country-list',attrs={'class':"form-control", 'style':"width: 100%;"} )





class AccountForm(forms.ModelForm):

    acc_name = forms.CharField(widget=forms.TextInput(attrs={'class': "form-control"}))

    acc_date_open = forms.DateField(initial=date.today().__format__('%m/%d/%Y'), widget=forms.TextInput(attrs={'class':"form-control pull-right", 'id':"datepicker"}))

    acc_open_balance = forms.DecimalField(max_digits=7, decimal_places=2, widget=forms.TextInput(
        attrs={'class': "form-control", 'type':"number", 'step':"0.01"}))

    CHOICES = (('Checking', 'Checking'), ('Savings', 'Savings'), ('Credit Card', 'Credit Card'), ('Cash', 'Cash'), ('Line of Credit', 'Line of Credit'), ('Loans', 'Loans'))
    acc_type = forms.ChoiceField(choices=CHOICES, required=True, widget=forms.Select(
        attrs={'class': "form-control ", 'style': "width: 100%;"}))

    class Meta:
        model = Account
        fields = ['acc_name', 'acc_date_open', 'acc_open_balance', 'acc_type']




class CategoryForm(forms.ModelForm):

    cat_name = forms.CharField(widget=forms.TextInput(attrs={'class': "form-control"}))

    class Meta:
        model = Category
        fields = ['cat_name']