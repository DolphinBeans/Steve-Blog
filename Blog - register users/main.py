from flask import Flask, render_template, redirect, request, url_for, flash, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
from functools import wraps
from dotenv import load_dotenv
import os
import email_validator

load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ['SECRET']
ckeditor = CKEditor(app)
Bootstrap(app)
gravatar = Gravatar(app, size=100, rating='g', default='retro', force_default=False, force_lower=False, use_ssl=False, base_url=None)

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)




##CONFIGURE TABLES

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True) #A primary key, or primary keyword, is a column in a relational database
    # table that's distinctive for each record (basically, a unique identifier).
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    username = db.Column(db.String(100), unique=True)
    blogs = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="comment_author")
    # What does db.relationship() do? It returns a property that can do multiple things. In thise case we told it to
    #point to the BlogPost class and load multiple of those (if you want to declare a one-to-one relationship you can pass
    # uselist=False to relationship). Since a person with no name or an email address with no address associated makes no sense,
    # nullable=False tells SQLAlchemy to create the column as NOT NULL. This is implied for primary key columns, but it's a good idea to specify
    # it for all other columns to make it clear to other people working on your code that you did actually want a nullable column and not just forget to add it.
    #backref is a simple way to also declare a relationship on the BlogPost class. You can then use


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="blogs")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    comments = relationship("Comment", back_populates="parent_post")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    comment_author = relationship("User", back_populates="comments")
    comment_author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    parent_post = relationship("BlogPost", back_populates="comments")
    parent_post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))


with app.app_context():
    db.create_all()


def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.get_id() != '1':
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    my_user = current_user.get_id()
    return render_template("index.html", all_posts=posts, logged_in=current_user.is_active, my_user=my_user)


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if request.method == "POST":
        new_user = User()
        new_user.username = request.form['username']
        new_user.email = request.form['email']
        new_user.password = generate_password_hash(password=request.form['password'], method='pbkdf2:sha256', salt_length=8)
        if User.query.filter_by(email=new_user.email).first():
            flash("This email address is already linked to an existing account.")
            flash("Please log in instead.")
            return render_template("login.html", form=form)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('get_all_posts'))
    return render_template("register.html", form=form)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user:
            if check_password_hash(user.password, password):
                login_user(user)
                return redirect(url_for('get_all_posts'))
            elif not check_password_hash(user.password, password):
                flash("Incorrect password.")
        else:
            flash("This email address is not linked to any account.")
    return render_template("login.html", form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Successfully logged out.")
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    comments = Comment.query.filter_by(parent_post_id=post_id).all()
    comment_form = CommentForm()
    if comment_form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for("login"))
        user_comment = request.form.to_dict()
        user_comment.pop('csrf_token')
        new_comment = Comment(text=user_comment['comment'], comment_author_id=current_user.get_id(),
                              parent_post_id=requested_post.id)
        db.session.add(new_comment)
        db.session.commit()
    return render_template("post.html", post=requested_post, logged_in=current_user.is_active,
                           my_user=current_user.get_id(), comment_form=comment_form, comments=comments)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author_id=current_user.id,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>")
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
