import os

from flask import Flask, render_template, request, flash, redirect, session, g, url_for
from dotenv import load_dotenv
from models import db, connect_db, User, Recipe, Favorite, Friend
from forms import UserAddForm, RecipeAddForm, LoginForm, SearchForm
from sqlalchemy.exc import IntegrityError

from flask_bcrypt import Bcrypt

load_dotenv()

CURR_USER_KEY = "curr_user"

app = Flask(__name__)
bcrypt = Bcrypt()

app.config['SQLALCHEMY_DATABASE_URI'] = ('postgresql:///food_friends')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['SPOONACULAR_API_KEY'] = os.getenv('SPOONACULAR_API_KEY')

connect_db(app)

with app.app_context():
    # db.drop_all()
    db.create_all()
    

##############################################################################
# User signup/login/logout


@app.before_request
def add_user_to_g():
    """If we're logged in, add curr user to Flask global."""

    if CURR_USER_KEY in session:
        # Get the user by ID from the database using the session
        g.user = User.query.get(session[CURR_USER_KEY])
    else:
        g.user = None


def do_login(user):
    """Log in user."""

    session[CURR_USER_KEY] = user.id


def do_logout():
    """Logout user."""

    if CURR_USER_KEY in session:
        del session[CURR_USER_KEY]

    session.modified = True


@app.route('/signup', methods=["GET", "POST"])
def signup():
    """Handle user signup.

    Create new user and add to DB. Redirect to home page.

    If form not valid, present form.

    If the there already is a user with that username: flash message
    and re-present form.
    """

    form = UserAddForm()

    if form.validate_on_submit():
        try:
            user = User.signup(
                username=form.username.data,
                password=form.password.data,
                email=form.email.data,
                image_url=form.image_url.data or User.image_url.default.arg,
            )
            db.session.commit()

        except IntegrityError:
            flash("Username already taken", 'danger')
            return render_template('users/signup.html', form=form)

        do_login(user)

        return redirect("/")

    else:
        return render_template('users/signup.html', form=form)
    

@app.route('/login', methods=["GET", "POST"])
def login():
    """Handle user login."""

    form = LoginForm()

    if form.validate_on_submit():
        user = User.authenticate(form.username.data,
                                 form.password.data)

        if user:
            do_login(user)
            flash(f"Hello, {user.username}!", "success")
            return redirect("/")

        flash("Invalid credentials.", 'danger')

    return render_template('users/login.html', form=form)


@app.route('/logout')
def logout():
    """Handle logout of user."""
    # pdb.set_trace()
    do_logout()

    flash("Logged out successful", 'danger')

    return redirect("/login")


##############################################################################
# Site-Homepage


@app.route('/')
def homepage():
    """Show homepage"""

    if g.user:
        form = SearchForm()
        random_recipes = Recipe.get_random_recipes(3)
        return render_template('home.html', form=form, random_recipes=random_recipes)

    else:
        return render_template('home-anon.html')

    
##############################################################################
# User Routes

@app.route('/users')
def find_users():
    """Show page of all users with pagination."""
    page = request.args.get('page', 1, type=int)
    users = User.query.paginate(page=page, per_page=12)  # 12 users per page
    return render_template('/users/all_users.html', users=users)


@app.route('/users/<int:user_id>')
def user_homepage(user_id):
    """Show the profile page for any user, with conditional display for the current user."""

    user = User.query.get_or_404(user_id)  # Get the user being viewed
    created_recipes = Recipe.query.filter_by(user_id=user_id).all()
    favorites = user.favorites

    # Count accepted friends where the user is either user_id or friend_id
    friend_count = Friend.query.filter(
        db.or_(
            (Friend.user_id == user_id) & (Friend.status == 'accepted'),
            (Friend.friend_id == user_id) & (Friend.status == 'accepted')
        )
    ).count()

    # Determine if g.user is friends with this user
    is_friend = False
    if g.user:
        is_friend = Friend.query.filter(
            db.or_(
                (Friend.user_id == g.user.id) & (Friend.friend_id == user_id) & (Friend.status == 'accepted'),
                (Friend.user_id == user_id) & (Friend.friend_id == g.user.id) & (Friend.status == 'accepted')
            )
        ).first() is not None

    # Only show pending friend requests if the logged-in user is viewing their own profile
    pending_requests_info = []
    if g.user and g.user.id == user_id:
        pending_requests = Friend.query.filter_by(friend_id=g.user.id, status='pending').all()
        pending_requests_info = [{'sender': User.query.get(request.user_id)} for request in pending_requests]

    return render_template(
        '/users/user-home.html', 
        user=user, 
        recipes=created_recipes, 
        favorites=favorites, 
        friends=friend_count,
        is_friend=is_friend,  # Pass the friendship status to the template
        pending_requests=pending_requests_info  # Pass pending requests only if viewing own profile
    )


@app.route('/users/<int:user_id>/recipes')
def user_recipes(user_id):
    """Show all recipes created by the user."""
    
    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    recipes = Recipe.query.filter_by(user_id=user.id).all()

    return render_template('users/my-recipes.html', user=user, recipes=recipes)


@app.route('/users/<int:user_id>/favorites')
def user_favorites(user_id):
    """Display the users favorite recipes page"""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    # Retrieve all favorites for the user
    user_favorites = Favorite.query.filter_by(user_id=user_id).all()

    # Separate user-created and Spoonacular favorites
    user_created_favorites = [f for f in user_favorites if f.recipe_id]
    spoonacular_favorites = [f for f in user_favorites if f.spoonacular_id]

    # Ensure that each favorite has the related recipe data
    user_created_favorites = [
        { 'favorite': f, 'recipe': Recipe.query.get(f.recipe_id) } for f in user_created_favorites
    ]
    spoonacular_favorites = [
        { 'favorite': f, 'spoonacular_recipe': Recipe.get_recipe_by_id(f.spoonacular_id) } for f in spoonacular_favorites
    ]

    return render_template(
        'users/favorites.html',
        user=user,
        user_created_favorites=user_created_favorites,
        spoonacular_favorites=spoonacular_favorites
    )


@app.route('/users/<int:user_id>/friends')
def user_friends(user_id):
    """Display the user's friends page."""

    # Ensure the user is logged in and authorized to view the page
    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)

    # Find accepted friends where the current user is either user_id or friend_id
    accepted_friends = db.session.query(User).join(
        Friend,
        db.or_(
            (Friend.user_id == user_id) & (Friend.friend_id == User.id),
            (Friend.friend_id == user_id) & (Friend.user_id == User.id)
        )
    ).filter(Friend.status == 'accepted').all()

    return render_template('users/user_friends.html', user=user, friends=accepted_friends)


@app.route('/favorites/<int:favorite_id>/remove', methods=["POST"])
def remove_favorite(favorite_id):
    """Remove a recipe from the user's favorites."""
    
    favorite = Favorite.query.get_or_404(favorite_id)

    # Ensure the user has permission to delete the favorite
    if favorite.user_id != g.user.id:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    # Delete the favorite
    db.session.delete(favorite)
    db.session.commit()

    flash("Recipe removed from favorites.", "success")
    return redirect(url_for('user_favorites', user_id=g.user.id))


##############################################################################
# Recipe routes:

@app.route('/recipes/new', methods=["GET", "POST"])
def recipes_add():
    """Add a new recipe:
    GET request will show form
    if valid POST request, add recipe to DB and redirect to My Recipes page"""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")
    
    form = RecipeAddForm()

    if form.validate_on_submit():
        recipe = Recipe(
            title=form.title.data,
            ingredients=form.ingredients.data,
            instructions=form.instructions.data,
            image_url=form.image_url.data or "/static/images/default-food.png",
            is_public=form.is_public.data,
            user_id=g.user.id
        )

        db.session.add(recipe)
        db.session.commit()
        flash('Recipe added successfully!', 'success')
        return redirect(f"/users/{g.user.id}/recipes")  # Redirect to user's recipe list
    
    return render_template('recipes/new.html', form=form)


@app.route('/recipes/<int:recipe_id>/delete', methods=["POST"])
def delete_recipe(recipe_id):
    """Delete a recipe."""
    
    recipe = Recipe.query.get_or_404(recipe_id)

    if recipe.user_id != g.user.id:
        flash("Access unauthorized.", "danger")
        return redirect("/")
    
    # Delete any favorites associated with this recipe
    Favorite.query.filter_by(recipe_id=recipe_id).delete()

    db.session.delete(recipe)
    db.session.commit()

    flash(f"Recipe '{recipe.title}' deleted.", "success")
    return redirect(f"/users/{g.user.id}/recipes")


@app.route('/recipes/<int:recipe_id>', methods=['GET'])
@app.route('/recipes/spoonacular/<int:spoonacular_id>', methods=['GET'])
def recipe_detail(recipe_id=None, spoonacular_id=None):
    """Display detailed information about a recipe."""

    if recipe_id:
        # Check if the recipe exists in the FoodFriends database (user-created recipe)
        recipe = Recipe.query.filter_by(id=recipe_id, spoonacular_id=None).first()
        
        if recipe:
            # Render template for user-created recipe
            return render_template('recipes/recipe_detail.html', recipe=recipe, is_user_created=True)

    elif spoonacular_id:
        # Fetch the recipe from Spoonacular API using the spoonacular_id
        api_recipe = Recipe.get_recipe_by_id(spoonacular_id)
        
        if api_recipe:
            return render_template('recipes/recipe_detail.html', recipe=api_recipe, is_user_created=False)

    flash("Recipe not found.", "danger")
    return redirect(url_for('homepage'))


##############################################################################
# General function routes:

@app.route('/search', methods=["GET", "POST"])
def search_recipes():
    """Search for recipes from Spoonacular API"""
    
    form = SearchForm()

    if form.validate_on_submit():
        query = form.query.data.strip()  # Get the search query from the form

        # Fetch search results from Spoonacular
        search_results = Recipe.search_recipes(query)

        return render_template('search_results.html', query=query, recipes=search_results, form=form)
    
    flash("Invalid search query!", "danger")
    return redirect(url_for('homepage'))


@app.route('/search-users', methods=["GET", "POST"])
def search_users():
    """Search for users by username."""
    
    query = request.args.get("query")
    page = request.args.get("page", 1, type=int)
    
    # Query users with a filter based on the search term
    users = User.query.filter(User.username.ilike(f"%{query}%")).paginate(page=page, per_page=12)

     # Debugging: Print the count of retrieved users
    print(f"Query: {query}, Users Found: {users.total}")
    
    return render_template('/users/all_users.html', users=users, search_query=query)




@app.route('/add_to_favorites', methods=['POST'])
def add_to_favorites():
    if not g.user:
        flash("You must be logged in to favorite a recipe.", "danger")
        return redirect(url_for('login'))

    # Get recipe_id and spoonacular_id from form data and convert empty strings to None
    recipe_id = request.form.get('recipe_id') or None
    spoonacular_id = request.form.get('spoonacular_id') or None

    # Check if the recipe is already favorited
    favorite = None
    if recipe_id:
        favorite = Favorite.query.filter_by(user_id=g.user.id, recipe_id=recipe_id).first()
    elif spoonacular_id:
        favorite = Favorite.query.filter_by(user_id=g.user.id, spoonacular_id=spoonacular_id).first()

    if favorite:
        flash("Recipe is already in your favorites.", "info")
    else:
        # Create a new Favorite entry, passing None where fields are empty
        new_favorite = Favorite(
            user_id=g.user.id,
            recipe_id=recipe_id if recipe_id else None,
            spoonacular_id=spoonacular_id if spoonacular_id else None,
        )
        db.session.add(new_favorite)
        db.session.commit()
        
        flash("Recipe added to your favorites!", "success")

    return redirect(request.referrer or url_for('homepage'))


@app.route('/users/<int:user_id>')
def show_user(user_id):
    """Show the profile page for a specific user."""
    user = User.query.get_or_404(user_id)
    
    # Retrieve the user's recipes, favorites, and friends
    recipes = user.recipes  # Assuming User has a relationship with Recipe
    favorites = user.favorites  # Assuming User has a relationship with Favorite
    friends = user.friends  # Assuming User has a relationship with Friend

    return render_template('user-home.html', user=user, recipes=recipes, favorites=favorites, friends=friends)


##############################################################################
# Friend Request routes:


@app.route('/users/<int:friend_id>/add', methods=['POST'])
def add_friend(friend_id):
    """Send a friend request to another user."""
    if not g.user:
        flash("You need to be logged in to add friends.", "danger")
        return redirect(url_for('login'))

    existing_friendship = Friend.query.filter_by(user_id=g.user.id, friend_id=friend_id).first()
    if existing_friendship:
        flash("Friend request already sent.", "warning")
    else:
        new_friendship = Friend(user_id=g.user.id, friend_id=friend_id)
        db.session.add(new_friendship)
        db.session.commit()
        flash("Friend request sent!", "success")

    return redirect(url_for('find_users'))


# Route to accept a friend request
@app.route('/users/<int:friend_id>/accept', methods=['POST'])
def accept_friend(friend_id):
    """Accept a friend request."""
    if not g.user:
        flash("You need to be logged in to accept friend requests.", "danger")
        return redirect(url_for('login'))
    
    friend_request = Friend.query.filter_by(user_id=friend_id, friend_id=g.user.id, status='pending').first()
    if friend_request:
        friend_request.status = 'accepted'
        db.session.commit()
        flash("Friend request accepted!", "success")
    else:
        flash("No pending friend request found.", "warning")

    return redirect(url_for('user_homepage', user_id=g.user.id))

# Route to reject a friend request
@app.route('/users/<int:friend_id>/reject', methods=['POST'])
def reject_friend(friend_id):
    """Reject a friend request."""
    if not g.user:
        flash("You need to be logged in to reject friend requests.", "danger")
        return redirect(url_for('login'))
    
    friend_request = Friend.query.filter_by(user_id=friend_id, friend_id=g.user.id, status='pending').first()
    if friend_request:
        db.session.delete(friend_request)
        db.session.commit()
        flash("Friend request rejected.", "info")
    else:
        flash("No pending friend request found.", "warning")

    return redirect(url_for('user_homepage', user_id=g.user.id))
