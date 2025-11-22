import os
from datetime import datetime

from flask import (
    Flask,
    request,
    render_template,
    redirect,
    url_for,
    session,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------------------------------------------
# Flask + Database config
# ---------------------------------------------------
app = Flask(__name__)
app.secret_key = "hua7y6s7u847yr80dsibjyg293wisxib0shf"  # change this in real life

# DATABASE_URL from env (Render) or local SQLite for development
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///local_dev.db")

# Some providers use postgres://, SQLAlchemy wants postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ---------------------------------------------------
# Models
# ---------------------------------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    clicks = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    upgrade = db.relationship("Upgrade", backref="user", uselist=False)


class Upgrade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    click_worth_value = db.Column(db.Integer, default=1, nullable=False)
    autoclick_value = db.Column(db.Integer, default=0, nullable=False)
    click_worth_price = db.Column(db.Integer, default=2, nullable=False)
    autoclick_price = db.Column(db.Integer, default=10, nullable=False)


# ---------------------------------------------------
# Helper functions
# ---------------------------------------------------
def get_user_by_username(username: str):
    return User.query.filter_by(username=username).first()


def get_logged_in_user():
    """Return User object from session username or None. Clears stale sessions."""
    username = session.get("username")
    if not username:
        return None
    user = get_user_by_username(username)
    if user is None:
        session.clear()
        return None
    return user


def create_user(username: str, email: str, password: str):
    hashed_pw = generate_password_hash(password)
    user = User(
        username=username,
        email=email,
        password_hash=hashed_pw,
        clicks=0,
    )
    db.session.add(user)
    db.session.commit()

    # Create default upgrades row
    upgrade = Upgrade(
        user_id=user.id,
        click_worth_value=1,
        autoclick_value=0,
        click_worth_price=2,
        autoclick_price=10,
    )
    db.session.add(upgrade)
    db.session.commit()
    return user


def get_upgrades_for_user(user: User) -> Upgrade:
    """Get the Upgrade row for a user, creating it if missing."""
    if user.upgrade is None:
        upgrade = Upgrade(
            user_id=user.id,
            click_worth_value=1,
            autoclick_value=0,
            click_worth_price=2,
            autoclick_price=10,
        )
        db.session.add(upgrade)
        db.session.commit()
        return upgrade
    return user.upgrade


def get_leaderboard():
    """Return a list of top 10 users by score (clicks)."""
    top_users = User.query.order_by(User.clicks.desc()).limit(10).all()
    return [{"username": u.username, "score": u.clicks} for u in top_users]


def apply_autoclick(user: User, upgrade: Upgrade):
    """
    Apply autoclick once to the user's score.
    This is called every time /get_score is polled from the browser.
    """
    if upgrade.autoclick_value > 0:
        user.clicks += upgrade.autoclick_value
        db.session.commit()


# ---------------------------------------------------
# Routes
# ---------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def start():
    if get_logged_in_user() is not None:
        return redirect(url_for("homepage"))
    return render_template("start.html")


@app.route("/sign_up", methods=["GET", "POST"])
def submit_form():
    if get_logged_in_user() is not None:
        return redirect(url_for("homepage"))

    error_message = ""
    error_message_status = False

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        verify_password = request.form["verify"].strip()
        email = request.form["email"].strip()

        # Check if user already exists
        existing_user = get_user_by_username(username)
        if existing_user:
            error_message = "Username already exists!"
            error_message_status = True
            return render_template(
                "sign_up.html",
                error_message=error_message,
                error_message_status=error_message_status,
            )

        if password != verify_password:
            error_message = "Verify password is not the same as password!"
            error_message_status = True
            return render_template(
                "sign_up.html",
                error_message_status=error_message_status,
                error_message=error_message,
            )

        # Create user in DB
        try:
            create_user(username, email, password)
        except Exception:
            # In a real app: log the error
            return "ERROR WITH DATABASE"

        return redirect(url_for("log_in"))

    return render_template(
        "sign_up.html",
        error_message=error_message,
        error_message_status=error_message_status,
    )


@app.route("/log_in", methods=["GET", "POST"])
def log_in():
    if get_logged_in_user() is not None:
        return redirect(url_for("homepage"))

    error_message = ""
    error_status = False

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        email = request.form["email"].strip()

        user = get_user_by_username(username)

        if user is None:
            error_status = True
            error_message = "This user does not exist"
            return render_template(
                "log_in.html",
                error_message=error_message,
                error_status=error_status,
            )

        # Check password + email
        if check_password_hash(user.password_hash, password) and user.email == email:
            session["username"] = username
            return redirect(url_for("homepage"))
        else:
            error_status = True
            error_message = "Incorrect email or password"

    return render_template(
        "log_in.html",
        error_status=error_status,
        error_message=error_message,
    )


@app.route("/homepage")
def homepage():
    user = get_logged_in_user()
    if user is None:
        return redirect(url_for("log_in"))

    upgrade = get_upgrades_for_user(user)

    score = user.clicks
    cps = upgrade.autoclick_value
    click_worth = upgrade.click_worth_value

    return render_template(
        "homepage.html",
        score=score,
        cps=cps,
        click_worth=click_worth,
    )


@app.route("/upgrade_shop", methods=["GET", "POST"])
def upgrade_shop():
    user = get_logged_in_user()
    if user is None:
        return redirect(url_for("start"))

    error_status = False
    error_message = ""

    upgrade = get_upgrades_for_user(user)

    score = user.clicks
    autoclick_price = upgrade.autoclick_price
    click_worth_price = upgrade.click_worth_price
    autoclick_value = upgrade.autoclick_value
    click_worth_value = upgrade.click_worth_value

    price_mult = 1.5

    if request.method == "POST":
        if "buy_autoclick" in request.form:
            if score >= autoclick_price:
                score -= autoclick_price
                user.clicks = score

                upgrade.autoclick_price = int(price_mult * autoclick_price)
                upgrade.autoclick_value = autoclick_value + 1

                db.session.commit()
            else:
                error_status = True
                error_message = "You dont have enough score to buy this item"

        elif "buy_click_worth" in request.form:
            if score >= click_worth_price:
                score -= click_worth_price
                user.clicks = score

                upgrade.click_worth_price = int(price_mult * click_worth_price)
                upgrade.click_worth_value = click_worth_value + 1

                db.session.commit()
            else:
                error_status = True
                error_message = "You dont have enough score to buy this item"

        # Refresh DB values after changes
        db.session.refresh(user)
        db.session.refresh(upgrade)
        score = user.clicks
        autoclick_price = upgrade.autoclick_price
        click_worth_price = upgrade.click_worth_price
        autoclick_value = upgrade.autoclick_value
        click_worth_value = upgrade.click_worth_value

    return render_template(
        "upgrade_shop.html",
        autoclick_price=autoclick_price,
        click_worth_price=click_worth_price,
        score=score,
        error_message=error_message,
        error_status=error_status,
    )


@app.route("/click", methods=["POST"])
def click():
    """
    Handle one manual cookie click without reloading the page.
    """
    user = get_logged_in_user()
    if user is None:
        return {"score": 0}, 401

    upgrade = get_upgrades_for_user(user)
    user.clicks += upgrade.click_worth_value
    db.session.commit()

    return {"score": user.clicks}


@app.route("/get_score")
def get_score():
    """
    Called every second by JS to:
    - apply autoclick once
    - return current score, cps, click_worth
    """
    user = get_logged_in_user()
    if user is None:
        return {"score": 0, "cps": 0, "click_worth": 1}

    upgrade = get_upgrades_for_user(user)

    # Apply autoclick once per poll
    apply_autoclick(user, upgrade)

    return {
        "score": user.clicks,
        "cps": upgrade.autoclick_value,
        "click_worth": upgrade.click_worth_value,
    }


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("start"))


@app.route("/get_leaderboard")
def get_leaderboard_route():
    top_players = get_leaderboard()
    return {"players": top_players}


# ---------------------------------------------------
# Main
# ---------------------------------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
