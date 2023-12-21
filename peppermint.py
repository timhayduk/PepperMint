from bson.objectid import ObjectId
from datetime import datetime
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
    accounts.update_one({'_id': account_id}, {'$set': {'balance': account['balance'] + transaction_amount}})


@app.route('/')
def index():
    return redirect(url_for('transactions'))


# @app.route('/<int:post_id>')
# def post(post_id):
#     post = get_post(post_id)
#     return render_template('post.html', post=post)


# @app.route('/create', methods=('GET', 'POST'))
# def create():
#     if request.method == 'POST':
#         id = request.form['_id']
#         title = request.form['title']
#         content = request.form['content']

#         if not title:
#             flash('Title is required!')
#         else:
#             db_connection = get_db_connection()
#             collection_name = db_connection['sandbox']
#             collection_name.insert_one({'_id': id, 'title': title, 'content': content, 'created': datetime.utcnow()})
#             return redirect(url_for('index'))
    
#     return render_template('create.html')


# @app.route('/<int:id>/edit', methods=('GET', 'POST'))
# def edit(id):
#     post = get_post(id)

#     if request.method == 'POST':
#         title = request.form['title']
#         content = request.form['content']

#         if not title:
#             flash('Title is required!')
#         else:
#             db_connection = get_db_connection()
#             collection_name = db_connection['sandbox']
#             collection_name.update_one({'_id': str(id)}, {'$set': {'title': title, 'content': content}})
#             return redirect(url_for('index'))

#     return render_template('edit.html', post=post)


# @app.route('/<int:id>/delete', methods=('POST',))
# def delete(id):
#     post = get_post(id)
    
#     db_connection = get_db_connection()
#     collection_name = db_connection['sandbox']
#     collection_name.delete_one({'_id': str(id)})

#     flash('"{}" was successfully deleted!'.format(post['title']))
#     return redirect(url_for('index'))


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
            'balance': request.form['balance'],
        })
        return redirect(url_for('accounts'))
    
    return  render_template('accounts/create_account.html')


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
            'description': request.form['description'],
            'amount': request.form['amount'],
            'date': request.form['date'],
        }

        rules = get_rules()
        for rule in rules:
            print(f"RULE: {rule}\nSEARCH: {search(rule['regex'], new_transaction['description'])}")
            if search(rule['regex'], new_transaction['description'], flags=IGNORECASE) is not None:
                new_transaction['category'] = rule['category']
                break

        transactions.insert_one(new_transaction)

        update_account_balance(ObjectId(new_transaction['account']), float(new_transaction['amount']))

        return redirect(url_for('transactions'))
    
    accounts = db_connection['accounts']
    accounts_list = list(accounts.find({}))
    return  render_template('transactions/create_transaction.html', accounts=accounts_list)


@app.route('/transactions/<string:id>/edit', methods=('GET', 'POST'))
def edit_transaction(id):
    db_connection = get_db_connection()
    transactions = db_connection['transactions']
    transaction = transactions.find_one({'_id': ObjectId(id)})

    if request.method == 'POST':
        transactions.update_one({'_id': transaction['_id']}, {
            '$set': {
                'account': request.form['account'],
                'description': request.form['description'],
                'amount': request.form['amount'],
                'date': request.form['date']
            }
        })
        return redirect(url_for('transactions'))
    
    return  render_template('transactions/edit_transaction.html', transaction=transaction)


@app.route('/transactions/<string:id>/delete')
def delete_transaction(id):
    db_connection = get_db_connection()
    transactions = db_connection['transactions']
    transaction = transactions.find_one({'_id': ObjectId(id)})
    transactions.delete_one({'_id': ObjectId(id)})

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
    return  render_template('rules/edit_rule.html', rule=rule, categories=categories_list)


@app.route('/rules/<string:id>/delete')
def delete_rule(id):
    db_connection = get_db_connection()
    rules = db_connection['rules']
    rule = rules.find_one({'_id': ObjectId(id)})
    rules.delete_one({'_id': ObjectId(id)})

    flash('"{}" was successfully deleted!'.format(rule['name']))
    return redirect(url_for('rules'))