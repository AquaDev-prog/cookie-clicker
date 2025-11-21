from flask import Flask, request, render_template, redirect, url_for, session
import json
import os
import random
import string
from flask_apscheduler import APScheduler
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "hua7y6s7u847yr80dsibjyg293wisxib0shf"

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()


def get_leaderboard():
    """Return a list of top 10 users by score."""
    users_folder = 'users'
    leaderboard = []

    if not os.path.exists(users_folder):
        return leaderboard  # empty

    for filename in os.listdir(users_folder):
        # We only want login_save_*.json files
        if filename.startswith("login_save_") and filename.endswith(".json"):
            path = os.path.join(users_folder, filename)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                continue  # skip broken files

            username = data.get("username", "Unknown")
            score = data.get("clicks", 0)

            leaderboard.append({
                "username": username,
                "score": score
            })

    # Sort by score, highest first
    leaderboard.sort(key=lambda x: x['score'], reverse=True)

    # Return only top 10
    return leaderboard[:10]

def apply_autoclick(username):
    """Add autoclick_value to the player's score once."""
    save = read_save_file(username)
    upgrades = read_upgrades_func(username)

    if save is None or upgrades is None:
        return None  # nothing to update

    autoclick_value = upgrades.get('autoclick_value', 0)
    if autoclick_value <= 0:
        return save  # user has no autoclickers

    current_score = save.get('clicks', 0)
    save['clicks'] = current_score + autoclick_value

    write_save_file(username, save)
    return save

#add the redirect link without the slash
def check_username(redirect_link):
    if 'username' in session:
        username = session['username']
        return username
    else:
        return redirect(url_for(f"{redirect_link}"))

def read_upgrades_func(username):
    filename = f"{username}_upgrades.json"
    path = os.path.join('users', filename)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def read_save_file(username):
    filename = f"login_save_{username}.json"
    path = os.path.join('users', filename)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def write_save_file(username, json_data):
    filename = f"login_save_{username}.json"
    path = os.path.join('users', filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=4)

def write_upgrades(username, json_data):
    filename = f"{username}_upgrades.json"
    path = os.path.join('users', filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=4)
def autoclick(username):
    read_save = read_save_file(username)
    read_upgrades = read_upgrades_func(username)
    
    if read_upgrades is None or read_save is None:
        return
        
    autoclick_value = read_upgrades.get('autoclick_value', 0)
    if autoclick_value <= 0:
        return
    current_score = read_save.get('clicks', 0)
    read_save['clicks'] = current_score + autoclick_value

    write_save_file(username, read_save)


@app.route('/', methods=['GET', 'POST'])
def start():
    if 'username' in session:
        return redirect(url_for('homepage'))
    return render_template('start.html')

@app.route('/sign_up', methods=['GET', 'POST'])
def submit_form():
    if 'username' in session:
        return redirect(url_for('homepage'))
    error_message = ""
    error_message_status = False
    if request.method == 'POST':
        username = request.form['username'].strip()
        path = os.path.join("users", f"login_save_{username}.json")
        if os.path.exists(path) == True:
            error_message = "Username already exists!"
            error_message_status = True
            return render_template('sign_up.html',
                                   error_message=error_message,
                                   error_message_status=error_message_status)
        else:

            password = request.form['password'].strip()
            verify_password = request.form['verify'].strip()
            if password != verify_password:
                error_message = "Verify password is not the same as password!"
                error_message_status = True
                return render_template('sign_up.html',
                                        error_message_status=error_message_status,
                                        error_message=error_message)
            email = request.form['email'].strip()
            hashed_pw = generate_password_hash(password)
            login_save = {
                "username" : username,
                "password" : hashed_pw,
                "email" : email,
                "clicks" : 0
            }
            upgrades_save = {
                "click_worth_value" : 1,
                "autoclick_value" : 0,
                "click_worth_price" : 2,
                "autoclick_price" : 10
            }

            try:
                write_save_file(username, login_save)
                write_upgrades(username, upgrades_save)

            except IOError as e:
                return "ERROR WITH .JSON"
            
            return redirect(url_for('log_in'))
    return render_template('sign_up.html',
                            error_message=error_message,
                            error_message_status=error_message_status,
                            )

@app.route('/log_in', methods=['GET', 'POST'])
def log_in():
    if 'username' in session:
            return redirect(url_for('homepage'))
    error_message = ""
    error_status = False
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        email = request.form['email'].strip()
        read_save = read_save_file(username)
            
                
        password_json = read_save.get("password")
        email_json = read_save.get("email")
        if read_save is None:
            error_status = True
            error_message - "This user does not exist"
            return render_template('log_in.html', error_message=error_message, error_status=error_status)
        elif check_password_hash(password_json, password) == password and email_json == email:
            session['username'] = username

            job_id = f"autoclick_{username}"
            try:
                scheduler.remove_job(job_id)
            except Exception:
                pass

            scheduler.add_job(
                id=job_id,
                func=autoclick,
                args=[username],
                trigger='interval',
                seconds=1
            )

            return redirect(url_for('homepage'))
        else:
            error_status = True
            error_message = "Incorrect email or password"

    return render_template('log_in.html', error_status=error_status,
                           error_message=error_message)

@app.route('/homepage', methods=['GET', 'POST'])
def homepage():
    
    usernameORredirect = check_username('log_in')
    if not isinstance(usernameORredirect, str):
        return usernameORredirect
    username = usernameORredirect

    read_upgrades = read_upgrades_func(username)
    read_save = read_save_file(username)
    

    score = read_save.get('clicks')
    cps = read_upgrades.get('autoclick_value', 0)
    click_worth = read_upgrades.get('click_worth_value', 1)

    if request.method == 'POST':
        if 'cookie' in request.form:
            score += click_worth
            new_score = score
            read_save['clicks'] = new_score

            write_save_file(username, read_save)

        elif 'shop' in request.form:
            return redirect(url_for('upgrade_shop'))
        
        elif 'log_out' in request.form:
            username = session.get('username')

            if username:
                job_id = f"autoclick_{username}"
                try:
                    scheduler.remove_job(job_id)
                except Exception:
                    pass

            session.clear()
            return redirect(url_for('start'))
    

    return render_template('homepage.html', score=score, cps=cps, click_worth=click_worth)

@app.route('/upgrade_shop', methods=['GET', 'POST'])
def upgrade_shop():
    if 'username' not in session:
        return redirect(url_for('start'))
    
    error_status = False
    error_message = ""
    username = session['username']
    read_clicks = read_save_file(username)
    read_upgrade = read_upgrades_func(username)

    score = read_clicks.get('clicks')
    autoclick_price = read_upgrade.get('autoclick_price', 10)
    click_worth_price = read_upgrade.get('click_worth_price', 2)
    autoclick_value = read_upgrade.get('autoclick_value', 0)
    click_worth_value = read_upgrade.get('click_worth_value', 1)
    price_mult = 1.5
    if request.method == 'POST':
        if 'buy_autoclick' in request.form:
            if score >= autoclick_price:
                score -= autoclick_price
                new_score1 = score
                read_clicks['clicks'] = new_score1

                autoclick_price = int(price_mult * autoclick_price)
                new_autoclick_price = autoclick_price
                read_upgrade['autoclick_price'] = new_autoclick_price

                autoclick_value += 1
                new_autoclick_value = autoclick_value
                read_upgrade['autoclick_value'] = new_autoclick_value
                
                
                write_upgrades(username, read_upgrade)

                write_save_file(username, read_clicks)
                
            else:
                error_status = True
                error_message = 'You dont have enough score to buy this item'

        elif 'buy_click_worth' in request.form:
            if score >= click_worth_price:

                score -= click_worth_price
                new_score2 = score
                read_clicks['clicks'] = new_score2

                click_worth_price = int(price_mult * click_worth_price)
                new_click_worth_price = click_worth_price
                read_upgrade['click_worth_price'] = new_click_worth_price

                click_worth_value += 1
                new_click_worth_value = click_worth_value
                read_upgrade['click_worth_value'] = new_click_worth_value
                
                write_upgrades(username, read_upgrade)

                write_save_file(username, read_clicks)
            else:
                error_status = True
                error_message = 'You dont have enough score to buy this item'

    return render_template('upgrade_shop.html',
                            autoclick_price=autoclick_price,
                            click_worth_price=click_worth_price,
                            score=score,
                            error_message=error_message,
                            error_status=error_status)

@app.route('/get_score')
def get_score():
    username = session.get('username')
    if not username:
        return {"score": 0, "cps": 0, "click_worth": 1}

    save = apply_autoclick(username)
    upgrades = read_upgrades_func(username)

    return {
        "score": save.get("clicks", 0),
        "cps": upgrades.get("autoclick_value", 0),
        "click_worth": upgrades.get("click_worth_value", 1)
    }

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('start'))

@app.route('/get_leaderboard')
def get_leaderboard_route():
    top_players = get_leaderboard()
    return {"players": top_players}

if __name__ == '__main__':
    app.run(debug=True)