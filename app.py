import os, datetime
from flask import Flask, render_template, redirect, request, url_for, session
from flask_wtf import FlaskForm
from wtforms import FileField
from flask_uploads import UploadSet, configure_uploads, IMAGES
from flask_pymongo import PyMongo
from bson.objectid import ObjectId


import bcrypt

if os.path.exists("env.py"):
  import env 

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]
app.config["MONGO_DBNAME"] = os.environ["MONGO_DBNAME"]
app.config["MONGO_URI"] = os.environ["MONGO_URI"]
mongo = PyMongo(app)

app.config['UPLOADED_IMAGES_DEST'] = 'static/img/users/'
images = UploadSet('images', IMAGES)
configure_uploads(app, images)

# ====================================================================================
# ==== H E L P E R  F U N C T I O N S ================================================
# ---- Get user in session  ----
def find_users():
	return mongo.db.users.find({
		"email" : session['email']})

# ---- Get a specified value from one user  ----
def get_user_value(key):
	return mongo.db.users.find_one({
		"email" : session['email']})[key]

# ---- Get _id when user logs in or register  ----
def get_user_id(email):
	return mongo.db.users.find_one({
		"email" : email})["_id"]

# ---- Set session variables ----
def set_session_vars(email):
	session['email'] = email
	session['user_id'] = str(get_user_id(email))

# ---- Update User activity code ----
def update_user_activity(new_activity):
	mongo.db.users.update(
		{"email" : session['email']},
		{"$set":{"activity_code":new_activity}})

def get_request_data(request_data, empty_string_text):
	if request_data == "":
		return empty_string_text
	return request_data

# ====================================================================================
# ==== I N D E X =====================================================================
# TODO: Fix crash when user is removed from db but still in cache
@app.route('/')
def index():
	if "email" in session:
		activity_code = get_user_value('activity_code')
		#img_base_url = "..\static\img\users\"
		return render_template(
			"index.html",
			users=find_users(),
			activity = get_activity(activity_code),
			options = get_activity_options(activity_code),
			log_headers = get_log_header(ObjectId(session['user_id'])),
			logs = list(get_log_entries(ObjectId(session['user_id']))))
	return render_template("login.html")

# ====================================================================================
# ==== C H A N G E  A C T I V I T Y ==================================================

# ---- Get activity by activity code ----
def get_activity(activity):
	if activity is not None:
		return mongo.db.activity_statuses.find_one({
			"activity_code" : activity})
	return "No activity set"

# ---- Get activity options  ----
def get_activity_options(activity):
	return mongo.db.activity_options.find({
		"show_on_status" : activity })

# ---- Change activity  ----
@app.route('/change_activity/<int:new_activity>')
def change_activity(new_activity):
	if new_activity == 2:
		return render_template("newjourney.html")
	if get_user_value('activity_code') == 2:
		close_journey()
	update_user_activity(new_activity)
	return redirect(url_for("index"))

# ====================================================================================
# ==== G E T  C O N T E N T ==========================================================

# ---- GET LOG HEADERS  ----
def get_log_header(userId):
	return mongo.db.log_headers.find({"user_id" : userId}).sort("number",-1)

# ---- GET LOG ENTRIES   ----
def get_log_entries(userId):
	return mongo.db.logs.find({"user_id" : userId}).sort("datetime",-1)

# ====================================================================================
# ==== L O G  T Y P E S  =============================================================

# **** LOGTYPE: JOURNEY  *************************************************************

# ---- New Journey Header  ----
@app.route("/newjourney", methods=["POST", "GET"])
def newjourney():
	if request.method == "POST":
		close_journey()
		update_user_activity(2)
		#TODO: Get the real index value for header_index below
		header_index = mongo.db.log_headers.count() + 1
		log_headers = mongo.db.log_headers
		log_headers.insert({
			'user_id' : ObjectId(session['user_id']),
			'type' : 'Journey',
			'number' : header_index,
			'title' : request.form["title"],
			'description' : get_request_data(request.form["description"], " -- "),
			'start_location' : get_request_data(request.form["start_location"], " -- "),
			'end_location' : get_request_data(request.form["end_location"], " -- "),
			'distance' : get_request_data(request.form["distance"], " -- "),
			'start_datetime' : datetime.datetime.now(),
			'end_datetime' :  "Ongoing",
			'is_active' : True,
			'is_editable' : False })
		return redirect(url_for('index'))
	return render_template("new_journey_log.html")

@app.route('/edit_journey/<journey_id>', methods=['POST', 'GET'])
def edit_journey(journey_id):
	if request.method == 'POST':
		mongo.db.log_headers.update(
		{'_id' : ObjectId(journey_id)},
		{'$set':{
			'title': request.form['title'],
			'description' : get_request_data(request.form["description"], " -- "),
			'start_location' : get_request_data(request.form["start_location"], " -- "),
			'end_location' : get_request_data(request.form["end_location"], " -- "),
			'distance' : get_request_data(request.form["distance"], " -- "),
			'is_editable' : False }})
		return redirect(url_for('index'))
	this_journey = mongo.db.log_headers.find({'_id' : ObjectId(journey_id)})
	return render_template("edit_journey.html", journey_id=journey_id, this_journey=this_journey)

# ---- Close active Journey before creating a new ----
def close_journey():
	find_journey = {
		'user_id' : ObjectId(session['user_id']),
		'type' : 'Journey', 'is_active' : True}
	update_values = {'$set': {
		'end_datetime' : datetime.datetime.now(),
		'is_active' : False} }
	mongo.db.log_headers.update_one(find_journey, update_values)

# ---- Set a logheader and it's sub lug entries to a editable state ----
@app.route("/set_editable/<journey_id>")
def set_editable(journey_id):
	find_journey = {'_id' : ObjectId(journey_id)}
	is_editable = mongo.db.log_headers.find_one(find_journey)['is_editable']
	if is_editable:
		update_values = {'$set': {'is_editable' : False } }
	else:
		update_values = {'$set': {'is_editable' : True } }
	mongo.db.log_headers.update_one(find_journey, update_values)
	return redirect(url_for('index'))

# ---- New Journey Log Entry ----
@app.route("/newlog/<journey_id>", methods=["POST", "GET", 'request.files or none'])
def newlog(journey_id):
	if request.method == "POST":
		log_number = mongo.db.logs.find({"head_id" : ObjectId(journey_id)}).count() + 1
		try:
			save_folder = str(session['user_id'] + '/' + str(journey_id)) + '/' + str(log_number)
			image = images.save(request.files['image'], save_folder)
			img_url = "../static/img/users/" + str(image)
		except:
			img_url = "none"

		mongo.db.logs.insert({
			'user_id' : ObjectId(session['user_id']),
			'head_id' : ObjectId(journey_id),
			'log_number' : log_number,
			'type' : 'journey_log',
			'datetime' : datetime.datetime.now(),
			'title' : request.form["title"],
			'note' : request.form["note"],
			'img_url' : img_url,
			'img_cap' : request.form["img_cap"],
			'weather' : get_request_data(request.form["weather"], " -- "),
			'temp' : get_request_data(request.form["temp"], " -- "),
			'air_pressure' : get_request_data(request.form["air_pressure"], " -- "),
			'wind_dir' : get_request_data(request.form["wind_dir"], " -- "),
			'wind_speed' : get_request_data(request.form["wind_speed"], " -- "),
			'activity' : get_request_data(request.form["activity"], " -- "),
			'heading' : get_request_data(request.form["heading"], " -- "),
			'speed' : get_request_data(request.form["speed"], " -- "),
			'location' : get_request_data(request.form["location"], " -- "),
			'position' : 
				[{
				'latitude' : get_request_data(request.form["latitude"], " -- "),
				'longitude' : get_request_data(request.form["longitude"], " -- ")
				}],
			})
		return redirect(url_for('index'))
	weather_options = mongo.db.weather_options.find()
	wind_directions = mongo.db.wind_dir_options.find()
	activity_options = mongo.db.sub_activity_options.find()
	return render_template(
		'new_journey_log.html', 
		journey_id = journey_id, 
		weather_options = weather_options,
		wind_directions = wind_directions,
		activity_options = activity_options)

# ====================================================================================
# ==== U S E R  A U T H E N T I C A T I O N  / R E G I S T R A T I O N ===============

# **** SIGNUP ************************************************************************
@app.route("/signup", methods=["POST", "GET"])
def signup():
	if request.method == "POST":
		users = mongo.db.users
		emailExist = users.find_one({"email": request.form["email"]})
		if emailExist is None:
			password_hashed = bcrypt.hashpw(request.form["password"].encode("utf-8"),bcrypt.gensalt())
			users.insert_one({
			'first_name' : request.form["first-name"],
			'last_name' : request.form["last-name"],
			'email' : request.form["email"],
			'password' : password_hashed,
			'activity_code' : 0 })
			set_session_vars(request.form['email'])
			return redirect(url_for("index"))
		return render_template("signup.html", emailExist = True)		
	elif "email" in session:
		return redirect(url_for("index")) 
	return render_template("signup.html")

# **** LOG IN ****************************************************************************
@app.route('/login', methods=['POST'])
def login():
	users = mongo.db.users
	validUser = users.find_one({'email' : request.form['email']})
	renderBadLogin = render_template('login.html', badLogin = True)
	if validUser:
		if bcrypt.hashpw(
			request.form['password'].encode('utf-8'),
			validUser['password']) == validUser['password']:
			set_session_vars(request.form['email'])
			return redirect(url_for('index'))
		return renderBadLogin
	return renderBadLogin

# **** LOG OUT ***************************************************************************
@app.route("/logout")
def logout():
	session.clear()
	return redirect(url_for('index'))

# ====================================================================================
# ==== A P P . R U N =================================================================
if __name__ == '__main__':
    app.run(host=os.environ.get('IP'),
        port=os.environ.get('PORT'),
        debug=True)
