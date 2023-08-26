from email_validator import validate_email, EmailSyntaxError
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, PasswordField
from wtforms.validators import DataRequired, Length
from random import sample
from datetime import timedelta
from keys import BOT_EMAIL, BOT_PASSWORD, RECIPIENT_EMAIL, HOST, USERNAME, ADMIN_PASSWORD,
                  APP_CON_SECRET_KEY, APP_SECRET_KEY)
import smtplib

# Flask
app = Flask(__name__)

# Connect to DB, set secret keys
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///poems.db'
db = SQLAlchemy()
db.init_app(app)
app.config['SECRET_KEY'] = APP_CON_SECRET_KEY
app.secret_key = APP_SECRET_KEY
app.permanent_session_lifetime = timedelta(hours=1)


# Form to add/edit poems
class NewPoem(FlaskForm):
    poem_title = StringField(label="Název básně: ", validators=[DataRequired()])
    poem_subtitle = TextAreaField(label="Ukázka básně: ", validators=[DataRequired()])
    poem_text = TextAreaField(label="Celá báseň: ", validators=[DataRequired()])
    poem_date = StringField(label="Datum (například 01.01.2020): ", validators=[DataRequired()])
    submit_button = SubmitField(label="Potvrdit")


# Login form
class Login(FlaskForm):
    username = StringField(label="Username: ", validators=[DataRequired()])
    password = PasswordField(label="Password: ", validators=[DataRequired()])
    submit_button = SubmitField("Login")


# Contact form
class Contact(FlaskForm):
    sender = StringField(label="Váš e-mail: ", validators=[DataRequired()])
    message = TextAreaField(label="Text e-mailu: ", validators=[DataRequired(), Length(min=10)])
    submit_button = SubmitField("Odeslat")


# Configure DB table
class Poem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(500), nullable=False)
    poem_text = db.Column(db.Text, nullable=False)
    date = db.Column(db.String(250), nullable=False)


# Create DB
with app.app_context():
    db.create_all()


def send_mail(sender, message):
    connection = smtplib.SMTP(host=HOST)
    connection.starttls()
    connection.login(user=BOT_EMAIL, password=BOT_PASSWORD)

    final_message = (f"Subject: Zpráva z nathaliaklatovski.cz\n\n"
                     f"E-mail odesílatele: {sender}\n"
                     f"{message}")
    connection.sendmail(from_addr=BOT_EMAIL,
                        to_addrs=RECIPIENT_EMAIL,
                        msg=final_message.encode('utf-8'))


@app.route("/")
def home():
    result = db.session.execute(db.select(Poem))
    poems = result.scalars().all()
    random_poems = sample(poems, 3)
    return render_template("index.html", all_poems=random_poems)


@app.route("/all_poems")
def all_poems():
    result = db.session.execute(db.select(Poem))
    poems = result.scalars().all()
    admin_logged = "admin" in session
    return render_template("all_poems.html", all_poems=poems, admin_logged=admin_logged)


@app.route("/poem/<int:poem_id>")
def show_poem(poem_id):
    requested_poem = db.get_or_404(Poem, poem_id)
    return render_template("poem.html", poem=requested_poem, admin_logged="admin" in session)


@app.route("/about_me")
def bio():
    return render_template("bio.html")


@app.route("/admin")
def admin():
    if "admin" in session:
        return render_template("admin.html")
    else:
        return redirect(url_for("login"))


@app.route("/admin/login", methods=["GET", "POST"])
def login():
    login_form = Login()
    if login_form.validate_on_submit():
        if login_form.username.data == USERNAME and login_form.password.data == ADMIN_PASSWORD:
            session["admin"] = "Logged"
            flash("Přihlášení úspěšné!", "Succes")
            return redirect(url_for("admin"))
        else:
            flash("Chybné údaje!", "danger")
            return render_template("login.html", form=login_form)
    return render_template("login.html", form=login_form)


@app.route("/admin/logout")
def logout():
    if "admin" in session:
        session.pop("admin", None)
        flash("Odhlášení úspěšné!", "succes")
    return redirect(url_for("login"))


@app.route("/admin/new_poem", methods=["GET", "POST"])
def add_new_poem():
    if "admin" not in session:
        return redirect(url_for("login"))
    poem_form = NewPoem()
    if poem_form.validate_on_submit():
        new_poem = Poem(
            title=poem_form.poem_title.data,
            subtitle=poem_form.poem_subtitle.data,
            poem_text=poem_form.poem_text.data,
            date=poem_form.poem_date.data
        )
        db.session.add(new_poem)
        db.session.commit()
        flash(f"Báseň {poem_form.poem_title.data} přidána!", "succes")
        return redirect(url_for("admin"))

    return render_template("new_poem.html", form=poem_form, is_edit=False)


@app.route("/admin/edit_poem/<int:poem_id>", methods=["GET", "POST"])
def edit_poem(poem_id):
    if "admin" in session:
        poem = db.get_or_404(Poem, poem_id)
        edit_form = NewPoem(poem_title=poem.title, poem_subtitle=poem.subtitle, poem_text=poem.poem_text,
                            poem_date=poem.date)
        if edit_form.validate_on_submit():
            poem.title = edit_form.poem_title.data
            poem.subtitle = edit_form.poem_subtitle.data
            poem.poem_text = edit_form.poem_text.data
            poem.date = edit_form.poem_date.data
            db.session.commit()
            flash(f"Báseň {edit_form.poem_title.data} upravena!", "succes")
            return redirect(url_for("all_poems"))

    else:
        return redirect(url_for("login"))

    return render_template("new_poem.html", form=edit_form, is_edit=True)


@app.route("/admin/delete_poem/<int:poem_id>", methods=["GET", "POST"])
def delete_poem(poem_id):
    if "admin" in session:
        poem = db.get_or_404(Poem, poem_id)
        poem_name = poem.title
        db.session.delete(poem)
        db.session.commit()
        flash(f"Báseň {poem_name} smazána!", "succes")
    else:
        return redirect(url_for("login"))
    return redirect(url_for("all_poems"))


@app.route("/contact", methods=["GET", "POST"])
def contact():
    contact_form = Contact()
    if contact_form.validate_on_submit():
        try:
            validate_email(contact_form.sender.data)
            send_mail(contact_form.sender.data, contact_form.message.data)
            flash("E-mail byl odeslán!", "success")
            contact_form.sender.data = ""
            contact_form.message.data = ""
        except EmailSyntaxError:
            flash("Zadej platnou e-mailovou adresu!", "danger")
    return render_template("contact.html", form=contact_form)


if __name__ == "__main__":
    app.run(debug=True, port=5002, host="10.0.1.35")
