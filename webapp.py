from flask import Flask
from flask_apscheduler import APScheduler
from apscheduler.schedulers.background import BackgroundScheduler
 
import time
 
app = Flask(__name__)
#initialize scheduler with your preferred timezone
scheduler = BackgroundScheduler({'apscheduler.timezone': 'America/Los_Angeles'})
scheduler.start()
 
@app.route('/')
def welcome():
    return 'Welcome to flask_apscheduler demo'
  
if __name__=="__main__":
    app.run(debug=False)
