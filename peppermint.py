from bson.objectid import ObjectId
from datetime import datetime
from flask import Flask, render_template, request, url_for, flash, redirect
from pymongo import MongoClient
from werkzeug.exceptions import abort


def get_db_connection(): 
   # Provide the mongodb atlas url to connect python to mongodb using pymongo
   CONNECTION_STRING = "mongodb://localhost:27017"
 
   # Create a connection using MongoClient. You can import MongoClient or use pymongo.MongoClient
   client = MongoClient(CONNECTION_STRING)

   return client['peppermint']


def get_post(post_id):
    db_connection = get_db_connection()
    collection_name = db_connection['sandbox']
    post = collection_name.find_one({"_id": str(post_id)})
    if post is None:
        abort(404)
    return post


app = Flask(__name__)
app.config['SECRET_KEY'] = 'abcd1234'


@app.route('/')
def index():
    db_connection = get_db_connection()
    collection_name = db_connection['sandbox']
    posts = list(collection_name.find())
    return render_template('index.html', posts=posts)


@app.route('/<int:post_id>')
def post(post_id):
    post = get_post(post_id)
    return render_template('post.html', post=post)


@app.route('/create', methods=('GET', 'POST'))
def create():
    if request.method == 'POST':
        id = request.form['_id']
        title = request.form['title']
        content = request.form['content']

        if not title:
            flash('Title is required!')
        else:
            db_connection = get_db_connection()
            collection_name = db_connection['sandbox']
            collection_name.insert_one({'_id': id, 'title': title, 'content': content, 'created': datetime.utcnow()})
            return redirect(url_for('index'))
    
    return render_template('create.html')


@app.route('/<int:id>/edit', methods=('GET', 'POST'))
def edit(id):
    post = get_post(id)

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']

        if not title:
            flash('Title is required!')
        else:
            db_connection = get_db_connection()
            collection_name = db_connection['sandbox']
            collection_name.update_one({'_id': str(id)}, {'$set': {'title': title, 'content': content}})
            return redirect(url_for('index'))

    return render_template('edit.html', post=post)


@app.route('/<int:id>/delete', methods=('POST',))
def delete(id):
    post = get_post(id)
    
    db_connection = get_db_connection()
    collection_name = db_connection['sandbox']
    collection_name.delete_one({'_id': str(id)})

    flash('"{}" was successfully deleted!'.format(post['title']))
    return redirect(url_for('index'))


@app.route('/transactions')
def transactions():
    db_connection = get_db_connection()
    transactions = db_connection['transactions']
    transactions_list = list(transactions.find({}))
    return render_template('transactions.html', transactions=transactions_list)


@app.route('/transactions/<string:id>/edit', methods=('GET', 'POST'))
def edit_transaction(id):
    db_connection = get_db_connection()
    transactions = db_connection['transactions']
    transaction = transactions.find_one({'_id': ObjectId(id)})

    if request.method == 'POST':
        print(f"DATE: {request.form['date']}")
        transactions.update_one({'_id': transaction['_id']}, {
            '$set': {
                'account': request.form['account'],
                'description': request.form['description'],
                'amount': request.form['amount'],
                'date': request.form['date']
            }
        })
        return redirect(url_for('transactions'))
    
    return  render_template('edit_transaction.html', transaction=transaction)


@app.route('/transactions/<string:id>/delete')
def delete_transaction(id):
    db_connection = get_db_connection()
    transactions = db_connection['transactions']
    transaction = transactions.find_one({'_id': ObjectId(id)})
    transactions.delete_one({'_id': ObjectId(id)})

    flash('"{} - {}" was successfully deleted!'.format(transaction['account'], transaction['description']))
    return redirect(url_for('transactions'))


@app.route('/accounts')
def accounts():
    db_connection = get_db_connection()
    accounts = db_connection['accounts']
    accounts_list = list(accounts.find({}).sort({'name': 1}))
    return render_template('accounts.html', accounts=accounts_list)


@app.route('/accounts/<string:id>/delete')
def delete_account(id):
    db_connection = get_db_connection()
    accounts = db_connection['accounts']
    account = accounts.find_one({'_id': ObjectId(id)})
    accounts.delete_one({'_id': ObjectId(id)})

    flash('"{}" was successfully deleted!'.format(account['name']))
    return redirect(url_for('accounts'))
