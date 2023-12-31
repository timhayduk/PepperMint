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
def transactions():
    db_connection = get_db_connection()
    transactions = db_connection['transactions']
    transactions_list = list(transactions.find({}).sort({'date': -1}))

    update_account_map()
    update_category_map()
    for transaction in transactions_list:
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
    return render_template('transactions/transactions.html', transactions=transactions_list)


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


@app.route('/budgets/<string:year>/<string:month>')
def budgets_by_month(year, month):
    db_connection = get_db_connection()
    budgets = db_connection['budgets']
    budgets_list = list(budgets.find({}).sort({'name': 1}))

    total_income = 0
    total_spending = 0

    for budget in budgets_list:
        # Process the name into a class name for dynamic styles on the progress bars
        budget['class_name'] = '_'.join(budget['name'].split(' '))

        # Calculate the budget's progress for the month
        transactions = db_connection['transactions']
        time_next_month = datetime(year=int(year), month=int(month), day=1) + relativedelta(months=+budget['period'])
        this_month = f"{year}-{str(month).zfill(2)}"
        next_month = f"{time_next_month.year}-{str(time_next_month.month).zfill(2)}"
        query = {'$and': [
            {'category': budget['category']},
            {'date': {'$gte': this_month}},
            {'date': {'$lt': next_month}}
        ]}
        transactions_list = list(transactions.find(query))
        total_transaction_amount = 0
        for transaction in transactions_list:
            total_transaction_amount = round(total_transaction_amount + transaction['amount'], 2)
        budget['total'] = round(total_transaction_amount, 2)
        budget['progress'] = round((total_transaction_amount / budget['amount']) * 100.0, 2)

        # Process the category ID into the human-readable name
        update_category_map()
        if budget['category'] in CATEGORY_MAP:
            budget['category'] = CATEGORY_MAP[budget['category']]
        else:
            budget['category'] = f"UNKNOWN CATEGORY ({budget['category']})"

        if budget['total'] > 0:
            total_income = round(total_income + budget['total'], 2)
        else:
            total_spending = round(total_spending + budget['total'], 2)

    cash_flow = round(total_income + total_spending, 2)

    return render_template('budgets/budgets.html', month_name=month_name[int(month)], year=year, month=month, budgets=budgets_list, cash_flow=cash_flow, total_income=total_income, total_spending=total_spending)


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