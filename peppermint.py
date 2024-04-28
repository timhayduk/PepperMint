from bson.objectid import ObjectId
from calendar import month_name
from datetime import datetime
from dateutil.relativedelta import *
from flask import Flask, render_template, request, url_for, flash, redirect
from re import search, IGNORECASE
from pymongo import MongoClient
from utils import get_db_connection
from werkzeug.exceptions import abort


# def get_post(post_id):
#     db_connection = get_db_connection()
#     collection_name = db_connection['sandbox']
#     post = collection_name.find_one({"_id": str(post_id)})
#     if post is None:
#         abort(404)
#     return post


app = Flask(__name__)
app.config['SECRET_KEY'] = 'abcd1234'


ACCOUNT_MAP = {}
CATEGORY_MAP = {}
INCOME_NAMES = ['paycheck', 'stocks', 'interest', 'credit card cash back']
NON_CASH_FLOW_NAMES = ['Transfer', 'Credit Card Payment', 'Stock Deposit']

def update_account_map():
    db_connection = get_db_connection()
    accounts = db_connection['accounts']
    accounts_list = list(accounts.find({}))
    for account in accounts_list:
        ACCOUNT_MAP[str(account['_id'])] = account['name']


def update_category_map():
    db_connection = get_db_connection()
    categories = db_connection['categories']
    categories_list = list(categories.find({}))
    for category in categories_list:
        CATEGORY_MAP[str(category['_id'])] = category['icon']


def get_rules():
    db_connection = get_db_connection()
    rules = db_connection['rules']
    return list(rules.find({}))


def update_account_balance(account_id, transaction_amount):
    db_connection = get_db_connection()
    accounts = db_connection['accounts']
    account = accounts.find_one({'_id': account_id})
    accounts.update_one({'_id': account_id}, {'$set': {'balance': round(account['balance'] + transaction_amount, 2)}})


@app.route('/')
def index():
    net_worth = 0.0
    db_connection = get_db_connection()
    accounts = db_connection['accounts']
    accounts_list = list(accounts.find({}))
    for account in accounts_list:
        net_worth = round(net_worth + account['balance'], 2)

    return render_template('index.html', net_worth=net_worth)


@app.route('/accounts')
def accounts():
    db_connection = get_db_connection()
    accounts = db_connection['accounts']
    accounts_list = list(accounts.find({}).sort({'name': 1}))
    return render_template('accounts/accounts.html', accounts=accounts_list)


@app.route('/accounts/create', methods=('GET', 'POST'))
def create_account():
    db_connection = get_db_connection()
    accounts = db_connection['accounts']

    if request.method == 'POST':
        accounts.insert_one({
            'name': request.form['name'],
            'description': request.form['description'],
            'balance': float(request.form['balance']),
        })
        return redirect(url_for('accounts'))
    
    return  render_template('accounts/create_account.html')


@app.route('/accounts/<string:id>/edit', methods=('GET', 'POST'))
def edit_account(id):
    db_connection = get_db_connection()
    accounts = db_connection['accounts']
    account = accounts.find_one({'_id': ObjectId(id)})

    if request.method == 'POST':
        accounts.update_one({'_id': account['_id']}, {
            '$set': {
            'name': request.form['name'],
            'description': request.form['description'],
            'balance': float(request.form['balance']),
        }
        })
        return redirect(url_for('accounts'))
    
    return render_template('accounts/edit_account.html', account=account)


@app.route('/accounts/<string:id>/delete')
def delete_account(id):
    db_connection = get_db_connection()
    accounts = db_connection['accounts']
    account = accounts.find_one({'_id': ObjectId(id)})
    accounts.delete_one({'_id': ObjectId(id)})

    flash('"{}" was successfully deleted!'.format(account['name']))
    return redirect(url_for('accounts'))


@app.route('/transactions')
def transactions(category='all'):
    date = datetime.now()
    year = date.year
    month = date.month
    return(redirect(url_for('transactions_by_month', year=year, month=month, category=category)))


@app.route('/transactions_next_month/<string:year>/<string:month>/<string:category>')
def transactions_next_month(year, month, category):
    next_month = datetime(year=int(year), month=int(month), day=1) + relativedelta(months=+1)
    return(redirect(url_for('transactions_by_month', year=next_month.year, month=next_month.month, category=category)))


@app.route('/transactions_previous_month/<string:year>/<string:month>/<string:category>')
def transactions_previous_month(year, month, category):
    prev_month = datetime(year=int(year), month=int(month), day=1) + relativedelta(months=-1)
    return(redirect(url_for('transactions_by_month', year=prev_month.year, month=prev_month.month, category=category)))


@app.route('/transactions/<string:year>/<string:month>/<string:category>', methods=('GET', 'POST'))
def transactions_by_month(year, month, category='all'):
    if request.method == 'POST':
        return(redirect(url_for('transactions_by_month', year=year, month=month, category=request.form['category'])))
    db_connection = get_db_connection()
    transactions = db_connection['transactions']
    categories = db_connection['categories']
    budgets = db_connection['budgets']

    time_next_month = datetime(year=int(year), month=int(month), day=1) + relativedelta(months=+1)
    this_month = f"{year}-{str(month).zfill(2)}"
    next_month = f"{time_next_month.year}-{str(time_next_month.month).zfill(2)}"
    query = {'$and': [
        {'date': {'$gte': this_month}},
        {'date': {'$lt': next_month}}
    ]}

    if category != 'all':
        # Only add a category filter if we're searching for one
        query['$and'].append({'category': category})
    transactions_list = list(transactions.find(query).sort({'date': -1}))

    update_account_map()
    update_category_map()
    for transaction in transactions_list:
        cat_id = "unknown" if transaction['category'] == "unknown" else ObjectId(transaction['category'])
        category = list(categories.find({'_id': cat_id}))[0]
        budget_list = list(budgets.find({'category': transaction['category']}))

        if len(budget_list) == 0 and category['name'] not in NON_CASH_FLOW_NAMES:
            flash('"{}" did not have a budget for category "{}"!'.format(transaction['description'], category['name']))

        if transaction['account'] in ACCOUNT_MAP.keys():
            transaction['account'] = ACCOUNT_MAP[transaction['account']]
        else:
            transaction['account'] = f"UNKNOWN ACCOUNT ({transaction['account']})"
        
        if 'to_account' in transaction.keys() and transaction['to_account'] is not None:
            if transaction['to_account'] in ACCOUNT_MAP.keys():
                transaction['account'] += f" -> {ACCOUNT_MAP[transaction['to_account']]}"
            else:
                transaction['account'] += f" -> UNKNOWN ACCOUNT ({transaction['to_account']})"

        if 'category' in transaction.keys() and transaction['category'] in CATEGORY_MAP.keys():
            transaction['icon'] = CATEGORY_MAP[transaction['category']]
        else:
            transaction['icon'] = CATEGORY_MAP['unknown']
    
    categories_list = categories.find({})

    return render_template('transactions/transactions.html', year=year, month=month, transactions=transactions_list, categories_list=categories_list, category=category)


@app.route('/transactions/create', methods=('GET', 'POST'))
def create_transaction():
    db_connection = get_db_connection()
    transactions = db_connection['transactions']

    if request.method == 'POST':
        new_transaction = {
            'account': request.form['account'],
            'category': request.form['category'],
            'description': request.form['description'],
            'amount': float(request.form['amount']),
            'date': request.form['date'],
        }

        if request.form['to_account'] != "None":
            new_transaction['to_account'] = request.form['to_account']
        else:
            new_transaction['to_account'] = None

        rules = get_rules()
        for rule in rules:
            if search(rule['regex'], new_transaction['description'], flags=IGNORECASE) is not None:
                new_transaction['category'] = rule['category']
                break

        transactions.insert_one(new_transaction)

        if new_transaction['to_account'] is not None:
            update_account_balance(ObjectId(new_transaction['account']), -float(new_transaction['amount']))
            update_account_balance(ObjectId(new_transaction['to_account']), float(new_transaction['amount']))
        else:
            update_account_balance(ObjectId(new_transaction['account']), float(new_transaction['amount']))

        return redirect(url_for('transactions'))
    
    accounts = db_connection['accounts']
    accounts_list = list(accounts.find({}))
    categories = db_connection['categories']
    categories_list = list(categories.find({}))
    return  render_template('transactions/create_transaction.html', accounts=accounts_list, categories_list=categories_list)


@app.route('/transactions/<string:id>/edit', methods=('GET', 'POST'))
def edit_transaction(id):
    db_connection = get_db_connection()
    transactions = db_connection['transactions']
    transaction = transactions.find_one({'_id': ObjectId(id)})

    if request.method == 'POST':
        transactions.update_one({'_id': transaction['_id']}, {
            '$set': {
                'category': request.form['category'],
                'description': request.form['description'],
                'amount': float(request.form['amount']),
                'date': request.form['date']
            }
        })
        return redirect(url_for('transactions'))
    
    update_account_map()
    if transaction['account'] in ACCOUNT_MAP.keys():
        transaction['account'] = ACCOUNT_MAP[transaction['account']]
    else:
        transaction['account'] = "UNKNOWN ACCOUNT"

    if transaction['to_account'] in ACCOUNT_MAP.keys():
        transaction['to_account'] = ACCOUNT_MAP[transaction['to_account']]
    elif transaction['to_account'] is not None:
        transaction['to_account'] = "UNKNOWN ACCOUNT"

    categories = db_connection['categories']
    categories_list = list(categories.find({}))
    return  render_template('transactions/edit_transaction.html', transaction=transaction, categories_list=categories_list)


@app.route('/transactions/<string:id>/delete/<string:undo_transaction>')
def delete_transaction(id, undo_transaction=False):
    db_connection = get_db_connection()
    transactions = db_connection['transactions']
    transaction = transactions.find_one({'_id': ObjectId(id)})
    transactions.delete_one({'_id': ObjectId(id)})

    # Undo the transaction from the account balances
    if bool(undo_transaction):
        if 'to_account' in transaction.keys() and transaction['to_account'] is not None:
            update_account_balance(ObjectId(transaction['account']), float(transaction['amount']))
            update_account_balance(ObjectId(transaction['to_account']), -float(transaction['amount']))
        else:
            update_account_balance(ObjectId(transaction['account']), -float(transaction['amount']))

    flash('"{} - {}" was successfully deleted!'.format(transaction['account'], transaction['description']))
    return redirect(url_for('transactions'))


@app.route('/categories')
def categories():
    db_connection = get_db_connection()
    categories = db_connection['categories']
    categories_list = list(categories.find({}))
    return render_template('categories/categories.html', categories=categories_list)


@app.route('/categories/create', methods=('GET', 'POST'))
def create_category():
    db_connection = get_db_connection()
    categories = db_connection['categories']

    if request.method == 'POST':
        categories.insert_one({
            'icon': request.form['icon'],
            'name': request.form['name'],
            'description': request.form['description'],
        })
        return redirect(url_for('categories'))
    
    return  render_template('categories/create_category.html')


@app.route('/categories/<string:id>/edit', methods=('GET', 'POST'))
def edit_category(id):
    db_connection = get_db_connection()
    categories = db_connection['categories']
    category = categories.find_one({'_id': ObjectId(id)})

    if request.method == 'POST':
        categories.update_one({'_id': category['_id']}, {
            '$set': {
                'icon': request.form['icon'],
                'name': request.form['name'],
                'description': request.form['description'],
            }
        })
        return redirect(url_for('categories'))
    
    return  render_template('edit_category.html', category=category)


@app.route('/categories/<string:id>/delete')
def delete_category(id):
    db_connection = get_db_connection()
    categories = db_connection['categories']
    category = categories.find_one({'_id': ObjectId(id)})
    categories.delete_one({'_id': ObjectId(id)})

    flash('"{}" was successfully deleted!'.format(category['name']))
    return redirect(url_for('categories'))


@app.route('/rules')
def rules():
    db_connection = get_db_connection()
    rules = db_connection['rules']
    rules_list = list(rules.find({}))

    update_category_map()
    for rule in rules_list:
        if rule['category'] in CATEGORY_MAP.keys():
            rule['category'] = CATEGORY_MAP[rule['category']]
        else:
            rule['category'] = f"UNKNOWN CATEGORY ({rule['category']})"

    return render_template('rules/rules.html', rules=rules_list)


@app.route('/rules/create', methods=('GET', 'POST'))
def create_rule():
    db_connection = get_db_connection()
    rules = db_connection['rules']

    if request.method == 'POST':
        rules.insert_one({
            'name': request.form['name'],
            'description': request.form['description'],
            'regex': request.form['regex'],
            'category': request.form['category'],
        })
        return redirect(url_for('rules'))
    
    categories = db_connection['categories']
    categories_list = categories.find({})
    return  render_template('rules/create_rule.html', categories=categories_list)


@app.route('/rules/<string:id>/edit', methods=('GET', 'POST'))
def edit_rule(id):
    db_connection = get_db_connection()
    rules = db_connection['rules']
    rule = rules.find_one({'_id': ObjectId(id)})

    if request.method == 'POST':
        rules.update_one({'_id': rule['_id']}, {
            '$set': {
                'name': request.form['name'],
                'description': request.form['description'],
                'regex': request.form['regex'],
                'category': request.form['category'],
            }
        })
        return redirect(url_for('rules'))
    
    categories = db_connection['categories']
    categories_list = categories.find({})
    return render_template('rules/edit_rule.html', rule=rule, categories=categories_list)


@app.route('/rules/<string:id>/delete')
def delete_rule(id):
    db_connection = get_db_connection()
    rules = db_connection['rules']
    rule = rules.find_one({'_id': ObjectId(id)})
    rules.delete_one({'_id': ObjectId(id)})

    flash('"{}" was successfully deleted!'.format(rule['name']))
    return redirect(url_for('rules'))


@app.route('/budgets')
def budgets():
    date = datetime.now()
    year = date.year
    month = date.month
    return(redirect(url_for('budgets_by_month', year=year, month=month)))


@app.route('/budgets_next_month/<string:year>/<string:month>')
def budgets_next_month(year, month):
    next_month = datetime(year=int(year), month=int(month), day=1) + relativedelta(months=+1)
    return(redirect(url_for('budgets_by_month', year=next_month.year, month=next_month.month)))


@app.route('/budgets_previous_month/<string:year>/<string:month>')
def budgets_previous_month(year, month):
    prev_month = datetime(year=int(year), month=int(month), day=1) + relativedelta(months=-1)
    return(redirect(url_for('budgets_by_month', year=prev_month.year, month=prev_month.month)))


def calculate_cash_flow_month(year, month):
     # Calculate the over all cash flow for the month
    db_connection = get_db_connection()
    categories = db_connection['categories']
    transfer_categories = list(categories.find({'name': {'$in': NON_CASH_FLOW_NAMES}}))

    transfer_categories_ids = [str(cat['_id']) for cat in transfer_categories]

    transactions = db_connection['transactions']
    time_next_month = datetime(year=int(year), month=int(month), day=1) + relativedelta(months=+1)
    this_month = f"{year}-{str(month).zfill(2)}"
    next_month = f"{time_next_month.year}-{str(time_next_month.month).zfill(2)}"
    query = {'$and': [
        {'category': {'$nin': transfer_categories_ids}},
        {'date': {'$gte': this_month}},
        {'date': {'$lt': next_month}}
    ]}
    transactions_list = list(transactions.find(query).sort({'date': 1}))
    total_cash_flow = 0.0
    for transaction in transactions_list:
        total_cash_flow = round(total_cash_flow + transaction['amount'], 2)

    return total_cash_flow


def calculate_budget_spending(budget, year, month):
    # Calculate the budget's progress for the month
    db_connection = get_db_connection()
    transactions = db_connection['transactions']
    time_next_month = datetime(year=int(year), month=int(month), day=1) + relativedelta(months=+1)
    this_month = f"{year}-{str(month).zfill(2)}"
    next_month = f"{time_next_month.year}-{str(time_next_month.month).zfill(2)}"
    query = {'$and': [
        {'category': budget['category']},
        {'date': {'$gte': this_month}},
        {'date': {'$lt': next_month}}
    ]}
    transactions_list = list(transactions.find(query).sort({'date': 1}))
    total_transaction_amount = 0.0
    for transaction in transactions_list:
        total_transaction_amount = round(total_transaction_amount + transaction['amount'], 2)
    total_transaction_amount = round(total_transaction_amount, 2)
    return total_transaction_amount


@app.route('/budgets/<string:year>/<string:month>')
def budgets_by_month(year, month):
    db_connection = get_db_connection()
    budgets = db_connection['budgets']
    budgets_list = list(budgets.find({}).sort({'name': 1}))

    overall_stats = {
        'total_income': 0.0,
        'total_spending': 0.0,
        'cash_flow': 0.0,
        'total_budgeted_income': 0.0,
        'total_budgeted_spending': 0.0,
        'total_budget_percentage': 0.0,
    }

    income_budgets = []
    over_budgets = []
    warning_budgets = []
    good_budgets = []

    for budget in budgets_list:
        # Process the name into a class name for dynamic styles on the progress bars
        budget['class_name'] = '_'.join(budget['name'].split(' '))

        # Calculate the budget's progress for the month
        budget['total'] = calculate_budget_spending(budget, year, month)
        if budget['amount'] != 0.0:
            budget['progress'] = round((budget['total'] / budget['amount']) * 100.0, 2)
        else:
            budget['progress'] = 100.0

        # Process the category ID into the human-readable name
        update_category_map()
        budget['category_id'] = budget['category']
        if budget['category'] in CATEGORY_MAP:
            budget['category'] = CATEGORY_MAP[budget['category']]
        else:
            budget['category'] = f"UNKNOWN CATEGORY ({budget['category']})"

        if budget['total'] > 0:
            overall_stats['total_income'] = round(overall_stats['total_income'] + budget['total'], 2)
        else:
            overall_stats['total_spending'] = round(overall_stats['total_spending'] + budget['total'], 2)
        
        # Separate out budgets into color categories
        if budget['name'].lower() in INCOME_NAMES:
            income_budgets.append(budget)
        elif budget['progress'] > 100.0:
            over_budgets.append(budget)
        elif budget['progress'] >= 75.0:
            warning_budgets.append(budget)
        else:
            good_budgets.append(budget)

        # Calculate total income vs. spending budget percentage
        if budget['name'].lower() in INCOME_NAMES:
            overall_stats['total_budgeted_income'] = round(overall_stats['total_budgeted_income'] + budget['amount'], 2)
        else:
            overall_stats['total_budgeted_spending'] = round(overall_stats['total_budgeted_spending'] + round(budget['amount'] / float(budget['period']), 2), 2)

    if overall_stats['total_budgeted_income'] != 0:
        overall_stats['total_budget_percentage'] = round((-overall_stats['total_budgeted_spending'] / overall_stats['total_budgeted_income']) * 100.0, 2)
    else:
        overall_stats['total_budget_percentage'] = 0.00

    if overall_stats['total_income'] != 0:
        overall_stats['total_percentage'] = round((-overall_stats['total_spending'] / overall_stats['total_income']) * 100.0, 2)
    else:
        overall_stats['total_percentage'] = 0.00

    overall_stats['cash_flow'] = round(overall_stats['total_income'] + overall_stats['total_spending'], 2)

    over_budgets = sorted(over_budgets, key=lambda x: x['progress'], reverse=True)
    warning_budgets = sorted(warning_budgets, key=lambda x: x['progress'], reverse=True)
    good_budgets = sorted(good_budgets, key=lambda x: x['progress'], reverse=True)

    return render_template('budgets/budgets.html', month_name=month_name[int(month)], year=year, month=month, income_budgets=income_budgets, over_budgets=over_budgets, warning_budgets=warning_budgets, good_budgets=good_budgets, overall_stats=overall_stats)


@app.route('/budgets/create', methods=('GET', 'POST'))
def create_budget():
    db_connection = get_db_connection()
    budgets = db_connection['budgets']

    if request.method == 'POST':
        carryover = 'carryover' in request.form.keys()
        budgets.insert_one({
            'name': request.form['name'],
            'description': request.form['description'],
            'category': request.form['category'],
            'amount': float(request.form['amount']),
            'period': int(request.form['period']),
            'carryover': carryover,
        })
        return redirect(url_for('budgets'))
    
    categories = db_connection['categories']
    categories_list = categories.find({})
    return  render_template('budgets/create_budget.html', categories_list=categories_list)


@app.route('/budgets/<string:id>/edit', methods=('GET', 'POST'))
def edit_budget(id):
    db_connection = get_db_connection()
    budgets = db_connection['budgets']
    budget = budgets.find_one({'_id': ObjectId(id)})

    if request.method == 'POST':
        carryover = 'carryover' in request.form.keys()
        budgets.update_one({'_id': budget['_id']}, {
            '$set': {
                'name': request.form['name'],
                'description': request.form['description'],
                'category': request.form['category'],
                'amount': float(request.form['amount']),
                'period': int(request.form['period']),
                'carryover': carryover,
            }
        })
        return redirect(url_for('budgets'))
    
    categories = db_connection['categories']
    categories_list = categories.find({})
    return render_template('budgets/edit_budget.html', budget=budget, categories_list=categories_list)


@app.route('/budgets/<string:id>/delete')
def delete_budget(id):
    db_connection = get_db_connection()
    budgets = db_connection['budgets']
    budget = budgets.find_one({'_id': ObjectId(id)})
    budgets.delete_one({'_id': ObjectId(id)})

    flash('"{}" was successfully deleted!'.format(budget['name']))
    return redirect(url_for('budgets'))


@app.route('/trends', methods=('GET', 'POST'))
def trends():
    return redirect(url_for('trends_by_budget', budget_filter='all'))


@app.route('/trends/<string:budget_filter>', methods=('GET', 'POST'))
def trends_by_budget(budget_filter='all'):
    if request.method == 'POST':
        return redirect(url_for('trends_by_budget', budget_filter=request.form['budget_filter']))

    db_connection = get_db_connection()
    budgets = db_connection['budgets']
    budgets_list = list(budgets.find({}))

    current_date = datetime.now()
    dates = [datetime(year=int(current_date.year), month=int(current_date.month), day=1) + relativedelta(months=x) for x in range(-12, 1)]
    years_and_months = [(d.year, d.month) for d in dates]

    income_datasets = []
    spending_datasets = []
    
    cash_flow_dataset = {
        'label': f"Cash Flow",
        'data': [],
        'borderWidth': 1,
        'type': 'bar',
        'backgroundColor': [],
    }

    for year_and_month in years_and_months:
        cash_flow_month = calculate_cash_flow_month(year_and_month[0], year_and_month[1])
        cash_flow_dataset['data'].append(cash_flow_month)
        
        if cash_flow_month < 0:
            cash_flow_dataset['backgroundColor'].append("rgba(247, 2, 2, 0.5)")
        else:
            cash_flow_dataset['backgroundColor'].append("rgba(27, 99, 20, 0.5)")
        

    for budget in budgets_list:
        if budget_filter.lower() != 'all' and budget['name'].lower() != budget_filter.lower() and budget['name'].lower() not in INCOME_NAMES:
            continue

        dataset = {
            'label': f"{budget['name']} Total",
            'data': [],
            'borderWidth': 1,
        }
        amount_line_dataset = {
            'label': f"{budget['name']} Budget",
            'data': [],
            'borderWidth': 1,
            'type': 'line',
            'fill': False,
        }
        average_line_dataset = {
            'label': f"{budget['name']} Average",
            'data': [],
            'borderWidth': 1,
            'type': 'line',
            'fill': False,
        }
        budget_total_amount = 0.0
        months_to_average = 0.0
        for year_and_month in years_and_months:
            budget_month_total = calculate_budget_spending(budget, year_and_month[0], year_and_month[1])
            if budget['name'].lower() not in INCOME_NAMES:
                budget_month_total = -budget_month_total
                amount_line_dataset['data'].append(-budget['amount'])
            else:
                amount_line_dataset['data'].append(budget['amount'])
            dataset['data'].append(budget_month_total)
            budget_total_amount = round(budget_total_amount + budget_month_total, 2)
            if budget_month_total > 0.0:
                months_to_average = round(months_to_average + 1.0, 2)

        if months_to_average > 0.0:
            average_budget_amount = round(budget_total_amount / months_to_average, 2)
        else:
            average_budget_amount = 0.0

        for year_and_month in years_and_months:
            average_line_dataset['data'].append(average_budget_amount)

        if budget['name'].lower() in INCOME_NAMES:
            income_datasets.append(dataset)
            income_datasets.append(amount_line_dataset)
            income_datasets.append(average_line_dataset)
        else:
            spending_datasets.append(dataset)
            spending_datasets.append(amount_line_dataset)
            spending_datasets.append(average_line_dataset)


    return render_template('trends/trends.html', budgets_list=budgets_list, years_and_months=years_and_months, cash_flow_datasets=[cash_flow_dataset], spending_datasets=spending_datasets, income_datasets=income_datasets)
