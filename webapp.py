import os
from flask import Flask, url_for, render_template, request
from flask import redirect
from flask import session
from flask_oauthlib.client import OAuth

app = Flask(__name__)

# In order to use "sessions",you need a "secret key".
# This is something random you generate.  
# For more info see: https://flask.palletsprojects.com/en/1.1.x/config/#SECRET_KEY


app.debug = False #Change this to False for production
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1' #Remove once done debugging

app.secret_key = os.environ['SECRET_KEY'] #used to sign session cookies
oauth = OAuth(app)
oauth.init_app(app) #initialize the app to be able to make requests for user information

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

#context processors run before templates are rendered and add variable(s) to the template's context
#context processors must return a dictionary 
#this context processor adds the variable logged_in to the conext for all templates

@app.context_processor
def inject_logged_in():
    is_logged_in = 'github_token' in session #this will be true if the token is in the session and false otherwise
    return {"logged_in":is_logged_in}

@app.route('/')
def home():
    return render_template('home.html')

#redirect to GitHub's OAuth page and confirm callback URL
@app.route('/login')
def login():   
    return github.authorize(callback=url_for('authorized', _external=True, _scheme='http')) #callback URL must match the pre-configured callback URL

@app.route('/logout')
def logout():
    session.clear()
    return render_template('message.html', message='You were logged out')

@app.route('/login/authorized')
def authorized():
    resp = github.authorized_response()
    if resp is None:
        session.clear()
        message = 'Access denied: reason=' + request.args['error'] + ' error=' + request.args['error_description'] + ' full=' + pprint.pformat(request.args)      
    else:
        try:
            session['github_token'] = (resp['access_token'], '') #save the token to prove that the user logged in
            session['user_data']=github.get('user').data
            #pprint.pprint(vars(github['/email']))
            #pprint.pprint(vars(github['api/2/accounts/profile/']))
            message='You were successfully logged in as ' + session['user_data']['login'] + '.'
        except Exception as inst:
            session.clear()
            print(inst)
            message='Unable to login, please try again.  '
    return render_template('message.html', message=message)

app.secret_key=os.environ["SECRET_KEY"]; #This is an environment variable.  
                                     #The value should be set on the server. 
                                     #To run locally, set in env.bat (env.sh on Macs) and include that file in gitignore so the secret key is not made public.
  
@app.route('/startOver')
def startOver():
    session.clear() #clears variable values and creates a new session
    return redirect(url_for('renderMain')) # url_for('renderMain') could be replaced with '/'

@app.route('/page1')
def renderPage1():
    return render_template('page1.html')
    
@app.route('/form2page1')
def renderForm2Page1():
    return render_template('page1.html')
    
@app.route('/page2',methods=['GET','POST'])
def renderPage2():
    return render_template('page2.html')

@app.route('/form2page2',methods=['GET','POST'])
def renderFormPage2():
    if "firstName" not in session:
        session["firstName"]=request.form['firstName']
    if "lastName" not in session:
        session["lastName"]=request.form['lastName']
    return render_template('form2page2.html')

@app.route('/page3',methods=['GET','POST'])
def renderPage3():
    if "firstName" not in session:
        session["firstName"]=request.form['firstName']
    if "lastName" not in session:
        session["lastName"]=request.form['lastName']
    return render_template('page3.html')
    
@app.route('/form2page3',methods=['GET','POST'])
def renderForm2Page3():
    if "interests" not in session:
        session["interests"]=request.form['interests']
    return render_template('form2page3.html')
    
@app.route('/page4',methods=['GET','POST'])
def renderPage4():
    if "interests" not in session:
        session["interests"]=request.form['interests']
    return render_template('page4.html')
    
@app.route('/form2page4',methods=['GET','POST'])
def renderForm2page4():
    if "education" not in session:
        session["education"]=request.form['education']
    return render_template('form2page4.html')

@app.route('/page5',methods=['GET','POST'])
def renderPage5():
    if "favColor" not in session:
        session["favColor"]=request.form['favColor']
    return render_template('page5.html')
    
@app.route('/form2page5',methods=['GET','POST'])
def renderForm2Page5():
    if "professional" not in session:
            session["professional"]=request.form['professional']
    return render_template('form2page5.html')

@app.route('/page6',methods=['GET','POST'])
def renderPage6():
    if "food" not in session:
        session["food"]=request.form['food']
    return render_template('page6.html')
    
@app.route('/form2page6',methods=['GET','POST'])
def renderForm2Page6():
    if "favSeason" not in session:
        session["favSeason"]=request.form['favSeason']
    return render_template('form2page6.html')

@app.route('/page7',methods=['GET','POST'])
def renderPage7():
    if "favSeason" not in session:
        session["favSeason"]=request.form['favSeason']
    return render_template('page7.html')

@app.route('/form2page7',methods=['GET','POST'])
def renderForm2Page7():
    if "age" not in session:
        session["age"]=request.form['age']
    return render_template('form2page7.html')
    
@app.route('/page8',methods=['GET','POST'])
def renderPage8():
    if "favHoliday" not in session:
        session["favHoliday"]=request.form['favHoliday']
    return render_template('page8.html')
    
@app.route('/form2page8',methods=['GET','POST'])
def renderForm2Page8():
    if "" not in session:
        session[""]=request.form['']
    return render_template('form2page8.html')
    
@app.route('/page9',methods=['GET','POST'])
def renderPage9():
    if "favHoliday" not in session:
        session["favHoliday"]=request.form['favHoliday']
    return render_template('page9.html')
    
@app.route('/quizFinal',methods=['GET','POST'])
def renderQuizFinal():
    if "future" not in session:
        session["future"]=request.form['professional']
    if "final" not in session:
        session["final"]=request.form['final']
    return render_template('quizFinal.html')
 
if __name__=="__main__":
    app.run(debug=True)
