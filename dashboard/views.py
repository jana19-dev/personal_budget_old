from django.shortcuts import render, redirect, HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.generic import View
from .forms import UserLoginForm, TransactionForm, AccountForm, CategoryForm, TransactionAccountForm
from .models import Transaction, Category, Account, Budget
from decimal import Decimal
import json
from datetime import datetime, timedelta, date
import calendar
from django.db.models import Sum
import random

def custom_404(request):
    return render(request, 'dashboard/404.html', {}, status=404)

def custom_400(request):
    return render(request, 'dashboard/400.html', {}, status=400)

def custom_500(request):
    return render(request, 'dashboard/500.html', {}, status=500)


@login_required()
def index(request, acc_name=None, date_range=None, bud_range=None, cat_name='All'):
    # Check if we are in November and add additional budget entries for next year
    if date.today().month == 11:
        ALL_CATEGORIES = Category.objects.filter(cat_user=request.user).exclude(cat_name='DELETED').exclude(
            cat_name='TRANSFER').order_by('cat_name')
        add_budget_entry(ALL_CATEGORIES, 1, 'ALL')
    # ---------------------------------------------------------------------------

    context = {}

    # Suggest list of already added payees in the budget in the blank form to add new transaction
    ALL_PAYEES = Transaction.objects.filter(tran_user=request.user).values('tran_payee').order_by(
        'tran_payee').distinct()
    ALL_ACCOUNTS = Account.objects.filter(acc_user=request.user).values('acc_name').exclude(
        acc_name='DELETED').order_by('acc_name').distinct()
    ALL_PAYEE_LIST = []
    for account in ALL_ACCOUNTS:
        ALL_PAYEE_LIST.append(account['acc_name'])
    for payee in ALL_PAYEES:
        ALL_PAYEE_LIST.append(payee['tran_payee'])
    ALL_PAYEE_LIST = tuple(set(ALL_PAYEE_LIST))
    form = TransactionForm(data_list=ALL_PAYEE_LIST, user=request.user)
    context['form'] = form
    # ---------------------------------------------------------------------------

    cat_obj, from_date, to_date = None, None, None
    # Check if viewing a specific account or all accounts and filter transactions
    if acc_name:
        try:  # account view filter option
            date_range = acc_name.split('/', 1)[1]
            acc_name = acc_name.split('/')[0]
        except Exception:
            pass

        context['acc_view'] = 'True'
        ALL_TRANSACTIONS = Transaction.objects.filter(tran_user=request.user).filter(
            tran_account__acc_name=acc_name).order_by('-tran_date')
        context['acc_name'] = acc_name
        form = TransactionAccountForm(data_list=ALL_PAYEE_LIST, user=request.user)
        context['form'] = form
    else:
        context['all_view'] = 'True'
        ALL_TRANSACTIONS = Transaction.objects.filter(tran_user=request.user).order_by('-tran_date')

    if bud_range:
        # budget view filter by category
        from_date = datetime.strptime(bud_range.split('-')[0], '%m/%d/%Y')
        days = calendar.monthrange(int(from_date.year), int(from_date.month))[1]
        to_date = datetime.strptime(str(from_date.year) + '-' + str(from_date.month).zfill(2) + '-' + str(days), '%Y-%m-%d')
        cat_obj = Category.objects.filter(cat_user=request.user).get(cat_name=bud_range.split('-')[1])
        date_range = True
        context['category'] = cat_obj.cat_name

    if date_range:
        if from_date:
            tran_from_date = from_date
            tran_to_date = to_date
        else:
            tran_from_date = datetime.strptime(date_range.split(':')[0],'%m/%d/%Y')
            tran_to_date = datetime.strptime(date_range.split(':')[1], '%m/%d/%Y')

        ALL_TRANSACTIONS = ALL_TRANSACTIONS.filter(tran_date__range=[tran_from_date, tran_to_date])
        context['tran_range'] = tran_from_date.__format__('%B %d, %Y') + ' - ' + tran_to_date.__format__('%B %d, %Y')
        context['start_date'] = tran_from_date.__format__('%m/%d/%Y')
        context['end_date'] = tran_to_date.__format__('%m/%d/%Y')
        context['tran_range_for_budget'] = context['start_date']+':'+context['end_date']
    else:
        current_month_from, current_month_to = _get_curr_month_range(None)
        ALL_TRANSACTIONS = ALL_TRANSACTIONS.filter(tran_date__range=[current_month_from, current_month_to])
        context['tran_range'] = current_month_from.__format__('%B %d, %Y') + ' - ' + current_month_to.__format__('%B %d, %Y')
        context['start_date'] = current_month_from.__format__('%m/%d/%Y')
        context['end_date'] = current_month_to.__format__('%m/%d/%Y')
        context['tran_range_for_budget'] = context['start_date'] + ':' + context['end_date']
    if cat_obj:
        ALL_TRANSACTIONS = ALL_TRANSACTIONS.filter(tran_category=cat_obj)
    if cat_name != 'All':
        ALL_TRANSACTIONS_CAT = ALL_TRANSACTIONS.filter(tran_category__cat_name=cat_name)
        context['ALL_TRANSACTIONS'] = ALL_TRANSACTIONS_CAT
    else:
        context['ALL_TRANSACTIONS'] = ALL_TRANSACTIONS
    # ---------------------------------------------------------------------------


    # Make drop down lists for Accounts and Categories in the table of list of transactions when editing
    ACCOUNTS_DROP_DOWN = Account.objects.filter(acc_user=request.user).exclude(acc_name='DELETED').values_list(
        'acc_name')
    accounts_dropdown_dict = {}
    for i in ACCOUNTS_DROP_DOWN:
        accounts_dropdown_dict[i[0]] = i[0]
    accounts_dropdown_dict = json.dumps(accounts_dropdown_dict)

    CATEGORIES_DROP_DOWN = Category.objects.filter(cat_user=request.user).exclude(cat_name='DELETED').values_list(
        'cat_name').order_by('cat_name')
    categories_dropdown_dict = {}
    for i in CATEGORIES_DROP_DOWN:
        categories_dropdown_dict[i[0]] = i[0]
    categories_dropdown_dict = json.dumps(categories_dropdown_dict)
    context['accounts_dropdown_dict'] = accounts_dropdown_dict
    context['categories_dropdown_dict'] = categories_dropdown_dict
    # ---------------------------------------------------------------------------

    # Get updated account balances of all accounts to display in sidebar
    NET_WORTH = _update_accounts(request)
    CASH, CHECKING, SAVINGS, CREDIT_CARD, LINE_OF_CREDIT, LOANS = _get_updated_account_balances(request)
    context['CASH'] = CASH
    context['CHECKING'] = CHECKING
    context['SAVINGS'] = SAVINGS
    context['CREDIT_CARD'] = CREDIT_CARD
    context['LINE_OF_CREDIT'] = LINE_OF_CREDIT
    context['LOANS'] = LOANS
    context['NET_WORTH'] = NET_WORTH
    # ---------------------------------------------------------------------------

    # Set the correct account name to be active in the sidebar list
    active_dict = {}
    for i in ACCOUNTS_DROP_DOWN:
        active_dict[i[0]] = ''
        if acc_name == i[0]:
            active_dict[i[0]] = 'active'
    context['active_dict'] = active_dict
    # ---------------------------------------------------------------------------

    # Get list of all categories to filter option
    context['ALL_CATEGORIES'] = Category.objects.filter(cat_user=request.user).exclude(cat_name='DELETED').order_by('cat_name')
    if bud_range:
        context['cat_name'] = context['category']
    else:
        context['cat_name'] = cat_name
    # ---------------------------------------------------------------------------

    context['TOTAL_OUTFLOWS'] = context['ALL_TRANSACTIONS'].aggregate(tran_outflow=Sum('tran_outflow'))[
        'tran_outflow']
    context['TOTAL_INFLOWS'] = context['ALL_TRANSACTIONS'].aggregate(tran_inflow=Sum('tran_inflow'))[
        'tran_inflow']
    context['COUNT'] = context['ALL_TRANSACTIONS'].count()
    return render(request, 'dashboard/transactions.html', context)


def _update_accounts(request):
    ALL_TRANSACTIONS = Transaction.objects.filter(tran_user=request.user).order_by('-tran_date')
    ALL_ACCOUNTS = Account.objects.filter(acc_user=request.user).exclude(acc_name='DELETED')
    NET_WORTH = 0
    for account in ALL_ACCOUNTS:
        TOTAL_OUTFLOWS = ALL_TRANSACTIONS.filter(tran_account=account).aggregate(tran_outflow=Sum('tran_outflow'))[
            'tran_outflow']
        TOTAL_INFLOWS = ALL_TRANSACTIONS.filter(tran_account=account).aggregate(tran_inflow=Sum('tran_inflow'))[
            'tran_inflow']
        if TOTAL_OUTFLOWS is None:
            TOTAL_OUTFLOWS = 0
        if TOTAL_INFLOWS is None:
            TOTAL_INFLOWS = 0
        account.acc_curr_balance = TOTAL_INFLOWS - TOTAL_OUTFLOWS + account.acc_open_balance
        NET_WORTH += account.acc_curr_balance
        account.save()
    return NET_WORTH


def _get_updated_account_balances(request):
    # return tuple (CASH, CHECKING, SAVINGS, CREDIT_CARD, LINE_OF_CREDIT, LOANS)
    ALL_ACCOUNTS = Account.objects.filter(acc_user=request.user).exclude(acc_name='DELETED')

    CASH = ALL_ACCOUNTS.filter(acc_type='Cash')
    CHECKING = ALL_ACCOUNTS.filter(acc_type='Checking')
    SAVINGS = ALL_ACCOUNTS.filter(acc_type='Savings')
    CREDIT_CARD = ALL_ACCOUNTS.filter(acc_type='Credit Card')
    LINE_OF_CREDIT = ALL_ACCOUNTS.filter(acc_type='Line of Credit')
    LOANS = ALL_ACCOUNTS.filter(acc_type='Loans')

    return (CASH, CHECKING, SAVINGS, CREDIT_CARD, LINE_OF_CREDIT, LOANS)


@login_required()
def add_transaction(request, acc_name=None):
    context = {}

    # Get updated account balances of all accounts to display in sidebar
    NET_WORTH = _update_accounts(request)
    CASH, CHECKING, SAVINGS, CREDIT_CARD, LINE_OF_CREDIT, LOANS = _get_updated_account_balances(request)
    context['CASH'] = CASH
    context['CHECKING'] = CHECKING
    context['SAVINGS'] = SAVINGS
    context['CREDIT_CARD'] = CREDIT_CARD
    context['LINE_OF_CREDIT'] = LINE_OF_CREDIT
    context['LOANS'] = LOANS
    context['NET_WORTH'] = NET_WORTH
    # ---------------------------------------------------------------------------

    # Used when filtering results on transactions page
    current_month_from, current_month_to = _get_curr_month_range(None)
    context['tran_range_for_budget'] = current_month_from.__format__(
        '%m/%d/%Y') + ':' + current_month_to.__format__('%m/%d/%Y')
    context['cat_name'] = 'All'
    # ---------------------------------------------------------------------------

    ALL_PAYEES = Transaction.objects.filter(tran_user=request.user).values('tran_payee').order_by(
        'tran_payee').distinct()
    ALL_ACCOUNTS = Account.objects.filter(acc_user=request.user).values('acc_name').exclude(
        acc_name='DELETED').order_by('acc_name').distinct()
    ALL_ACCOUNTS_LIST = []
    ALL_PAYEE_LIST = []
    for account in ALL_ACCOUNTS:
        ALL_PAYEE_LIST.append(account['acc_name'])
        ALL_ACCOUNTS_LIST.append(account['acc_name'])
    for payee in ALL_PAYEES:
        ALL_PAYEE_LIST.append(payee['tran_payee'])
    ALL_PAYEE_LIST = tuple(set(ALL_PAYEE_LIST))

    ALL_TRANSACTIONS = Transaction.objects.filter(tran_user=request.user).order_by('-tran_date')

    context['ALL_TRANSACTIONS'] = ALL_TRANSACTIONS
    if acc_name:
        context['acc_name'] = acc_name
    else:
        context['all_view'] = 'True'

    if request.method == 'POST':
        if acc_name:
            form = TransactionAccountForm(request.POST, data_list=ALL_PAYEE_LIST, user=request.user)
        else:
            form = TransactionForm(request.POST, data_list=ALL_PAYEE_LIST, user=request.user)
        context['form'] = form
        if form.is_valid():
            if acc_name:
                tran_account = Account.objects.get(acc_name=acc_name)
            else:
                tran_account = form.cleaned_data['tran_account']
            tran_payee = form.cleaned_data['tran_payee'].upper()
            tran_category = form.cleaned_data['tran_category']
            tran_memo = form.cleaned_data['tran_memo'].upper()
            tran_outflow = form.cleaned_data['tran_outflow']
            tran_inflow = form.cleaned_data['tran_inflow']

            result = check_transaction_errors(request, tran_account, tran_payee, tran_category, tran_outflow,
                                              tran_inflow)
            if result is not None:
                # Form has errors
                form.add_error(None, result)
                return render(request, 'dashboard/transactions.html', context)
            else:
                # Form has no errors
                tran_obj = Transaction()
                tran_obj.tran_user = request.user
                tran_obj.tran_date = form.cleaned_data['tran_date']
                tran_obj.tran_account = tran_account
                tran_obj.tran_payee = tran_payee
                tran_obj.tran_category = tran_category
                tran_obj.tran_memo = tran_memo
                tran_obj.tran_outflow = tran_outflow
                tran_obj.tran_inflow = tran_inflow
                tran_obj.save()

                # Check if the transaction was a transfer and add another transaction for the other account
                if tran_category.cat_name == 'TRANSFER':
                    tran_obj = Transaction()
                    tran_obj.tran_user = request.user
                    tran_obj.tran_date = form.cleaned_data['tran_date']
                    tran_obj.tran_account = Account.objects.get(acc_name=tran_payee)
                    tran_obj.tran_payee = tran_account.acc_name
                    tran_obj.tran_category = tran_category
                    tran_obj.tran_memo = tran_memo
                    if tran_outflow > 0:
                        tran_obj.tran_outflow = 0
                        tran_obj.tran_inflow = tran_outflow
                    else:
                        tran_obj.tran_outflow = tran_inflow
                        tran_obj.tran_inflow = 0
                    tran_obj.save()
        else:  # Form has in-built validation errors
            return render(request, 'dashboard/transactions.html', context)

    if acc_name:
        return redirect('dashboard:filter_results', context['tran_range_for_budget'], acc_name, 'All')
    else:
        return redirect('dashboard:index')


@login_required()
def edit_transaction(request):
    if request.method == 'POST':
        input_dict = request.POST.dict()
        print(input_dict)
        if input_dict['action'] == 'edit':
            try:
                tran_obj = Transaction.objects.get(pk=input_dict['id'])

                tran_account = tran_obj.tran_account
                tran_payee = tran_obj.tran_payee
                tran_category = tran_obj.tran_category
                tran_outflow = tran_obj.tran_outflow
                tran_inflow = tran_obj.tran_inflow

                if tran_category.cat_name == 'TRANSFER':
                    input_dict = _handle_edit_transfer(request, tran_obj)
                    return HttpResponse(json.dumps(input_dict), content_type="application/json")

                else:
                    if 'tran_account' in input_dict:
                        if tran_account.acc_name != input_dict['tran_account']:
                            tran_account = Account.objects.filter(acc_user=request.user).get(
                                acc_name=input_dict['tran_account'])
                            result = check_transaction_errors(request, tran_account, tran_payee, tran_category,
                                                              tran_outflow, tran_inflow)
                            if result is not None:
                                input_dict['error'] = result
                            else:
                                tran_obj.tran_account = tran_account
                                tran_obj.save()
                        else:
                            input_dict['nothing'] = 'nothing'

                    elif 'tran_date' in input_dict:
                        try:
                            if tran_obj.tran_date.__format__('%m/%d/%Y') != datetime.strptime(input_dict['tran_date'],'%m/%d/%Y').__format__('%m/%d/%Y'):
                                tran_obj.tran_date = datetime.strptime(input_dict['tran_date'], '%m/%d/%Y')
                                tran_obj.save()
                            else:
                                input_dict['nothing'] = 'nothing'
                        except Exception:
                            input_dict['error'] = "Invalid Date Format. Use MM/DD/YYYY."

                    elif 'tran_payee' in input_dict:
                        if tran_payee != input_dict['tran_payee'].upper():
                            tran_payee = input_dict['tran_payee'].upper()
                            result = check_transaction_errors(request, tran_account, tran_payee, tran_category,
                                                              tran_outflow, tran_inflow)
                            if result is not None:
                                input_dict['error'] = result
                            else:
                                tran_obj.tran_payee = tran_payee
                                tran_obj.save()
                        else:
                            input_dict['nothing'] = 'nothing'

                    elif 'tran_category' in input_dict:

                        if tran_category.cat_name != input_dict['tran_category']:

                            tran_category = Category.objects.filter(cat_user=request.user).get(cat_name=input_dict['tran_category'])
                            result = check_transaction_errors(request, tran_account, tran_payee, tran_category,
                                                              tran_outflow, tran_inflow)
                            if result is not None:
                                input_dict['error'] = result
                            else:

                                tran_obj.tran_category = tran_category
                                tran_obj.save()
                        else:
                            input_dict['nothing'] = 'nothing'

                    elif 'tran_memo' in input_dict:
                        if tran_obj.tran_memo != input_dict['tran_memo'].upper():
                            tran_obj.tran_memo = input_dict['tran_memo'].upper()
                            tran_obj.save()
                        else:
                            input_dict['nothing'] = 'nothing'

                    elif 'tran_outflow' in input_dict:
                        try:
                            if tran_outflow != float(input_dict['tran_outflow'].replace(',','')):
                                tran_outflow = float(input_dict['tran_outflow'].replace(',',''))
                                result = check_transaction_errors(request, tran_account, tran_payee, tran_category,
                                                                  tran_outflow, tran_inflow)
                                if result is not None:
                                    input_dict['error'] = result
                                else:
                                    tran_obj.tran_outflow = tran_outflow
                                    tran_obj.save()
                            else:
                                input_dict['nothing'] = 'nothing'
                        except Exception:
                            input_dict['error'] = "Invalid amount for Outflow."

                    elif 'tran_inflow' in input_dict:
                        try:
                            if tran_inflow != float(input_dict['tran_inflow'].replace(',','')):
                                tran_inflow = float(input_dict['tran_inflow'].replace(',',''))
                                result = check_transaction_errors(request, tran_account, tran_payee, tran_category,
                                                                  tran_outflow, tran_inflow)
                                if result is not None:
                                    input_dict['error'] = result
                                else:
                                    tran_obj.tran_inflow = tran_inflow
                                    tran_obj.save()
                            else:
                                input_dict['nothing'] = 'nothing'
                        except Exception:
                            input_dict['error'] = "Invalid amount for Inflow."

            except Exception:
                input_dict['nothing'] = 'nothing'

        else:  # Delete Request
            tran_obj = Transaction.objects.get(pk=input_dict['id'])
            if tran_obj.tran_category.cat_name == 'TRANSFER':
                # Delete the other connected transaction as well
                try:
                    other_tran_obj = Transaction.objects.filter(tran_date__exact=tran_obj.tran_date).filter(tran_memo__exact=tran_obj.tran_memo).filter(tran_outflow__exact=tran_obj.tran_inflow).filter(tran_inflow__exact=tran_obj.tran_outflow).filter(tran_payee=tran_obj.tran_account.acc_name)[0]
                    other_tran_obj.delete()
                    tran_obj.delete()
                except Exception:
                    input_dict['error'] = "Something went wrong."
            else:
                tran_obj.delete()
        print(input_dict)

        return HttpResponse(json.dumps(input_dict), content_type="application/json")
    else:
        return HttpResponse(json.dumps({"nothing to see": "this isn't happening"}), content_type="application/json")




def _handle_edit_transfer(request, tran_obj):
    input_dict = request.POST.dict()

    tran_account = tran_obj.tran_account
    tran_payee = tran_obj.tran_payee
    tran_category = tran_obj.tran_category
    tran_outflow = tran_obj.tran_outflow
    tran_inflow = tran_obj.tran_inflow

    other_tran_obj = \
    Transaction.objects.filter(tran_user=request.user).filter(tran_date__exact=tran_obj.tran_date).filter(tran_memo__exact=tran_obj.tran_memo).filter(
        tran_outflow__exact=tran_obj.tran_inflow).filter(tran_inflow__exact=tran_obj.tran_outflow).filter(
        tran_payee=tran_obj.tran_account.acc_name)[0]

    if 'tran_account' in input_dict:
        if tran_account.acc_name != input_dict['tran_account']:
            tran_account = Account.objects.filter(acc_user=request.user).get(
                acc_name=input_dict['tran_account'])
            result = check_transaction_errors(request, tran_account, tran_payee, tran_category,
                                              tran_outflow, tran_inflow)
            if result is not None:
                input_dict['error'] = result
            else:
                tran_obj.tran_account = tran_account
                tran_obj.save()
                other_tran_obj.tran_payee = tran_account.acc_name
                other_tran_obj.save()
        else:
            input_dict['nothing'] = 'nothing'

    elif 'tran_date' in input_dict:
        try:
            if tran_obj.tran_date.__format__('%m/%d/%Y') != datetime.strptime(input_dict['tran_date'],
                                                                              '%m/%d/%Y').__format__('%m/%d/%Y'):
                tran_obj.tran_date = datetime.strptime(input_dict['tran_date'], '%m/%d/%Y')
                tran_obj.save()
                other_tran_obj.tran_date = datetime.strptime(input_dict['tran_date'], '%m/%d/%Y')
                other_tran_obj.save()
            else:
                input_dict['nothing'] = 'nothing'
        except Exception:
            input_dict['error'] = "Invalid Date Format. Use MM/DD/YYYY."

    elif 'tran_payee' in input_dict:
        if tran_payee != input_dict['tran_payee'].upper():
            tran_payee = input_dict['tran_payee'].upper()
            result = check_transaction_errors(request, tran_account, tran_payee, tran_category,
                                              tran_outflow, tran_inflow)
            if result is not None:
                input_dict['error'] = result
            else:
                tran_obj.tran_payee = tran_payee
                tran_obj.save()
                other_tran_obj.tran_account = Account.objects.get(acc_name=tran_payee)
                other_tran_obj.save()
        else:
            input_dict['nothing'] = 'nothing'

    elif 'tran_category' in input_dict:
        input_dict['error'] = 'You cannot change the category for a TRANSFER. However, You can delete the transaction.'


    elif 'tran_memo' in input_dict:
        if tran_obj.tran_memo != input_dict['tran_memo'].upper():
            tran_obj.tran_memo = input_dict['tran_memo'].upper()
            tran_obj.save()
            other_tran_obj.tran_memo = input_dict['tran_memo'].upper()
            other_tran_obj.save()
        else:
            input_dict['nothing'] = 'nothing'

    elif 'tran_outflow' in input_dict:
        try:
            if tran_outflow != float(input_dict['tran_outflow'].replace(',','')):
                tran_outflow = float(input_dict['tran_outflow'].replace(',',''))
                result = check_transaction_errors(request, tran_account, tran_payee, tran_category,
                                                  tran_outflow, tran_inflow)
                if result is not None:
                    input_dict['error'] = result
                else:
                    tran_obj.tran_outflow = tran_outflow
                    tran_obj.save()
                    other_tran_obj.tran_inflow = tran_outflow
                    other_tran_obj.save()
            else:
                input_dict['nothing'] = 'nothing'
        except Exception:
            input_dict['error'] = "Invalid amount for Outflow."

    elif 'tran_inflow' in input_dict:
        try:
            if tran_inflow != float(input_dict['tran_inflow'].replace(',','')):
                tran_inflow = float(input_dict['tran_inflow'].replace(',',''))
                result = check_transaction_errors(request, tran_account, tran_payee, tran_category,
                                                  tran_outflow, tran_inflow)
                if result is not None:
                    input_dict['error'] = result
                else:
                    tran_obj.tran_inflow = tran_inflow
                    tran_obj.save()
                    other_tran_obj.tran_outflow = tran_inflow
                    other_tran_obj.save()
            else:
                input_dict['nothing'] = 'nothing'
        except Exception:
            input_dict['error'] = "Invalid amount for Inflow."


    return input_dict





def check_transaction_errors(request, tran_account, tran_payee, tran_category, tran_outflow, tran_inflow):
    ALL_ACCOUNTS = Account.objects.filter(acc_user=request.user).values('acc_name').exclude(
        acc_name='DELETED').order_by('acc_name').distinct()
    ALL_ACCOUNTS_LIST = [account['acc_name'] for account in ALL_ACCOUNTS]

    if tran_outflow > 0 and tran_inflow > 0:
        return "Both Inflow & Outflow cannot have values greater than 0.00 at the same time."
    if tran_outflow == 0 and tran_inflow == 0:
        if tran_category.cat_name == 'INCOME':
            return "Fill in a value for Inflow."
        else:
            return "Fill in a value for Outflow."
    if tran_payee == '':
        return "Payee name cannot be left blank."
    if tran_payee == tran_account.acc_name:
        return "Account name and Payee name cannot be the same."
    if tran_category.cat_name == 'INCOME' and tran_outflow > 0:
        return "INCOME category must have only an Inflow value."
    if tran_category.cat_name not in ['INCOME', 'TRANSFER'] and tran_inflow > 0:
        return "Only INCOME or TRANSFER category can have an Inflow value."
    if tran_category.cat_name == 'TRANSFER':
        if tran_payee not in ALL_ACCOUNTS_LIST:
            return "Payee name must match one of the Account name for a TRANSFER."
    if tran_category.cat_name != 'TRANSFER':
        if tran_payee in ALL_ACCOUNTS_LIST:
            return "Payee name cannot be an Account Name for Non-Transfer."

    return None


class UserLoginFormView(View):
    form_class = UserLoginForm
    template_name = 'dashboard/login_form.html'

    # display a blank form to login
    def get(self, request):
        form = self.form_class(None)
        return render(request, self.template_name, {'form': form})

    # process form and login the user
    def post(self, request):
        form = self.form_class(request.POST)
        username = request.POST['username']
        password = request.POST['password']
        # returns User object if credentials are correct
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                return redirect('dashboard:budget')
            else:
                form.add_error(None, "This Account is disabled")
        else:
            form.add_error(None, "Invalid USERNAME or PASSWORD")

        return render(request, self.template_name, {'form': form})


@login_required(login_url='dashboard:login')
def logout_view(request):
    logout(request)
    return redirect('dashboard:login')


@login_required(login_url='dashboard:login')
def accounts(request):
    acc_form = AccountForm()
    ALL_ACCOUNTS = Account.objects.filter(acc_user=request.user).exclude(acc_name='DELETED').order_by(
        'acc_name').order_by('acc_type', 'acc_name')

    if request.method == 'POST':
        acc_form = AccountForm(request.POST)
        result = _handle_account_add(request)
        if result:  # Form has some errors
            for custom_error in result:
                if custom_error != 'validation_error':
                    acc_form.add_error(None, custom_error)
        else:  # Account added successfully
            return redirect('dashboard:accounts')

    context = {'acc_form': acc_form, 'ALL_ACCOUNTS': ALL_ACCOUNTS}

    # Get updated account balances of all accounts to display in sidebar
    NET_WORTH = _update_accounts(request)
    CASH, CHECKING, SAVINGS, CREDIT_CARD, LINE_OF_CREDIT, LOANS = _get_updated_account_balances(request)
    context['CASH'] = CASH
    context['CHECKING'] = CHECKING
    context['SAVINGS'] = SAVINGS
    context['CREDIT_CARD'] = CREDIT_CARD
    context['LINE_OF_CREDIT'] = LINE_OF_CREDIT
    context['LOANS'] = LOANS
    context['NET_WORTH'] = NET_WORTH
    # ---------------------------------------------------------------------------

    # Used when filtering results on transactions page
    current_month_from, current_month_to = _get_curr_month_range(None)
    context['tran_range_for_budget'] = current_month_from.__format__('%m/%d/%Y')+':'+current_month_to.__format__('%m/%d/%Y')
    context['cat_name'] = 'All'
    # ---------------------------------------------------------------------------

    return render(request, 'dashboard/accounts.html', context)


def _handle_account_add(request):
    form = AccountForm(request.POST)
    errors = []
    if form.is_valid():
        acc_name = form.cleaned_data['acc_name'].upper()
        acc_type = form.cleaned_data['acc_type']
        if Account.objects.filter(acc_user=request.user).filter(acc_name=acc_name).count():
            errors.append("Account name already in use.")
        else:
            acc_obj = Account()
            acc_obj.acc_user = request.user
            acc_obj.acc_name = acc_name
            acc_obj.acc_date_open = form.cleaned_data['acc_date_open']
            acc_obj.acc_open_balance = form.cleaned_data['acc_open_balance']
            acc_obj.acc_type = acc_type
            acc_obj.acc_curr_balance = form.cleaned_data['acc_open_balance']
            acc_obj.save()
    else:  # form has some validation errors
        return ['validation_error']

    return errors


@login_required()
def edit_account(request):
    if request.method == 'POST':
        input_dict = request.POST.dict()
        print(input_dict)
        if input_dict['action'] == 'edit':
            try:
                acc_obj = Account.objects.get(pk=input_dict['id'])
                if 'acc_name' in input_dict:
                    if acc_obj.acc_name != input_dict['acc_name']:
                        if (Account.objects.filter(acc_user=request.user).filter(acc_name=input_dict['acc_name']).count()):
                            input_dict['error'] = "Account Name already in use."
                        else:
                            acc_obj.acc_name = input_dict['acc_name']
                            acc_obj.save()
                    else:
                        input_dict['nothing'] = 'nothing'
                elif 'acc_type' in input_dict:
                    if acc_obj.acc_type != input_dict['acc_type']:
                        if (input_dict['acc_type'] == "0"):
                            input_dict['error'] = "Account Type cannot be left blank."
                        else:
                            acc_obj.acc_type = input_dict['acc_type']
                            acc_obj.save()
                    else:
                        input_dict['nothing'] = 'nothing'
                elif 'acc_date_open' in input_dict:
                    try:
                        if acc_obj.acc_date_open.__format__('%m/%d/%Y') != datetime.strptime(
                                input_dict['acc_date_open'],
                                '%m/%d/%Y').__format__(
                            '%m/%d/%Y'):
                            acc_obj.acc_date_open = datetime.strptime(input_dict['acc_date_open'], '%m/%d/%Y')
                            acc_obj.save()
                        else:
                            input_dict['nothing'] = 'nothing'
                    except Exception:
                        input_dict['error'] = "Invalid Date Format. Use MM/DD/YYYY."
                elif 'acc_open_balance' in input_dict:
                    try:
                        if acc_obj.acc_open_balance != float(input_dict['acc_open_balance'].replace(',','')):
                            acc_obj.acc_open_balance = float(input_dict['acc_open_balance'].replace(',',''))
                            acc_obj.save()
                        else:
                            input_dict['nothing'] = 'nothing'
                    except Exception:
                        input_dict['error'] = "Invalid amount for Opening Balance."
            except Exception:
                input_dict['nothing'] = 'nothing'
        else:  # Delete Request
            acc_obj = Account.objects.get(pk=input_dict['id'])
            acc_obj.delete()

        return HttpResponse(json.dumps(input_dict), content_type="application/json")
    else:
        return HttpResponse(json.dumps({"nothing to see": "this isn't happening"}), content_type="application/json")


@login_required()
def addCategory(request):
    context = {}
    ALL_CATEGORIES = Category.objects.filter(cat_user=request.user).exclude(cat_name='DELETED').exclude(
        cat_name='TRANSFER').order_by('cat_name')
    context['ALL_CATEGORIES'] = ALL_CATEGORIES
    # Used when filtering results on transactions page
    current_month_from, current_month_to = _get_curr_month_range(None)
    context['tran_range_for_budget'] = current_month_from.__format__(
        '%m/%d/%Y') + ':' + current_month_to.__format__('%m/%d/%Y')
    context['cat_name'] = 'All'
    # ---------------------------------------------------------------------------

    if request.method == 'POST':
        cat_form = CategoryForm(request.POST)
        if cat_form.is_valid():
            cat_name = cat_form.cleaned_data['cat_name'].upper()
            if (Category.objects.filter(cat_user=request.user).filter(cat_name=cat_name).count()):
                cat_form.add_error(None, "Category name already in use.")
                context['cat_form'] = cat_form
                return render(request, 'dashboard/budget.html', context)
            else:  # Form has no errors
                cat_obj = Category()
                cat_obj.cat_user = request.user
                cat_obj.cat_name = cat_name
                cat_obj.save()
                add_budget_entry(cat_obj)  # add entries for 3 years in advance
        else:  # Form has in-built validation errors
            context['cat_form'] = cat_form
            return render(request, 'dashboard/budget.html', context)

    return redirect('dashboard:budget')


def add_budget_entry(cat_obj, add=0, all=None):
    months = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']
    years = [str(date.today().year + add)]

    for y in years:
        for m in months:
            if (all):  # Happens only on November each year to extend budget list
                ALL_CATEGORIES = cat_obj
                for cat in ALL_CATEGORIES:
                    bud_obj = Budget()
                    bud_obj.bud_user = cat.cat_user
                    bud_obj.bud_date = datetime.strptime(m + '/01/' + y, '%m/%d/%Y')
                    bud_obj.bud_category = cat
                    bud_obj.bud_budgeted = Decimal('0')
                    bud_obj.save()
            else:
                bud_obj = Budget()
                bud_obj.bud_user = cat_obj.cat_user
                bud_obj.bud_date = datetime.strptime(m + '/01/' + y, '%m/%d/%Y')
                bud_obj.bud_category = cat_obj
                bud_obj.bud_budgeted = Decimal('0')
                bud_obj.save()


@login_required()
def edit_category_name(request):
    if request.method == 'POST':
        input_dict = request.POST.dict()
        if input_dict['action'] == 'edit':
            try:
                cat_obj = Category.objects.get(pk=input_dict['id'])
                if 'cat_name' in input_dict:
                    if cat_obj.cat_name != input_dict['cat_name'].upper():
                        if Category.objects.filter(cat_user=request.user).filter(cat_name=input_dict['cat_name']).count():
                            input_dict['error'] = "Category Name already in use."
                        else:
                            cat_obj.cat_name = input_dict['cat_name'].upper()
                            cat_obj.save()
                    else:
                        input_dict['nothing'] = 'nothing'
            except Exception:
                input_dict['nothing'] = 'nothing'
        else:  # Delete Request
            cat_obj = Category.objects.get(pk=input_dict['id'])
            cat_obj.delete()

        return HttpResponse(json.dumps(input_dict), content_type="application/json")
    else:
        return HttpResponse(json.dumps({"nothing to see": "this isn't happening"}), content_type="application/json")


@login_required()
def budget(request, date_range=None):
    context = {}

    # Get updated account balances of all accounts to display in sidebar
    NET_WORTH = _update_accounts(request)
    CASH, CHECKING, SAVINGS, CREDIT_CARD, LINE_OF_CREDIT, LOANS = _get_updated_account_balances(request)
    context['CASH'] = CASH
    context['CHECKING'] = CHECKING
    context['SAVINGS'] = SAVINGS
    context['CREDIT_CARD'] = CREDIT_CARD
    context['LINE_OF_CREDIT'] = LINE_OF_CREDIT
    context['LOANS'] = LOANS
    context['NET_WORTH'] = NET_WORTH
    # ---------------------------------------------------------------------------

    # List all categories and display a blank form to add new category
    ALL_CATEGORIES = Category.objects.filter(cat_user=request.user).exclude(cat_name='DELETED').exclude(
        cat_name='TRANSFER').exclude(cat_name='INCOME').order_by('cat_name')
    context['ALL_CATEGORIES'] = ALL_CATEGORIES
    cat_form = CategoryForm(None)
    context['cat_form'] = cat_form
    # ---------------------------------------------------------------------------

    # Get date ranges of Prev, Current, Next months
    current_month_from, current_month_to = _get_curr_month_range(date_range)
    prev_month_from, prev_month_to = _get_prev_month_range(current_month_from)
    next_month_from, next_month_to = _get_next_month_range(current_month_to)
    context['current_month_from'] = current_month_from.__format__('%B %Y').upper()
    context['prev_month_from'] = prev_month_from.__format__('%B %Y').upper()
    context['next_month_from'] = next_month_from.__format__('%B %Y').upper()
    context['tran_range_for_budget'] = current_month_from.__format__('%m/%d/%Y')+':'+current_month_to.__format__('%m/%d/%Y')
    context['cat_name'] = 'All'
    # ---------------------------------------------------------------------------


    try:
        # PREVIOUS BUDGET STUFF
        prev_prev_month_from, prev_prev_month_to = _get_prev_month_range(prev_month_from)
        prev_prev_month_not_or_over_budgeted = _get_master_bud_balance(request, prev_prev_month_from, prev_prev_month_to)
        overspent_prev_prev_month = _get_overspent_total(request, prev_prev_month_from, prev_prev_month_to)
        income_for_prev_month = _get_income_total(request, prev_month_from, prev_month_to)
        budgeted_for_prev_month = _get_budgeted_total(request, prev_month_from, prev_month_to)
        prev_month_available_to_budget = prev_prev_month_not_or_over_budgeted + overspent_prev_prev_month + income_for_prev_month - budgeted_for_prev_month
        outflows_for_prev_month = _get_outflows_total(request, prev_month_from, prev_month_to)
        balance_for_prev_month = _get_balance_total(request, prev_month_from, prev_month_to)
        ALL_PREV_BUDGETS = _get_budgets_in_range(request, prev_month_from, prev_month_to)
        context['prev_month_available_to_budget'] = prev_month_available_to_budget
        context['income_for_prev_month'] = income_for_prev_month
        context['overspent_prev_prev_month'] = overspent_prev_prev_month
        context['prev_prev_month_not_or_over_budgeted'] = prev_prev_month_not_or_over_budgeted
        context['budgeted_for_prev_month'] = budgeted_for_prev_month
        context['outflows_for_prev_month'] = outflows_for_prev_month
        context['balance_for_prev_month'] = balance_for_prev_month
        context['ALL_PREV_BUDGETS'] = ALL_PREV_BUDGETS
        # ---------------------------------------------------------------------------

        # CURRENT BUDGET STUFF
        prev_month_not_or_over_budgeted = _get_master_bud_balance(request, prev_month_from, prev_month_to)
        overspent_prev_month = _get_overspent_total(request, prev_month_from, prev_month_to)
        income_for_curr_month = _get_income_total(request, current_month_from, current_month_to)
        budgeted_for_curr_month = _get_budgeted_total(request, current_month_from, current_month_to)
        curr_month_available_to_budget = prev_month_not_or_over_budgeted + overspent_prev_month + income_for_curr_month - budgeted_for_curr_month
        outflows_for_curr_month = _get_outflows_total(request, current_month_from, current_month_to)
        balance_for_curr_month = _get_balance_total(request, current_month_from, current_month_to)
        ALL_CURR_BUDGETS = _get_budgets_in_range(request, current_month_from, current_month_to)
        context['curr_month_available_to_budget'] = curr_month_available_to_budget
        context['income_for_curr_month'] = income_for_curr_month
        context['overspent_prev_month'] = overspent_prev_month
        context['prev_month_not_or_over_budgeted'] = prev_month_not_or_over_budgeted
        context['budgeted_for_curr_month'] = budgeted_for_curr_month
        context['outflows_for_curr_month'] = outflows_for_curr_month
        context['balance_for_curr_month'] = balance_for_curr_month
        context['ALL_CURR_BUDGETS'] = ALL_CURR_BUDGETS
        # ---------------------------------------------------------------------------

        # NEXT BUDGET STUFF
        curr_month_not_or_over_budgeted = _get_master_bud_balance(request, current_month_from, current_month_to)
        overspent_curr_month = _get_overspent_total(request, current_month_from, current_month_to)
        income_for_next_month = _get_income_total(request, next_month_from, next_month_to)
        budgeted_for_next_month = _get_budgeted_total(request, next_month_from, next_month_to)
        next_month_available_to_budget = curr_month_not_or_over_budgeted + overspent_curr_month + income_for_next_month - budgeted_for_next_month
        outflows_for_next_month = _get_outflows_total(request, next_month_from, next_month_to)
        balance_for_next_month = _get_balance_total(request, next_month_from, next_month_to)
        ALL_NEXT_BUDGETS = _get_budgets_in_range(request, next_month_from, next_month_to)
        context['next_month_available_to_budget'] = next_month_available_to_budget
        context['income_for_next_month'] = income_for_next_month
        context['overspent_curr_month'] = overspent_curr_month
        context['curr_month_not_or_over_budgeted'] = curr_month_not_or_over_budgeted
        context['budgeted_for_next_month'] = budgeted_for_next_month
        context['outflows_for_next_month'] = outflows_for_next_month
        context['balance_for_next_month'] = balance_for_next_month
        context['ALL_NEXT_BUDGETS'] = ALL_NEXT_BUDGETS
        # ---------------------------------------------------------------------------
    except Exception: # A new user wont have anything to display at the beginning
        context['prev_month_available_to_budget'] = Decimal('0.00')
        context['income_for_prev_month'] = Decimal('0.00')
        context['overspent_prev_prev_month'] = Decimal('0.00')
        context['prev_prev_month_not_or_over_budgeted'] = Decimal('0.00')
        context['budgeted_for_prev_month'] = Decimal('0.00')
        context['outflows_for_prev_month'] = Decimal('0.00')
        context['balance_for_prev_month'] = Decimal('0.00')

        context['curr_month_available_to_budget'] = Decimal('0.00')
        context['income_for_curr_month'] = Decimal('0.00')
        context['overspent_prev_month'] = Decimal('0.00')
        context['prev_month_not_or_over_budgeted'] = Decimal('0.00')
        context['budgeted_for_curr_month'] = Decimal('0.00')
        context['outflows_for_curr_month'] = Decimal('0.00')
        context['balance_for_curr_month'] = Decimal('0.00')

        context['next_month_available_to_budget'] = Decimal('0.00')
        context['income_for_next_month'] = Decimal('0.00')
        context['overspent_curr_month'] = Decimal('0.00')
        context['curr_month_not_or_over_budgeted'] = Decimal('0.00')
        context['budgeted_for_next_month'] = Decimal('0.00')
        context['outflows_for_next_month'] = Decimal('0.00')
        context['balance_for_next_month'] = Decimal('0.00')


    try:
        # No need to display anything if there aren't any transactions created.
        starting = Budget.objects.filter(bud_user=request.user)[0].bud_date
        starting = datetime.strptime(str(starting.year) + '-' + str(starting.month) + '-01','%Y-%m-%d')
        if prev_month_from <= starting:
            pass
        else:
            # Update all budgets with correct data
            _set_budgets_outflows(request, prev_month_from, prev_month_to)
            _set_budgets_balance(request, prev_month_from, prev_month_to)
            _set_budgets_outflows(request, current_month_from, current_month_to)
            _set_budgets_balance(request, current_month_from, current_month_to)
            _set_budgets_outflows(request, next_month_from, next_month_to)
            _set_budgets_balance(request, next_month_from, next_month_to)
            # ---------------------------------------------------------------------------
    except Exception: # A new user wont have anything to display at the beginning
        pass

    return render(request, 'dashboard/budget.html', context)



@login_required()
def editBudget(request):
    if request.method == 'POST':
        input_dict = request.POST.dict()
        if input_dict['action'] == 'edit':
            try:
                bud_obj = Budget.objects.get(pk=input_dict['id'])
                if 'bud_budgeted' in input_dict:
                    try:
                        if bud_obj.bud_budgeted != float(input_dict['bud_budgeted'].replace(',','')):
                            bud_obj.bud_budgeted = float(input_dict['bud_budgeted'].replace(',',''))
                            bud_obj.save()
                        else:
                            input_dict['nothing'] = 'nothing'
                    except Exception:
                        input_dict['error'] = "Invalid number for currency entered."
                else:
                    input_dict['nothing'] = 'nothing'
            except Exception:
                input_dict['nothing'] = 'nothing'
        else: # This won't happen. There is no DELETE button fot budget entries.
            input_dict['nothing'] = 'nothing'

        return HttpResponse(json.dumps(input_dict), content_type="application/json")
    else:
        return HttpResponse(json.dumps({"nothing to see": "this isn't happening"}), content_type="application/json")







def _get_master_bud_balance(request, from_date, to_date):
    starting = Budget.objects.filter(bud_user=request.user)[0].bud_date
    starting = datetime.strptime(str(starting.year) + '-' + str(starting.month) + '-01','%Y-%m-%d')
    if from_date <= starting:
        return Decimal('0.00')
    else:
        prev_month_from, prev_month_to = _get_prev_month_range(from_date)
        prev_month_budget_balance = _get_master_bud_balance(request, prev_month_from, prev_month_to)
        prev_month_overspent = _get_overspent_total(request, prev_month_from, prev_month_to)
        income_this_month = _get_income_total(request, from_date, to_date)
        budgeted_this_month = _get_budgeted_total(request, from_date, to_date)
        return  prev_month_budget_balance + prev_month_overspent + income_this_month - budgeted_this_month


def _get_outflows_total(request, from_date, to_date):
    budgets_in_range = _get_budgets_in_range(request, from_date, to_date)
    outflows = Decimal('0.00')
    for b in budgets_in_range:
        outflows += b.bud_outflows
    return outflows


def _get_balance_total(request, from_date, to_date):
    budgets_in_range = _get_budgets_in_range(request, from_date, to_date)
    balance = Decimal('0.00')
    for b in budgets_in_range:
        balance += b.bud_balance
    return balance


def _get_budgeted_total(request, from_date, to_date):
    budgets_in_range = _get_budgets_in_range(request, from_date, to_date)
    budgetted = Decimal('0.00')
    for b in budgets_in_range:
        budgetted += b.bud_budgeted
    return budgetted


def _get_income_total(request, from_date, to_date):
    relevant_tranasctios = Transaction.objects.filter(tran_user=request.user).filter(tran_date__range=[from_date, to_date]).filter(tran_category__cat_name='INCOME')
    income_total =  relevant_tranasctios.aggregate(income=Sum('tran_inflow'))['income']
    if income_total is None:
        return Decimal('0.00')
    return income_total


def _get_overspent_total(request, from_date, to_date):
    budgets_in_range = _get_budgets_in_range(request, from_date, to_date)
    overspent = Decimal('0.00')
    for b in budgets_in_range:
        if b.bud_balance < 0:
            overspent += b.bud_balance
    return overspent


def _set_budgets_balance(request, from_date, to_date):
    budgets_in_range = _get_budgets_in_range(request, from_date, to_date)
    prev_month_from = _get_prev_month_range(from_date)[0]
    for b in budgets_in_range:
        cat_obj = b.bud_category
        prev_month_balance = _get_balance_cat_in_date(request, cat_obj, prev_month_from)
        b.bud_balance = prev_month_balance + b.bud_budgeted - b.bud_outflows
        b.save()


def _set_budgets_outflows(request, from_date, to_date):
    budgets_in_range = _get_budgets_in_range(request, from_date, to_date)
    for b in budgets_in_range:
        cat_obj = b.bud_category
        bud_outflows = _get_outflows_cat_in_date_range(request, cat_obj, from_date, to_date)
        if bud_outflows is None:
            b.bud_outflows = Decimal('0')
        else:
            b.bud_outflows = bud_outflows
        b.save()


def _get_balance_cat_in_date(request, cat_obj, from_date):
    bud_obj = Budget.objects.filter(bud_user=request.user).filter(bud_date__exact=from_date).filter(bud_category=cat_obj)
    if bud_obj is None:
        return Decimal('0')
    else:
        return bud_obj[0].bud_balance


def _get_outflows_cat_in_date_range(request, cat_obj, from_date, to_date):
    relevant_tranasctios = Transaction.objects.filter(tran_user=request.user).filter(tran_date__range=[from_date, to_date]).filter(tran_category=cat_obj)
    return relevant_tranasctios.aggregate(outflows=Sum('tran_outflow'))['outflows']


def _get_budgets_in_range(request, from_date, to_date):
    return Budget.objects.filter(bud_user=request.user).filter(bud_date__range=[from_date, to_date]).order_by('bud_category__cat_name')


def _get_curr_month_range(date_range):
    if date_range:
        current_month_from = datetime.strptime(date_range, '%m/%Y')
    else:
        current_month_from = str(date.today().year) + '-' + str(date.today().month).zfill(2) + '-01'
        current_month_from = datetime.strptime(current_month_from, '%Y-%m-%d')
    days = calendar.monthrange(int(current_month_from.year), int(current_month_from.month))[1]
    current_month_to = datetime.strptime(str(current_month_from.year) + '-' + str(current_month_from.month).zfill(2) + '-' + str(days), '%Y-%m-%d')
    return current_month_from, current_month_to


def _get_prev_month_range(current_month_from):
    prev_month_to = current_month_from - timedelta(days=1)
    prev_month_from = datetime.strptime(str(prev_month_to.year) + '-' + str(prev_month_to.month).zfill(2) + '-01', '%Y-%m-%d')
    return prev_month_from, prev_month_to


def _get_next_month_range(current_month_to):
    next_month_from = current_month_to + timedelta(days=1)
    days = calendar.monthrange(int(next_month_from.year), int(next_month_from.month))[1]
    next_month_to = datetime.strptime(str(next_month_from.year) + '-' + str(next_month_from.month).zfill(2) + '-' + str(days), '%Y-%m-%d')
    return next_month_from, next_month_to







@login_required()
def reports(request, date_range=None):
    context = {}

    # Get updated account balances of all accounts to display in sidebar
    NET_WORTH = _update_accounts(request)
    CASH, CHECKING, SAVINGS, CREDIT_CARD, LINE_OF_CREDIT, LOANS = _get_updated_account_balances(request)
    context['CASH'] = CASH
    context['CHECKING'] = CHECKING
    context['SAVINGS'] = SAVINGS
    context['CREDIT_CARD'] = CREDIT_CARD
    context['LINE_OF_CREDIT'] = LINE_OF_CREDIT
    context['LOANS'] = LOANS
    context['NET_WORTH'] = NET_WORTH
    # ---------------------------------------------------------------------------

    # Used when filtering results on transactions page
    current_month_from, current_month_to = _get_curr_month_range(None)
    context['tran_range_for_budget'] = current_month_from.__format__('%m/%d/%Y')+':'+current_month_to.__format__('%m/%d/%Y')
    context['cat_name'] = 'All'
    # ---------------------------------------------------------------------------



    if date_range:
        tran_from_date = datetime.strptime(date_range.split(':')[0], '%m/%d/%Y')
        tran_to_date = datetime.strptime(date_range.split(':')[1], '%m/%d/%Y')
        context['tran_range'] = tran_from_date.__format__('%B %d, %Y') + ' - ' + tran_to_date.__format__('%B %d, %Y')
        context['start_date'] = tran_from_date.__format__('%m/%d/%Y')
        context['end_date'] = tran_to_date.__format__('%m/%d/%Y')
    else:
        tran_from_date = current_month_from
        tran_to_date = current_month_to
        context['tran_range'] = current_month_from.__format__('%B %d, %Y') + ' - ' + current_month_to.__format__('%B %d, %Y')
        context['start_date'] = current_month_from.__format__('%m/%d/%Y')
        context['end_date'] = current_month_to.__format__('%m/%d/%Y')

    ALL_TRANSACTIONS = Transaction.objects.filter(tran_user=request.user).exclude(tran_category__cat_name='INCOME').exclude(tran_category__cat_name='TRANSFER').exclude(tran_category__cat_name='DELETED').filter(tran_date__range=[tran_from_date, tran_to_date])
    context['CATEGORY_REPORTS'],context['CATEGORY_TOTAL']  = get_category_reports(request, ALL_TRANSACTIONS, tran_from_date, tran_to_date)
    context['PAYEE_REPORTS'],context['PAYEE_TOTAL'] = get_payee_reports(request, ALL_TRANSACTIONS, tran_from_date, tran_to_date)

    return render(request, 'dashboard/reports.html', context)



def get_category_reports(request, ALL_TRANSACTIONS, from_date, to_date):
    result = {}
    total = 0
    col = 0
    for t in ALL_TRANSACTIONS:
        if t.tran_category.cat_name not in result:
            r = ['#4D4D4D', '#5DA5DA', '#FAA43A', '#60BD68', '#F17CB0', '#B2912F', '#B276B2', '#DECF3F', '#F15854']
            value_dict = {}
            value_dict['amount'] = _get_outflows_cat_in_date_range(request, t.tran_category, from_date, to_date)
            total += value_dict['amount']
            value_dict['colour'] = r[col]
            result[t.tran_category.cat_name] = value_dict
            col += 1
            if col > 8:
                col = 0
    return result, total


def get_payee_reports(request, ALL_TRANSACTIONS, from_date, to_date):
    result = {}
    total = 0
    col = 0
    for t in ALL_TRANSACTIONS:
        if t.tran_payee not in result:
            r = ['#4D4D4D', '#5DA5DA', '#FAA43A', '#60BD68', '#F17CB0', '#B2912F', '#B276B2', '#DECF3F', '#F15854']
            value_dict = {}
            value_dict['amount'] = _get_outflows_payee_in_date_range(request, t.tran_payee, from_date, to_date)
            total += value_dict['amount']
            value_dict['colour'] = r[col]
            result[t.tran_payee] = value_dict
            col += 1
            if col > 8:
                col = 0

    return result, total


def _get_outflows_payee_in_date_range(request, payee, from_date, to_date):
    relevant_tranasctios = Transaction.objects.filter(tran_user=request.user).filter(
        tran_date__range=[from_date, to_date]).filter(tran_payee=payee)
    return relevant_tranasctios.aggregate(outflows=Sum('tran_outflow'))['outflows']

