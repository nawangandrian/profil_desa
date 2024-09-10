import os
from os.path import join, dirname
from dotenv import load_dotenv
from math import ceil

from flask import Flask, redirect, url_for, render_template, request, jsonify, flash, session
from pymongo import MongoClient, DESCENDING, ASCENDING

from bson import ObjectId
from flask_bcrypt import Bcrypt
from flask_session import Session
from flask_bcrypt import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

MONGODB_URI = os.environ.get("MONGODB_URI")
DB_NAME =  os.environ.get("DB_NAME")

client = MongoClient(MONGODB_URI)

db = client[DB_NAME]

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/assets/uploads'
app.secret_key = 'BALEREJO'
SECRET_KEY = "BALEREJO"

bcrypt = Bcrypt(app)

users_collection = db['users']

#mongodb+srv://kknumkbalerejo:kknumk_balerejo@cluster0.0kij7.mongodb.net/

@app.template_filter('datetimeformat')
def datetimeformat(value, format='%d %b, %Y'):
    return datetime.strptime(value, '%Y-%m-%d').strftime(format)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session or session['username'] == '':
            flash('Harap login terlebih dahulu.', 'error')
            return redirect(url_for('home'))
        if 'status' not in session or session['status'] != 'login':
            flash('Anda harus login terlebih dahulu untuk mengakses halaman ini.', 'error')
            return redirect(url_for('home'))
        if session['username'] != 'admin':
            flash('Akses ditolak. Hanya admin yang dapat mengakses halaman ini.', 'error')
            return redirect(url_for('beranda'))
        return f(*args, **kwargs)
    return decorated_function

def user_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session or session['username'] == '':
            flash('Harap login terlebih dahulu.', 'error')
            return redirect(url_for('home'))
        if 'status' not in session or session['status'] != 'login':
            flash('Anda harus login terlebih dahulu untuk mengakses halaman ini.', 'error')
            return redirect(url_for('home'))
        if session['username'] == 'admin':
            flash('Akses ditolak, harus login sebagai user.', 'error')
            return redirect(url_for('upmerchandise'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm-password']

        if password != confirm_password:
            return jsonify({"status": "error", "message": "Password dan konfirmasi password tidak cocok"}), 404

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        user_exists = users_collection.find_one({'username': username})

        if user_exists:
            return jsonify({"status": "error", "message": "Username sudah ada, gunakan yang lain"}), 404

        users_collection.insert_one({'username': username, 'password': hashed_password,})

        return redirect(url_for('home'))

    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    if request.method == 'POST':
        login_user = users_collection.find_one({'username': request.form['username']})

        if login_user and bcrypt.check_password_hash(login_user['password'], request.form['password']):
            session['username'] = request.form['username']
            session['password'] = login_user['password']
            session['_id'] = str(login_user['_id'])
            session['status'] = 'login'

            if request.form['username'] == 'admin':
                return jsonify({"status": "success", "redirect_url": url_for('beranda')}), 200
            else:
                return jsonify({"status": "success", "redirect_url": url_for('home')}), 200

        return jsonify({"status": "error", "message": "Kombinasi username/password tidak valid"}), 404

    return render_template('index.html')

@app.route('/blog/create', methods=['GET', 'POST'])
@admin_required
def create_blog():
    if request.method == 'POST':
        # Extract form data
        title = request.form['title']
        author = request.form['author']
        publication_date = request.form['publication_date']
        initial_views = int(request.form['initial_views'])
        archived = 'archived' in request.form 
        quotes = request.form.get('quotes', '')
        tags = request.form.getlist('tags')

        # Handle title image upload
        title_image = request.files['title_image']
        title_image_filename = secure_filename(title_image.filename)
        title_image.save(os.path.join(app.config['UPLOAD_FOLDER'], title_image_filename))

        # Handle additional images
        additional_images = []
        for file in request.files.getlist('additional_images[]'):
            if file:
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                additional_images.append(filename)

        # Handle content paragraphs
        content_paragraphs = request.form.getlist('content_paragraphs[]')
        content = "\n\n".join(content_paragraphs)  # Combine paragraphs with two newlines

        # Create a blog post document
        blog_post = {
            'title': title,
            'author': author,
            'publication_date': publication_date,
            'quotes': quotes,
            'views': initial_views,
            'title_image': title_image_filename,
            'additional_images': additional_images,
            'content': content,
            'archived': archived,
            'tags': tags,
        }

        # Insert the blog post into the MongoDB database
        db.blogs.insert_one(blog_post)

        flash('Blog post created successfully!', 'success')
        return redirect(url_for('crud_blog'))  
    
    return render_template('crud_blog.html', form_title='Create Blog Post', submit_button_text='Create')

@app.route('/blog/edit/<blog_id>', methods=['GET', 'POST'])
@admin_required
def edit_blog(blog_id):
    blog = db.blogs.find_one({'_id': ObjectId(blog_id)})
    if request.method == 'POST':
        # Update the basic fields
        title = request.form['title']
        author = request.form['author']
        publication_date = request.form['publication_date']
        content_paragraphs = request.form.getlist('content_paragraphs[]')
        content = "\n\n".join(content_paragraphs)
        quotes = request.form.get('quotes', '')
        tags = request.form.getlist('tags')

        # Update title image if a new one is provided
        if 'title_image' in request.files and request.files['title_image'].filename:
            title_image = request.files['title_image']
            title_image_filename = secure_filename(title_image.filename)
            title_image.save(os.path.join(app.config['UPLOAD_FOLDER'], title_image_filename))
            blog['title_image'] = title_image_filename

        # Handle additional images
        updated_images = []
        for idx, image in enumerate(blog['additional_images']):
            if f'remove_image_{idx}' in request.form:
                # Skip adding this image if it should be removed
                continue
            elif f'replace_image_{idx}' in request.files and request.files[f'replace_image_{idx}'].filename:
                # Replace image
                new_image = request.files[f'replace_image_{idx}']
                new_image_filename = secure_filename(new_image.filename)
                new_image.save(os.path.join(app.config['UPLOAD_FOLDER'], new_image_filename))
                updated_images.append(new_image_filename)
            else:
                # Keep existing image
                updated_images.append(image)

        # Add new images
        for new_image in request.files.getlist('additional_images[]'):
            if new_image.filename:
                new_image_filename = secure_filename(new_image.filename)
                new_image.save(os.path.join(app.config['UPLOAD_FOLDER'], new_image_filename))
                updated_images.append(new_image_filename)

        # Update the blog post in the database
        db.blogs.update_one(
            {'_id': ObjectId(blog_id)},
            {
                '$set': {
                    'title': title,
                    'author': author,
                    'publication_date': publication_date,
                    'content': content,
                    'title_image': blog['title_image'],
                    'additional_images': updated_images,
                    'quotes': quotes,
                    'tags': tags,
                }
            }
        )
        flash('Blog post updated successfully!', 'success')
        return redirect(url_for('crud_blog'))
    
    return render_template('edit_blog.html', blog=blog, enumerate=enumerate)

@app.route('/blog/delete/<blog_id>', methods=['POST'])
@admin_required
def delete_blog(blog_id):
    result = db.blogs.delete_one({'_id': ObjectId(blog_id)})
    if result.deleted_count > 0:
        flash('Blog post deleted successfully!', 'success')
    else:
        flash('Blog post not found!', 'danger')
    return redirect(url_for('crud_blog'))

@app.route('/blog/view/<blog_id>')
@admin_required
def view_blog(blog_id):
    blog = db.blogs.find_one({'_id': ObjectId(blog_id)})
    if blog:
        return render_template('view_blog.html', blog=blog)
    else:
        flash('Blog post not found!', 'danger')
        return redirect(url_for('crud_blog'))
    
@app.route('/archive_item/<blog_id>', methods=['POST'])
@admin_required
def archive_item(blog_id):
    db_collection = db.blogs
    item = db_collection.find_one({"_id": ObjectId(blog_id)})

    if item:
        new_status = not item.get('archived', False)
        db_collection.update_one({"_id": ObjectId(blog_id)}, {"$set": {"archived": new_status}})
        return redirect(url_for('crud_blog'))
    
    return redirect(url_for('crud_blog'))

@app.route('/beranda')
@admin_required
def beranda():   
    return render_template('beranda.html')

@app.route('/form_blog')
@admin_required
def form_blog():
   return render_template('form_blog.html')

@app.route('/')
def home():
   blogs = db.blogs.find({"archived": False}).sort("publication_date", -1).limit(5)
   blogs_list = []
   for blog in blogs:
       blog['_id'] = str(blog['_id'])
       blogs_list.append(blog)
   return render_template('index.html', blogs=blogs_list)

@app.route('/crud_blog')
@admin_required
def crud_blog():
   blogs = db.blogs.find()
   return render_template('crud_blog.html', blogs=blogs)

@app.route('/profil_desa')
def profil_desa():
   return render_template('profil_desa.html')

@app.route('/login_page')
def login_page():
   return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/pemerintahan')
def pemerintahan():
   return render_template('pemerintahan.html')

@app.route('/Visi')
def visi_misi():
   return render_template('Visi.html')

@app.route('/geografis')
def geografis():
   return render_template('geografis.html')

@app.route('/fasilitas')
def fasilitas():
   return render_template('fasilitas.html')

@app.route('/contact')
def contact():
   return render_template('contact.html')

@app.route('/blog')
def blog():
    # Fetch only non-archived blog posts from the database
    blogs = db.blogs.find({"archived": False})
    # Convert ObjectId to string for each blog post
    tags = ['Teknologi', 'Layanan', 'Budaya', 'Karya', 'Kegiatan', 'Informasi']
    tag_counts = {}
    
    for tag in tags:
        tag_counts[tag] = db.blogs.count_documents({"tags": tag, "archived": False})
    
    popular_posts = db.blogs.find({"archived": False}).sort("views", -1).limit(3)
    
    per_page = 5  # Number of blogs per page
    page = int(request.args.get('page', 1))  # Get the current page number from the query string
    skip = (page - 1) * per_page

    # Query the database for blogs
    total_blogs = db.blogs.count_documents({'archived': False})
    blogss = db.blogs.find({'archived': False}).sort('publication_date', DESCENDING).skip(skip).limit(per_page)

    # Calculate total number of pages
    total_pages = ceil(total_blogs / per_page)
    
    blogs_list = []
    for blog in blogs:
        blog['_id'] = str(blog['_id'])
        blogs_list.append(blog)
    return render_template('blog.html', blogs=blogs_list, blogss=blogss, tag_counts=tag_counts, popular_posts=popular_posts, page=page, total_pages=total_pages)

@app.route('/blogs/<string:tag_name>')
def blogs_by_tag(tag_name):
    per_page = 5  # Number of blogs per page
    page = int(request.args.get('page', 1))  # Get the current page number from the query string
    skip = (page - 1) * per_page

    # Query the database for blogs with the specified tag
    blogs = db.blogs.find({'tags': tag_name, 'archived': False}).sort('publication_date', DESCENDING)
    
    blogs_list = list(blogs)
    
    if not blogs_list:  # If no blogs are found, render the 404 page
        return render_template('404.html'), 404
    
    # Get popular posts for sidebar
    popular_posts = db.blogs.find({"archived": False}).sort("views", -1).limit(3)
    
    # Total number of blogs with the specified tag
    total_blogs = db.blogs.count_documents({'tags': tag_name, 'archived': False})
    total_pages = ceil(total_blogs / per_page)
    
    # Calculate total number of pages
    total_pages = ceil(total_blogs / per_page)
    
    # Get the counts of blogs by tags for the sidebar
    tag_counts = {
        tag: db.blogs.count_documents({'tags': tag, 'archived': False})
        for tag in ['Teknologi', 'Layanan', 'Budaya', 'Karya', 'Kegiatan', 'Informasi']
    }

    return render_template('blogs_by_tag.html', 
                           blogs=blogs_list, 
                           tag_counts=tag_counts, 
                           selected_tag=tag_name, 
                           popular_posts=popular_posts, 
                           page=page, 
                           total_pages=total_pages)

@app.route('/blog_detail/<blog_id>')
def blog_detail(blog_id):
    # Fetch the blog post by its _id
    blog = db.blogs.find_one({"_id": ObjectId(blog_id), "archived": False})
    db.blogs.update_one(
        {'_id': ObjectId(blog_id)},
        {'$inc': {'views': 1}}
    )
    
    popular_posts = db.blogs.find({"archived": False}).sort("views", -1).limit(3)
    
    prev_blog = db.blogs.find_one({'_id': {'$lt': ObjectId(blog_id)}, "archived": False}, sort=[('_id', DESCENDING)])
    next_blog = db.blogs.find_one({'_id': {'$gt': ObjectId(blog_id)}, "archived": False}, sort=[('_id', ASCENDING)])
    
    tags = ['Teknologi', 'Layanan', 'Budaya', 'Karya', 'Kegiatan', 'Informasi']
    tag_counts = {}
    
    for tag in tags:
        tag_counts[tag] = db.blogs.count_documents({"tags": tag, "archived": False})
    
    if blog:
        blog['_id'] = str(blog['_id'])  # Convert ObjectId to string for template
        return render_template('blog_detail.html', blog=blog, enumerate=enumerate, prev_blog=prev_blog, next_blog=next_blog, tag_counts=tag_counts, popular_posts=popular_posts)
    else:
        flash('Blog post not found or has been archived.', 'error')
        return redirect(url_for('blog'))

if __name__ == '__main__':  
    app.run('0.0.0.0',port=5000,debug=True)