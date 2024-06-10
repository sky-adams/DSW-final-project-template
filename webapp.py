from flask import Flask, redirect, url_for, session, request, jsonify, render_template, flash, Response
from markupsafe import Markup
from flask_apscheduler import APScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from flask_oauthlib.client import OAuth
from bson.objectid import ObjectId
from flask_socketio import SocketIO, send, emit, join_room, leave_room
from bson.objectid import ObjectId
from flask_pymongo import PyMongo
#TODO Check why log out check is not working and why submitting when logged out on summary adds a message

import pprint
import os
import time
import pymongo
import gridfs
import sys
import datetime
import codecs
 
app = Flask(__name__)

app.debug = True #Change this to False for production
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1' #Remove once done debugging

app.config['MONGO_URI'] = os.environ['MONGO_URI']

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

#Test from StackOverflow
#imageDBConnect = client.Images

db = client[os.environ["MONGO_DBNAME"]]
ImagesDB = client[os.environ["MONGO_DBIMAGES"]]
posts = db['posts']
characters = db['Characters']
partys = db['Partys']
messages = db['messages']

# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)


mongo = PyMongo(app)
imagesFS = gridfs.GridFS(mongo.db)
#context processors run before templates are rendered and add variable(s) to the template's context
#context processors must return a dictionary 
#this context processor adds the variable logged_in to the conext for all templates
@app.context_processor
def inject_logged_in():
    return {"logged_in":('github_token' in session)}

@app.route('/')
def home():
    if 'user_data' in session:
        gitHubID = session['user_data']['login']
        #TODO make it so you can leave a party
        if characters.find_one({"GitHubID":gitHubID}):
            currentParty = loadCharacterData(gitHubID)["CurrentParty"]
            if currentParty != None:
                recentEvents = getPosts(currentParty)
                return render_template('home.html', recent_events=recentEvents, current_Party=currentParty)
            else:
                message = 'Please Join a Party.'
                return render_template('message.html', message=message)
        else:
            message= 'Please make an account.'
            return render_template('message.html', message=message)
    else:
        userData = None
        print(userData)
        return render_template('home.html', user_Data=userData)

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
    print('Loged out')
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

@app.route('/page2')
def renderPage2():
    if 'user_data' in session:
        gitHubID = session['user_data']['login']
        if characters.find_one({"GitHubID":gitHubID}):
            currentParty = loadCharacterData(gitHubID)["CurrentParty"]
            if currentParty != None:
                message = getMessages(currentParty)
                print(message)
                return render_template('page2.html', message_display=message)
            else:
                message = 'Please Join a Party.'
                return render_template('message.html', message=message)
        else:
            message= 'Please make an account.'
            return render_template('message.html', message=message)
    else:
        message = 'Please Log in.'
        return render_template('message.html', message=message)
    
def getMessages(current_Party):
    message = ""
    
    for doc in messages.find({"PartyTag": current_Party}):
        message = message + Markup("<li>" + "<p>" + str(doc["Username"]) + ": " + str(doc["Body"]) + "</p>" + "</li>")   
    
    print(message)
    return(message)    
    
@app.route('/SubmitMessage',methods=['GET','POST'])
def submitMessage():
    #Used for checking party
    gitHubID = session['user_data']['login']
    PartyTag = loadCharacterData(gitHubID)["CurrentParty"]
    
    message = request.form['messageBody']
    updateMessages(message, PartyTag, gitHubID)
    username = gitHubID
    socketio.emit('message', "<b>" + username + "</b>" + ": " + message, to=PartyTag)
    remove_old_messages(PartyTag)
    
    return redirect('/page2')
    
def updateMessages(message, partyTag, username):
    
    doc = {
        "Username": username,
        "Body": message,
        "PartyTag": partyTag
    }
    messages.insert_one(doc)

def remove_old_messages(partyTag):
    numberofmessages = 0
    for doc in messages.find({"PartyTag": partyTag}):
        numberofmessages += 1
    if numberofmessages > 5:
        messages.delete_one({"PartyTag": partyTag})
  
@socketio.on('join')
def on_join(data):
    username = session['user_data']['login']
    room = loadCharacterData(username)["CurrentParty"]
    join_room(room)
    #send(username + ' has entered the room.', to=room)
    #print("Joined Room")
  
@app.route('/Summary',methods=['GET','POST'])
def renderSummaryPage():
    if 'user_data' in session:
        gitHubID = session['user_data']['login']
        if characters.find_one({"GitHubID":gitHubID}):
            currentParty = loadCharacterData(gitHubID)["CurrentParty"]
            if currentParty != None:
                sumInput = getPosts(currentParty)
                isDM = loadCharacterData(gitHubID)["DMaster"]
                return render_template('summary.html', sum_Input=sumInput,is_DM=isDM, current_party=currentParty)
            else:
                message = 'Please Join a Party.'
                return render_template('message.html', message=message)
        else:
            message= 'Please make an account.'
            return render_template('message.html', message=message)
    else:
        message = 'Please Log in.'
        return render_template('message.html', message=message)
   
def getPosts(current_Party):
    sumInput = ""
    
    for doc in posts.find({"PartyTag": current_Party}):
        sumInput = Markup("<li>" + "<h5>" + str(doc["Head"]) + "</h5>" + "<p>" + str(doc["Body"]) + "</p>" + "</li>") + sumInput   
    
    print(sumInput)
    return(sumInput)

@app.route('/SummaryInput',methods=['GET','POST'])
def renderSummaryInputPage():

    return render_template('summaryInput.html')
    
@app.route('/Submit',methods=['GET','POST'])
def submitSummeryInput():
    sumInput = request.form['bodyInput']
    headInput = request.form['headInput']
    gitHubID = session['user_data']['login']
    PartyTag = loadCharacterData(gitHubID)["CurrentParty"]
    updateSummary(headInput, sumInput, PartyTag)
    return redirect('/Summary')



def updateSummary(head, body, partyTag):
    doc = {
        "Head": head,
        "Body": body,
        "PartyTag": partyTag
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
            isDM = loadCharacterData(gitHubID)["DMaster"]
            print(isDM)
            characterData=loadCharacterData(gitHubID)
            currentParty = loadCharacterData(gitHubID)["CurrentParty"]
            return render_template('account.html',character_data=characterData, current_party=currentParty, is_DM=isDM)
        else:
            return render_template('account.html')
    else:
        message = 'Please Log in.'
        return render_template('message.html', message=message)

@app.route('/createAccount', methods=['GET', 'POST'])
def renderAccountCreation():
    gitHubID = session['user_data']['login']
    Name=request.form['name']
    Race=request.form['race']
    Class=request.form['class']

    Strength=request.form['strength']
    Dexterity=request.form['dexterity']
    Constitution=request.form['constitution']
    Intelligence=request.form['intelligence']
    Wisdom=request.form['wisdom']
    Charisma=request.form['charisma']

    Level=0
    isDM = False
    Party = None
        
    characterData=createCharacterData(gitHubID, Name, Race, Class, Strength, Dexterity, Constitution, Intelligence, Wisdom, Charisma ,Level, isDM, Party)
   
    return render_template('account.html',character_data=characterData, current_party=None, is_DM=isDM)

@app.route('/createParty', methods=['GET', 'POST'])
def renderCreateParty(): 
    return render_template('createParty.html') 

@app.route('/JoinParty', methods=['GET', 'POST'])
def renderPartySelection(): 
    partys = getPartys()
    Error = ""
    return render_template('partySelect.html', party_List=partys, message=Error)

@app.route('/leaveParty', methods=['GET', 'POST'])
def leaveParty():
    gitHubID = session['user_data']['login']
    currentParty = None
    editCharacter(gitHubID, "CurrentParty", currentParty)
    return redirect('/Account')
    
@app.route('/DeleteParty', methods=['GET', 'POST'])
def DeleteParty():
    gitHubID = session['user_data']['login']    
   
    partyToDelete = loadCharacterData(gitHubID)["CurrentParty"]

    #Deletes The Party From Mongo
    deleteParty(partyToDelete)

    #Deletes all Data associated with deleted party on Mongo
    #Messages
    MessagesKey = "PartyTag"
    MassDeleteDoc(partyToDelete, messages, MessagesKey)
    #Summary
    SummaryKey = "PartyTag"
    MassDeleteDoc(partyToDelete, posts, SummaryKey)
    #Images
    deleteGridFSImage(partyToDelete)
    #Sets all party members current party to none.
    MassChangeCharacters("CurrentParty", partyToDelete)
    
    #Sets DM's current party to none
    currentParty = None
    editCharacter(gitHubID, "CurrentParty", currentParty)
    
  
    return redirect('/Account')
    
def deleteGridFSImage(Party):
    doc = imagesFS.find_one({"party": Party})
    if doc:   
        fileDelete = imagesFS.get(doc._id)
        imagesFS.delete(doc._id)

def deleteParty(Party):
    print(Party)
    PartyToDelete = { "Name": Party }
    partys.delete_one(PartyToDelete)

def MassChangeCharacters(Key, Value):
    changes = {'$set': {Key:None}}
    characters.update_many({Key : Value}, changes)

def MassDeleteDoc(Party, DB, Key):
    query = {Key: Party}

    DeletedDocs = DB.delete_many(query)

    print(DeletedDocs.deleted_count, " documents deleted.")

    
    
@app.route('/PartyConnect', methods=['GET', 'POST'])
def renderPartyConnect(): 
    #Used for redirects
    partysList = getPartys()
    
    gitHubID = session['user_data']['login']
    SelName=request.form['PartyName']
    SelPassword=request.form['Password']
    
    Key = "CurrentParty"
    
    doc = partys.find_one({"Name": SelName})
    
    
    if doc == None:
        Error = "Name Incorrect"
        return render_template('partySelect.html', party_List=partysList, message=Error)
    
    if doc["Name"] == loadCharacterData(gitHubID)["CurrentParty"]:
        Error = "Already In Party."
        return render_template('partySelect.html', party_List=partysList, message=Error)
    
    if SelPassword == doc["Password"]:
        editCharacter(gitHubID, Key, SelName)
        isDM = False
        editCharacter(gitHubID, "DMaster", isDM)
        return redirect('/Account')
    else:
        Error = "Password Incorrect"
        return render_template('partySelect.html', party_List=partysList, message=Error)
    
   #editCharacter(gitHubID)
    return redirect('/Account')

def getPartys():
    partyList = ""
    for doc in partys.find():
        partyList = partyList + Markup("<li>" + "<h3>" + str(doc["Name"]) + "</h3>" + "</li>")
    
    return(partyList)
@app.route('/SubmitParty', methods=['GET', 'POST'])
def submitPartyInput(): 
    gitHubID = session['user_data']['login']
    PName = request.form['PartyName']
    Password = request.form['Password']
    CurrentParty = "CurrentParty"
    
    partyList = []
    
    for doc in partys.find():
        partyList.append(doc["Name"])
        
    print(partyList)
    
    if PName in partyList:
        message = 'Party name already in use, please choose a different name.'
        return render_template('message.html', message=message)
    else:
        createparty = createParty(PName, Password)
        #Sets character party to new party.
       
        editCharacter(gitHubID, CurrentParty, PName) 
        isDM = True
        editCharacter(gitHubID, "DMaster", isDM)
    return redirect('/Account')    
   
def createParty(name, password):
    doc = {
        "Name": name,
        "Password": password,
    }
    partys.insert_one(doc)
    currentParty = doc
    return(currentParty)
   
   
@app.route('/updateCharacter', methods=['GET', 'POST'])
def renderUpdateCharacter():  
    gitHubID = session['user_data']['login']
    newLevel=request.form['level']
    Key = "Level"
    characterData=editCharacter(gitHubID, Key,newLevel)
    
    return redirect('/Account')

def createCharacterData(gitHubID, Name, Race, Class, Strength, Dexterity, Constitution, Intelligence, Wisdom, Charisma ,Level, isDM, Party):
    doc = {
        "GitHubID": gitHubID,
        "Name": Name,
        "Race": Race,
        "Class": Class,
        "Strength": Strength,
        "Dexterity": Dexterity,
        "Constitution": Constitution,
        "Intelligence": Intelligence,
        "Wisdom": Wisdom,
        "Charisma": Charisma,
        "Level": Level,
        "DMaster": isDM,
        "CurrentParty": Party
    }
    characters.insert_one(doc)
    characterData = doc
    print("CREATED A CHARACTER!!!")
    return(characterData)
    
def loadCharacterData(gitHubID):
    characterData = characters.find_one({"GitHubID": gitHubID})
    return(characterData)
    
def editCharacter(gitHubID, Key, Value):
    query = characters.find_one({"GitHubID": gitHubID})
    changes = {'$set': {Key:Value}}
    characters.update_one(query, changes)

    characterData = query
    return(characterData)

@app.route('/page1')
def renderPage1():
    if 'user_data' in session:
        gitHubID = session['user_data']['login']
        if characters.find_one({"GitHubID":gitHubID}):
            currentParty = loadCharacterData(gitHubID)["CurrentParty"]
            if currentParty != None:
                isDM = loadCharacterData(gitHubID)["DMaster"]
                return render_template('page1.html', current_Party=currentParty, is_dm=isDM)
            else:
                message = 'Please Join a Party.'
                return render_template('message.html', message=message)
        else:
            message= 'Please make an account.'
            return render_template('message.html', message=message)
    else:
       message = 'Please Log in.'
       return render_template('message.html', message=message)


@app.route('/uploadMapImage', methods=['GET', 'POST'])
def uploadMap():  
    if request.method == 'POST':
        if request.files:
            gitHubID = session['user_data']['login']
            currentParty = loadCharacterData(gitHubID)["CurrentParty"]
            file = request.files["image"]
            image = request.files["image"].read()
            imageName = file.filename
            print("Submitted Image")
            
            uploadImage(image, imageName, currentParty)
            
            print(image)
            
            return redirect(request.url)
        else:
            print("Did not submit image")
            
            return redirect(request.url)
                   
    return redirect("/page1")  
    
@app.route('/file/<partyTag>')
def file(partyTag):
    doc = imagesFS.find_one({"party": partyTag})
    if doc:
        file_data = imagesFS.get(doc._id)
        if file_data:
            return Response(file_data, mimetype=file_data.content_type, direct_passthrough=True)
        else:
            error = "Did not find file."
            print(error)
            return(error)
    else:
        error = "Did not find any doc."
        print(error)
        return(error)
    


def uploadImage(image, imageName, partyTag):
    doc = imagesFS.find_one({"party": partyTag})
    if doc:   
        fileDelete = imagesFS.get(doc._id)
        imagesFS.delete(doc._id)
        imagesFS.put(image, filename=imageName, party=partyTag)
    else:
        imagesFS.put(image, filename=imageName, party=partyTag)
#https://www.youtube.com/watch?v=6WruncSoCdI
if __name__ == '__main__':
    socketio.run(app)
