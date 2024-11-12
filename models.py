import requests, re
from flask import current_app
from datetime import datetime, timezone

from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy

bcrypt = Bcrypt()
db = SQLAlchemy()


def connect_db(app):
    """Connect this database to provided Flask app.

    You should call this in your Flask app.
    """

    db.app = app
    db.init_app(app)


from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()

# User Model
class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.Text, nullable=False)
    bio = db.Column(db.Text)
    image_url = db.Column(db.Text, default="/static/images/default-pic.png")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    recipes = db.relationship('Recipe', backref='user', lazy=True)
    favorites = db.relationship('Favorite', backref='user', lazy=True)
    ratings = db.relationship('Rating', backref='user', lazy=True)
    friends = db.relationship('Friend', foreign_keys='[Friend.user_id]', backref='user', lazy=True)
    friend_requests = db.relationship('Friend', foreign_keys='[Friend.friend_id]', backref='friend', lazy=True)
    meal_trades_sent = db.relationship('MealTrade', foreign_keys='[MealTrade.sender_id]', backref='sender', lazy=True)
    meal_trades_received = db.relationship('MealTrade', foreign_keys='[MealTrade.recipient_id]', backref='recipient', lazy=True)

    def __repr__(self):
        return f"<User {self.username}>"
    
    
    @classmethod
    def signup(cls, username, email, password, image_url):
        """Sign up user.

        Hashes password and adds user to system.
        """

        hashed_pwd = bcrypt.generate_password_hash(password).decode('UTF-8')

        user = User(
            username=username,
            email=email,
            password=hashed_pwd,
            image_url=image_url,
        )

        db.session.add(user)
        return user
    

    @classmethod
    def authenticate(cls, username, password):
        """Find user with `username` and `password`.

        This is a class method (call it on the class, not an individual user.)
        It searches for a user whose password hash matches this password
        and, if it finds such a user, returns that user object.

        If can't find matching user (or if password is wrong), returns False.
        """

        user = cls.query.filter_by(username=username).first()

        if user:
            is_auth = bcrypt.check_password_hash(user.password, password)
            if is_auth:
                return user

        return False



# Recipe Model
class Recipe(db.Model):
    __tablename__ = 'recipes'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    spoonacular_id = db.Column(db.Integer, nullable=True)
    title = db.Column(db.String(255), nullable=False)
    ingredients = db.Column(db.Text, nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.Text, default="/static/images/default-food.png")
    source_url = db.Column(db.Text)
    is_public = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    favorites = db.relationship('Favorite', backref='recipe', lazy=True)
    ratings = db.relationship('Rating', backref='recipe', lazy=True)
    meal_trades = db.relationship('MealTrade', backref='recipe', lazy=True)


    def __repr__(self):
        return f"<Recipe {self.title}>"
    
    
    @classmethod
    def get_random_recipes(cls, num=3, include_tags='', exclude_tags=''):
        """Get random recipes from the Spoonacular API"""
        api_key = current_app.config.get('SPOONACULAR_API_KEY')
        if not api_key:
            raise ValueError("API key for Spoonacular not found!")

        url = f"https://api.spoonacular.com/recipes/random?number={num}&apiKey={api_key}"

        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json().get('recipes', [])  

            random_recipes = []
            for recipe in data:
                random_recipes.append({
                "spoonacular_id": recipe.get("id"),
                "title": recipe.get("title"),
                "image": recipe.get("image"),
                "source_url": recipe.get("sourceUrl")
            })

            return random_recipes
        
        except requests.RequestException as e:
            print(f"Error fetching random recipes: {e}")
            return []
        
    
    @classmethod
    def get_recipe_by_id(cls, recipe_id):
        """Fetch full recipe details from Spoonacular by recipe ID"""
        api_key = current_app.config.get('SPOONACULAR_API_KEY')
        if not api_key:
            raise ValueError("API key for Spoonacular not found!")
        
        url = f"https://api.spoonacular.com/recipes/{recipe_id}/information?apiKey={api_key}"

        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            instructions = data.get("instructions", "")

            # Check if instructions contain HTML tags
            if "<ol>" in instructions or "<li>" in instructions:
                # Remove HTML tags and split by sentences or list items
                instructions = re.sub(r'<[^>]+>', '', instructions)
                instructions_list = [step.strip() for step in instructions.split('.') if step.strip()]
            else:
                # Split plain text instructions by sentences
                instructions_list = [sentence.strip() for sentence in instructions.split('.') if sentence.strip()]

            # Format the recipe data
            recipe = {
                "spoonacular_id": data.get("id"),
                "title": data.get("title"),
                "image": data.get("image"),
                "source_url": data.get("sourceUrl"),
                "instructions": instructions_list,
                "ingredients": [ingredient["name"] for ingredient in data.get("extendedIngredients", [])]
            }

            return recipe
        
        except requests.RequestException as e:
            print(f"Error fetching recipe details: {e}")
            return None
        

    @classmethod
    def search_recipes(cls, query):
        """Search for recipes using the Spoonacular API based on a query"""
        
        api_key = current_app.config.get('SPOONACULAR_API_KEY')
        if not api_key:
            raise ValueError("API key for Spoonacular not found!")

        url = f"https://api.spoonacular.com/recipes/complexSearch?query={query}&number=12&apiKey={api_key}"

        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json().get('results', [])

            # Format each recipe result to include spoonacular_id, title, and image
            recipes = []
            for recipe in data:
                recipes.append({
                    "spoonacular_id": recipe.get("id"),
                    "title": recipe.get("title"),
                    "image": recipe.get("image"),
                })

            return recipes
        
        except requests.RequestException as e:
            print(f"Error searching for recipes: {e}")
            return []
        

# Favorite Model
class Favorite(db.Model):
    __tablename__ = 'favorites'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipes.id', ondelete='CASCADE'), nullable=True)
    spoonacular_id = db.Column(db.Integer, nullable=True)
    favorited_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Favorite User {self.user_id} Recipe {self.recipe_id}>"
    

# Friend Model
class Friend(db.Model):
    __tablename__ = 'friends'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    friend_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Friendship User {self.user_id} with User {self.friend_id} - Status: {self.status}>"


# Rating Model
class Rating(db.Model):
    __tablename__ = 'ratings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipes.id', ondelete='CASCADE'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    review = db.Column(db.Text)
    rated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Rating {self.rating} for Recipe {self.recipe_id} by User {self.user_id}>"





# MealTrade Model (Stretch Goal)
class MealTrade(db.Model):
    __tablename__ = 'meal_trades'

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipes.id', ondelete='CASCADE'), nullable=False)
    status = db.Column(db.String(20), default='pending')
    trade_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<MealTrade from User {self.sender_id} to User {self.recipient_id} for Recipe {self.recipe_id} - Status: {self.status}>"


