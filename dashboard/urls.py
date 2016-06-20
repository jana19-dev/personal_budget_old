from django.conf.urls import url
from . import views
from django.contrib.auth.decorators import login_required


urlpatterns = [
    url(r'^login/$', views.UserLoginFormView.as_view(), name='login'),
    url(r'^logout/$', views.logout_view, name='logout'),

    # Transactions
    url(r'^add_transaction/$', views.add_transaction, name='add_transaction'),
    url(r'^add_transaction/(?P<acc_name>[-_: a-zA-Z0-9]*)/$', views.add_transaction, name='add_pre_transaction'),
    url(r'^edit_transaction/$', views.edit_transaction, name='edit_transaction'),

    # Accounts
    url(r'^accounts/edit_account/$', views.edit_account, name='edit_account'),
    url(r'^accounts/$', views.accounts, name='accounts'),

    # Budget
    url(r'^budget/$', views.budget, name='budget'),
    url(r'^budget/addCategory/$', views.addCategory, name='addCategory'),
    url(r'^budget/edit_category_name/$', views.edit_category_name, name='edit_category_name'),
    url(r'^budget/editBudget/$', views.editBudget, name='editBudget'),
    url(r'^budget/(?P<date_range>(\d{2})[/.-](\d{4}))/$', views.budget, name='budget'),

    # Reports
    url(r'^reports/(?P<date_range>(\d{2})[/.-](\d{2})[/.-](\d{4}):(\d{2})[/.-](\d{2})[/.-](\d{4}))/$', views.reports, name='reports_filter'),
    url(r'^reports/$', views.reports, name='reports'),


    # FILTERING RESULTS ON TRANSACTION PAGE
    url(r'^(?P<date_range>(\d{2})[/.-](\d{2})[/.-](\d{4}):(\d{2})[/.-](\d{2})[/.-](\d{4}))/(?P<acc_name>[-_: a-zA-Z0-9]*)/(?P<cat_name>[-_ a-zA-Z0-9]*)/$', views.index, name='filter_results'),
    url(r'^(?P<bud_range>(\d{2})[/.-](\d{2})[/.-](\d{4})-.*)/$', views.index, name='filter_budget_range'),

    url(r'^$', views.index, name='index'),
]


# Matching text only with white space, underscore, semicolon [-_: a-zA-Z0-9]+