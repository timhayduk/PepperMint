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
    print(f"ID: {post_id}")
    post = collection_name.find_one({"_id": str(post_id)})
    print(f"POST: {post}")
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
    print(f"POSTS: {posts}")
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
            print(f"FORM: {request.form}")
            collection_name.insert_one({'_id': id, 'title': title, 'content': content, 'created': datetime.utcnow()})
            return redirect(url_for('index'))
    
    return render_template('create.html')

