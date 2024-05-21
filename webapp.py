from flask import Flask, redirect, url_for, session, request, jsonify, render_template, flash
from markupsafe import Markup
from flask_apscheduler import APScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from flask_oauthlib.client import OAuth
from bson.objectid import ObjectId
from flask_socketio import SocketIO, send, emit
from bson.objectid import ObjectId



import pprint
import os
import time
import pymongo
import sys
import datetime
 
app = Flask(__name__)

app.debug = True #Change this to False for production
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1' #Remove once done debugging

app.secret_key = os.environ['SECRET_KEY'] #used to sign session cookies
oauth = OAuth(app)
oauth.init_app(app) #initialize the app to be able to make requests for user information
socketio = SocketIO(app)

#Set up GitHub as OAuth provider
github = oauth.remote_app(
    'github',
    consumer_key=os.environ['GITHUB_CLIENT_ID'], #your web app's "username" for github's OAuth
    consumer_secret=os.environ['GITHUB_CLIENT_SECRET'],#your web app's "password" for github's OAuth
    request_token_params={'scope': 'user:email'}, #request read-only access to the user's email.  For a list of possible scopes, see developer.github.com/apps/building-oauth-apps/scopes-for-oauth-apps
    base_url='https://api.github.com/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://github.com/login/oauth/access_token',  
    authorize_url='https://github.com/login/oauth/authorize' #URL for github's OAuth login
)

#Connect to database
url = os.environ["MONGO_CONNECTION_STRING"]
client = pymongo.MongoClient(url)
db = client[os.environ["MONGO_DBNAME"]]
posts = db['posts']
characters = db['Characters']
messages = db['messages']
# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

#context processors run before templates are rendered and add variable(s) to the template's context
#context processors must return a dictionary 
#this context processor adds the variable logged_in to the conext for all templates
@app.context_processor
def inject_logged_in():
    return {"logged_in":('github_token' in session)}

@app.route('/')
def home():
    #session.clear()
    return render_template('home.html')

#redirect to GitHub's OAuth page and confirm callback URL
@app.route('/login')
def login():   
    return github.authorize(callback=url_for('authorized', _external=True, _scheme='http')) #callback URL must match the pre-configured callback URL

@app.route('/logout')
def logout():
    #if 'character_data' in session:
        #clearCookies()
    #else:
    session.clear()
    flash('You were logged out.')
    return redirect('/')

@app.route('/login/authorized')
def authorized():
    resp = github.authorized_response()
    if resp is None:
        session.clear()
        message=''
        flash('Access denied: reason=' + request.args['error'] + ' error=' + request.args['error_description'] + ' full=' + pprint.pformat(request.args), 'error')      
    else:
        try:
            session['github_token'] = (resp['access_token'], '') #save the token to prove that the user logged in
            session['user_data']=github.get('user').data
            message = 'You were successfully logged in as ' + session['user_data']['login'] + '.'
        except Exception as inst:
            session.clear()
            print(inst)
            message = 'Unable to login, please try again.', 'error'
    return render_template('message.html', message=message)


@app.route('/page1')
def renderPage1():
    if 'user_data' in session:
        user_data_pprint = pprint.pformat(session['user_data'])#format the user data nicely
    else:
        user_data_pprint = '';
    return render_template('page1.html',dump_user_data=user_data_pprint)



@app.route('/page2')
def renderPage2():
    message = getMessages()
    print(message)
    return render_template('page2.html', message_display=message)
    
    
def getMessages():
    message = ""
    
    for doc in messages.find():
        message = message + Markup("<li>" + "<p>" + str(doc["Body"]) + "</p>" + "</li>")   
    
    print(message)
    return(message)    
    
@app.route('/Submit',methods=['GET','POST'])
def submitMessage():
    message = request.form['messageBody']
    updateMessages(message)
    socketio.emit('message', message)
    remove_old_messages()
    return redirect('/page2')
    
def updateMessages(message):
    
    doc = {
        "Body": message
    }
    messages.insert_one(doc)

def remove_old_messages():
    numberofmessages = 0
    for doc in messages.find():
        numberofmessages += 1
    if numberofmessages > 5:
        messages.delete_one({})
    
    
@socketio.on('text')
def text(data):
    socketio.emit('message', data)
  
@app.route('/Summary',methods=['GET','POST'])
def renderSummaryPage():
    sumInput = getPosts()
    print(sumInput)
    return render_template('summary.html', sum_Input=sumInput)
   
def getPosts():
    sumInput = ""
    
    for doc in posts.find():
        sumInput = sumInput + Markup("<li>" + "<h3>" + str(doc["Head"]) + "</h3>" + "<p>" + str(doc["Body"]) + "</p>" + "</li>")   
    
    print(sumInput)
    return(sumInput)

@app.route('/SummaryInput',methods=['GET','POST'])
def renderSummaryInputPage():
    return render_template('summaryInput.html')
    
@app.route('/Submit',methods=['GET','POST'])
def submitSummeryInput():
    sumInput = request.form['bodyInput']
    headInput = request.form['headInput']
    updateSummary = updateSummary(headInput, sumInput)
    return redirect('/Summary')



def updateSummary(head, body):
    doc = {
        "Head": head,
        "Body": body
    }
    posts.insert_one(doc)
    sumUpdate = doc
    return(sumUpdate)

#the tokengetter is automatically called to check who is logged in.
@github.tokengetter
def get_github_oauth_token():
    return session['github_token']

@app.route('/Account')
def renderAccountPage():
    if 'user_data' in session:
        
        gitHubID = session['user_data']['login']
        
        if characters.find_one({"GitHubID": gitHubID}):
            gitHubID = session['user_data']['login']
            characterData=loadCharacterData(gitHubID)
            return render_template('account.html',character_data=characterData)
        else:
            return render_template('account.html')
    else:
        message = 'Please Log in.'
        return render_template('message.html', message=message)

@app.route('/createAccount', methods=['GET', 'POST'])
def renderAccountCreation():
    gitHubID = session['user_data']['login']
    Name=request.form['name']
    Class=request.form['class']
    Level=request.form['level']
    
    characterData=createCharacterData(gitHubID, Name, Class, Level)
    
    return render_template('account.html',character_data=characterData) 
   
@app.route('/updateCharacter', methods=['GET', 'POST'])
def renderUpdateCharacter():  
    gitHubID = session['user_data']['login']
    Level=request.form['level']
    characterData=editCharacter(gitHubID, Level)
    
    return redirect('/Account')

def createCharacterData(gitHubID, Name, Class, Level):
    doc = {
        "GitHubID": gitHubID,
        "Name": Name,
        "Class": Class,
        "Level": Level
    }
    characters.insert_one(doc)
    characterData = doc
    return(characterData)
    
def loadCharacterData(gitHubID):
    characterData = characters.find_one({"GitHubID": gitHubID})
    return(characterData)
    
def editCharacter(gitHubID, Level):
    query = characters.find_one({"GitHubID": gitHubID})
    changes = {'$set': {"Level":Level}}
    characters.update_one(query, changes)

    characterData = query
    return(characterData)
if __name__ == '__main__':
    socketio.run(app)
