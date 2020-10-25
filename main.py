import pymongo
import os
import json
import werkzeug

from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from pymongo import TEXT
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from wtforms import StringField, PasswordField
from wtforms.validators import Email, Length, InputRequired, DataRequired
from passlib.hash import sha256_crypt

app = Flask(__name__)

MONGODB_URI = os.getenv("MONGO_URI")
DBS_NAME = "dreamrecipes"
USER_COLLECTION = "users"
RECIPE_COLLECTION = "recipe"

# Mongo
db = pymongo.MongoClient(MONGODB_URI)
users = db[DBS_NAME][USER_COLLECTION]
recipes = db[DBS_NAME][RECIPE_COLLECTION]
recipesearch = recipes.create_index([('description',TEXT)],default_language ="english")

class RegForm(FlaskForm):
    name = StringField('name', validators=[InputRequired(), Length(max=30)])
    email = StringField('email', validators=[InputRequired(), Email(message='Invalid email'), Length(max=30)])
    password = PasswordField('password', validators=[InputRequired(), Length(min=8)])
    phone = StringField('phone')

class SearchForm(FlaskForm):
    search = StringField('search', validators=[DataRequired()])

# Flask
# @app.route("/")
# def index():
#     return render_template("index.html")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/search", methods=["POST"])
def search():
    form = SearchForm()
    query = form.data['search']
    if query:
        searchresult = recipesearch.find({"$text": {"$search": query}}).limit(10)
        return render_template("search.html", form=form, query=query, searchresult=searchresult)
    
    return render_template("search.html", form=form, query=query, searchresult=None)

@app.route("/recipe")
def recipe():
    homeresults = recipes.find().limit(9).sort('date',pymongo.DESCENDING)      
    return render_template("recipe.html", homeresults=homeresults)

@app.route("/settings")
def settings():
    return render_template("settings.html")


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = RegForm()
    if form.validate():
        login_user = users.find_one({'email': form.email.data})
        if login_user:
            if sha256_crypt.verify(form.password.data, login_user['password']):
                session['name'] = form.name.data
                session['logged_in'] = True
                return redirect(url_for('index'))



    return render_template('login.html', form=form)
  
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegForm()
    if form.validate():
        existing_user = users.find_one({'email' : form.email.data})
        if existing_user is None:
            hashpass = sha256_crypt.encrypt(form.password.data)
            users.insert_one({'name' : form.name.data, 'email' : form.email.data, 'password' : hashpass, 'phone' : form.phone.data})
            session['name'] = form.name.data
            session['logged_in'] = True
            return redirect(url_for('index'))
        
        return 'That username already exists!'

    return render_template('register.html', form=form)
    
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('index')) 

if __name__ == "__main__":
    app.secret_key = 'extrasecret'
    app.run(host=os.environ.get("IP"),
            port=int(os.environ.get("PORT")),
            debug=True)