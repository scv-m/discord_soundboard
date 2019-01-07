import os
import dataset
import json
from boto.s3.connection import S3Connection
from flask import Flask, redirect, url_for, request, render_template
from flask_dance.contrib.discord import make_discord_blueprint, discord

# Get Config
with open('/home/ubuntu/discord_soundboard/config.json') as json_config:
    config = json.load(json_config)

# While we have no HTTPS, allow insecure transport for testing
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'


app = Flask(__name__)
app.secret_key = config['SOUNDBOARD_APPSECRET']
blueprint = make_discord_blueprint(
    client_id=config['SOUNDBOARD_CLIENTID'],
    client_secret=config['SOUNDBOARD_CLIENTSECRET'],
    redirect_url='http://ec2-54-252-129-183.ap-southeast-2.compute.amazonaws.com:5000/',
    scope=['identify']
)
app.register_blueprint(blueprint)

def get_user_roles(user):
    db = dataset.connect('sqlite:////home/ubuntu/discord_bot/sqlite3/discord.db')
    return db['user_roles'].find_one(user=user)['roles'].split(',')

def get_discord_user(discord):
    return discord.get('/api/users/@me').json()

def verify_role(username, role_required):
    user_roles = get_user_roles(username)
    return role_required in user_roles

def get_s3_sounds():
    conn = S3Connection(config['AWS_ACCESS_KEY_ID'],
                        config['AWS_SECRET_ACCESS_KEY'])
    bucket = conn.get_bucket(config['AWS_STORAGE_BUCKET_NAME'])

    sounds_list = []
    for key in bucket.list():
        sounds_list.append(str(key.name.split('.mp3')[0]).lower())

    return sounds_list

def generate_sounds_table(sounds):
    data = ''
    for sound in sounds:
        data += '<a href="{sound}">{sound}</a><br>'.format(sound=sound)
    return data

def add_to_queue(sound, user):
    db = dataset.connect('sqlite:////home/ubuntu/discord_bot/sqlite3/discord.db')
    db['sound_queue'].insert(dict(user=user, sound=sound, state='ready'))
    return 'Added {sound} by {user} to queue'.format(sound=sound, user=user)

@app.route('/')
def index():
    if not discord.authorized:
        return '<a href="/login">Click here to login</a>'
    else:
        return redirect(url_for('soundboard'))

@app.route('/add/<string:sound>/<string:user>')
def add(sound, user):
    add_to_queue(sound, user)
    return redirect(url_for('soundboard'))

@app.route('/login')
def login():
    if not discord.authorized:
        return redirect(url_for('discord.login'))
    else:
        return redirect(url_for('soundboard'))

@app.route('/soundboard')
def soundboard():
    if not discord.authorized:
        return '<a href="/login">Click here to login</a>'

    if not verify_role(get_discord_user(discord)['username'], 'Soundboard'):
        return "Sorry, you don't have the required role for this page"

    return render_template('soundboard.html', 
        sounds=get_s3_sounds(), 
        user=get_discord_user(discord)['username'])

if __name__ == '__main__':
    app.run()
