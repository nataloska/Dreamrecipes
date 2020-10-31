import pymongo
import os
import base64

from flask import Flask, flash, render_template, request, redirect, url_for, session, send_from_directory
from pymongo import TEXT
from bson.objectid import ObjectId
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, PasswordField, TextAreaField
from wtforms.validators import Email, Length, InputRequired, DataRequired
from passlib.hash import sha256_crypt
from datetime import datetime
from werkzeug.utils import secure_filename
from werkzeug.datastructures import CombinedMultiDict, MultiDict, FileStorage

app = Flask(__name__)
app.config['SECRET_KEY'] = "123412341234123412341234123412341234"

MONGODB_URI = os.getenv("MONGO_URI")
DBS_NAME = "dreamrecipes"
USER_COLLECTION = "users"
RECIPE_COLLECTION = "recipe"

# Mongo
db = pymongo.MongoClient(MONGODB_URI)
users = db[DBS_NAME][USER_COLLECTION]
recipes = db[DBS_NAME][RECIPE_COLLECTION]
recipesearch = recipes.create_index([('ingredients', TEXT), 
                                    ('description', TEXT)])

class LoginForm(FlaskForm):
    email = StringField('email', validators=[InputRequired(), Email(message='Invalid email'), Length(max=30)])
    password = PasswordField('password', validators=[InputRequired(), Length(min=8)])

class PasswordForm(FlaskForm):
    oldpassword = PasswordField('oldpassword', validators=[InputRequired(), Length(min=8)])
    newpassword = PasswordField('newpassword', validators=[InputRequired(), Length(min=8)])

class NameForm(FlaskForm):
    newname = StringField('newname', validators=[InputRequired(), Length(max=30)])
    password = PasswordField('password', validators=[InputRequired(), Length(min=8)])

class PhoneForm(FlaskForm):
    phone = StringField('phone')
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
    photo = FileField('photo', validators=[FileRequired()])
    ingredients = StringField('ingredients')
    description = StringField('description')
    instructions = StringField('instructions')
    cTime = StringField('cTime')
    pTime = StringField('pTime')

# Flask
@app.route("/")
def index():
    searchform = SearchForm()
    recentrecipes = []
    recententries = recipes.find().sort('date' , pymongo.DESCENDING).limit(5)
    for entry in recententries:
        customername = users.find_one({'email' : entry['username']})['name']
        entry['customername'] = customername    
        newdate = datetime.date(entry['date'])
        entry['date'] = newdate
        recentrecipes.append(entry)
        
    return render_template("index.html", recentrecipes=recentrecipes, searchform=searchform)

@app.route("/search", methods=["POST"])
def search():
    searchform = SearchForm(request.form)   
    query = searchform.search.data
    if searchform:
        searchresult = recipes.find({"$text": {"$search" : query }})
        return render_template("search.html", searchform=searchform, searchresult=searchresult)
    
    return render_template("search.html", searchform=searchform, searchresult=None)

@app.route("/search/<string:category>")
def recipeingredient(category):
    searchform = SearchForm()
    searchresult = recipes.find({"$text": {"$search" : category }})
    return render_template("search.html", searchresult=searchresult, searchform=searchform)

@app.route("/recipe")
def recipe():
    homeresults = []
    homequery = recipes.find().sort('date' , pymongo.DESCENDING).limit(9)
    for result in homequery:       
        customername = users.find_one({'email' : result['username']})['name']
        result['customername'] = customername       
        newdate = datetime.date(result['date'])
        result['date'] = newdate
        homeresults.append(result)  
    return render_template("recipe.html", homeresults=homeresults)

@app.route("/recipe/<string:_id>")
def recipeitem(_id):
    currentrecipe = recipes.find_one({'_id': ObjectId(_id)})
    customername = users.find_one({'email' : currentrecipe['username']})['name']
    currentrecipe['customername'] = customername       
    newdate = datetime.date(currentrecipe['date'])
    currentrecipe['date'] = newdate
    return render_template("recipeitem.html", currentrecipe=currentrecipe)

@app.route("/newrecipe", methods=['POST', 'GET'])
def newrecipe(): 
    form = RecipeForm(CombinedMultiDict([request.files, request.form]))  
    if form.validate_on_submit():
        files_dir = os.path.join(
            os.path.dirname(app.instance_path), 'static'
        )
        p = form.photo.data
        filename = secure_filename(p.filename)
        p.save(os.path.join(files_dir, 'recipe', filename))
        currentuser = users.find_one({'email' : session['email']})
        if currentuser:
            recipes.insert_one({'username' : session['email'], 'recipename' : form.recipename.data,
                                'ingredients' : form.ingredients.data, 'description' : form.description.data,
                                'instructions' : form.instructions.data, 'cooktime' : form.cTime.data,
                                'preptime' : form.pTime.data, 'date' : datetime.now(), 'photo_path' : '/static/recipe/' + filename})
            return redirect(url_for('index'))
        return redirect(url_for('index'))
    return render_template("newrecipe.html", form=form)

@app.route("/settings")
def settings():
    return render_template("settings.html")

@app.route("/settingsemail", methods=['GET', 'POST'])
def settingsemail():
    form = LoginForm(request.form)
    if form.validate():
        currentuser = users.find_one({'email' : session['email']})
        isemailknown = users.find_one({'email' : form.email.data})
        if isemailknown == None:
            if sha256_crypt.verify(form.password.data, currentuser['password']):
                recipes.update_many({'username' : currentuser['email']}, 
                                    {"$set" : {'username' : form.email.data}}, upsert=False)
                users.update_one({'email' : session['email']}, 
                                {'$set': {'email' : form.email.data}}, upsert=False)
                session['email'] = None
                session['logged_in'] = False
                flash('email changed! Please log in again')
                return redirect(url_for('login'))
            flash('password incorrect')
            return redirect(url_for('settingsemail'))
        flash('email already known')
        return redirect(url_for('settingsemail'))
    return render_template("settingsemail.html", form=form)

@app.route("/settingspassword", methods=['GET', 'POST'])
def settingspassword():
    form = PasswordForm(request.form)
    if form.validate():
        currentuser = users.find_one({'email' : session['email']})
        if sha256_crypt.verify(form.oldpassword.data, currentuser['password']):
            updatedpassword = sha256_crypt.encrypt(form.newpassword.data)
            users.update_one({'password' : currentuser['password']}, 
                            {'$set': {'password' : updatedpassword}}, upsert=False)
            session['email'] = None
            session['logged_in'] = False
            flash('Password has been changed! Please log in again')
            return redirect(url_for('login'))
        flash('Password incorrect')
        return redirect(url_for('settingspassword'))
    return render_template("settingspassword.html", form=form)

@app.route("/settingsname", methods=['GET', 'POST'])
def settingsname():
    form = NameForm(request.form)
    if form.validate():
        currentuser = users.find_one({'email' : session['email']})
        if sha256_crypt.verify(form.password.data, currentuser['password']):
            users.update_one({'email' : session['email']}, 
                            {'$set': {'name' : form.newname.data}}, upsert=False)
            flash('Name has been changed!')
            return redirect(url_for('index'))  
        flash('Password incorrect')
        return redirect(url_for('settingsname'))               
    return render_template("settingsname.html", form=form)

@app.route("/settingsphone", methods=['GET', 'POST'])
def settingsphone():
    form = PhoneForm(request.form)
    if form.validate():
        currentuser = users.find_one({'email' : session['email']})
        if sha256_crypt.verify(form.password.data, currentuser['password']):
            users.update_one({'email' : session['email']}, 
                            {'$set': {'phone' : form.phone.data}}, upsert=False)
            flash('Phone number has been changed!')
            return redirect(url_for('index'))  
        flash('Password incorrect')
        return redirect(url_for('settingsphone')) 
    return render_template("settingsphone.html", form=form)

@app.route("/deletephone", methods=['GET', 'POST'])
def deletephone():
    form = PhoneForm(request.form)
    if form.validate():
        currentuser = users.find_one({'email' : session['email']})
        if sha256_crypt.verify(form.password.data, currentuser['password']):
            users.update_one({'email' : session['email']}, 
                            {'$unset': {'phone' : ''}}, upsert=False)
            flash('Phone number has been deleted!')
            return redirect(url_for('index')) 
    return render_template("settingsphone.html", form=form)

@app.route("/settingsrecipe")
def settingsrecipe():
    currentuser = users.find_one({'email' : session['email']})
    myrecipes = recipes.find({'username' : currentuser['email']})   
    return render_template("settingsrecipe.html", myrecipes=myrecipes)

@app.route("/settingsrecipe/<string:_id>")
def deleterecipe(_id):
    recipes.delete_one({'_id': ObjectId(_id)})
    currentuser = users.find_one({'email' : session['email']})
    myrecipes = recipes.find({'username' : currentuser['email']})
    flash('Recipe deleted!')
    return render_template("settingsrecipe.html", myrecipes=myrecipes)

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
            flash('Wrong password!')
        flash('There is no account under this email, please sign up!')
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
        flash('email already known, please sign in')
        return redirect(url_for('register'))

    return render_template('register.html', form=form)
    
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('index')) 

if __name__ == "__main__":
    app.config['MAX_CONTENT_LENGTH'] = 2* 1024 * 1024 
    app.run(host=os.environ.get("IP"),
            port=int(os.environ.get("PORT")),
            debug=True)