import pymongo
import os
import gridfs

from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from pymongo import TEXT
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from wtforms import StringField, PasswordField, TextAreaField
from wtforms.validators import Email, Length, InputRequired, DataRequired
from passlib.hash import sha256_crypt
from datetime import datetime
from werkzeug.datastructures import CombinedMultiDict, MultiDict

app = Flask(__name__)

MONGODB_URI = os.getenv("MONGO_URI")
DBS_NAME = "dreamrecipes"
USER_COLLECTION = "users"
RECIPE_COLLECTION = "recipe"

# Mongo
db = pymongo.MongoClient(MONGODB_URI)
users = db[DBS_NAME][USER_COLLECTION]
recipes = db[DBS_NAME][RECIPE_COLLECTION]
recphoto = db[DBS_NAME]
fs = gridfs.GridFS(recphoto)
recipesearch = recipes.create_index([('description',TEXT)],default_language="english")

class LoginForm(FlaskForm):
    email = StringField('email', validators=[InputRequired(), Email(message='Invalid email'), Length(max=30)])
    password = PasswordField('password', validators=[InputRequired(), Length(min=8)])

class RegForm(FlaskForm):
    name = StringField('name', validators=[InputRequired(), Length(max=30)])
    email = StringField('email', validators=[InputRequired(), Email(message='Invalid email'), Length(max=30)])
    password = PasswordField('password', validators=[InputRequired(), Length(min=8)])
    phone = StringField('phone')

class SearchForm(FlaskForm):
    search = StringField('search', validators=[InputRequired(), Length(max=30)])

class RecipeForm(FlaskForm):
    recipename = StringField('recipename', validators=[InputRequired(), Length(max=30)])
    photo = FileField('photo')
    ingredients = StringField('ingredients')
    description = StringField('description')
    instructions = StringField('instructions')
    cTime = StringField('cTime')
    pTime = StringField('pTime')


# Flask
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/search", methods=["POST"])
def search():
    form = SearchForm(request.form)
    query = form.data['search']
    if query:
        searchresult = recipesearch.find({"$text": {"$search": query}}).limit(10)
        return render_template("search.html", form=form, query=query, searchresult=searchresult)
    
    return render_template("search.html", form=form, query=query, searchresult=None)

@app.route("/recipe")
def recipe():
    homeresults = recipes.find().limit(9).sort('date',pymongo.DESCENDING)
    return render_template("recipe.html", homeresults=homeresults)

@app.route("/newrecipe", methods=['POST'])
def newrecipe(): 
    form = RecipeForm(CombinedMultiDict([request.files, request.form]))
    print('validatefail')
    if form.validate():
        print('validatesuccess')
        currentuser = users.find_one({'email' : session['email']})
        if currentuser:
            recipes.insert_one({'username' : session['email'], 'recipename' : form.recipename.data,
                                'ingredients' : form.ingredients.data, 'description' : form.description.data,
                                'instructions' : form.instructions.data, 'cooktime' : form.cTime.data,
                                'preptime' : form.pTime.data, 'date' : datetime.now()})
            recipe_id = recipes.find_one({'username' : session['email'], 'recipename' : form.recipename.data})['_id']
            try: 
                with open(form.phone.data, 'rb') as blob:
                    fs.put(blob, recipe_id = recipe_id)
                    return redirect(url_for('index'))
            except EnvironmentError:
                print('No photo to upload')
            
    return render_template("newrecipe.html", form=form)

@app.route("/settings")
def settings():
    return render_template("settings.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm(request.form)
    if form.validate():
        user_exist = users.find_one({'email': form.email.data})
        if user_exist:
            if sha256_crypt.verify(form.password.data, user_exist['password']):
                session['email'] = form.email.data
                session['logged_in'] = True
                return redirect(url_for('index'))

    return render_template('login.html', form=form)
  
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegForm(request.form)
    if form.validate():
        existing_user = users.find_one({'email' : form.email.data})
        if existing_user is None:
            hashpass = sha256_crypt.encrypt(form.password.data)
            users.insert_one({'name' : form.name.data, 'email' : form.email.data, 'password' : hashpass, 'phone' : form.phone.data})
            session['logged_in'] = True
            session['email'] = form.email.data       
            return redirect(url_for('index'))
        
        return 'That username already exists!'

    return render_template('register.html', form=form)
    
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('index')) 

if __name__ == "__main__":
    app.secret_key = '12346894741389410'
    app.config['MAX_CONTENT_LENGTH'] = 2* 1024 * 1024    
    app.run(host=os.environ.get("IP"),
            port=int(os.environ.get("PORT")),
            debug=True)