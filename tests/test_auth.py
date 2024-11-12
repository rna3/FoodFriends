import unittest
from app import app, CURR_USER_KEY, db
from models import User, Recipe, Favorite
from flask import session, g
from werkzeug.security import generate_password_hash

class AuthTests(unittest.TestCase):
    def setUp(self):
        """Set up test client, initialize database, and create test data."""
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql:///your_test_database'
        app.config['WTF_CSRF_ENABLED'] = False

        # Use app context for database setup
        with app.app_context():
            db.create_all()

            # Create a sample user and keep it bound to the session
            self.test_user = User.signup(
                username="testuser",
                email="test@example.com",
                password="password",
                image_url=None
            )
            db.session.add(self.test_user)
            db.session.commit()

        self.client = app.test_client()

    def tearDown(self):
        """Rollback db session and drop all tables."""
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_login(self):
        """Test logging in with valid credentials."""
        with self.client as client:
            response = client.post('/login', data={
                'username': 'testuser',
                'password': 'password'
            }, follow_redirects=True)

            # Verify the user is now logged in
            self.assertEqual(response.status_code, 200)
            self.assertIn(CURR_USER_KEY, session)
            self.assertEqual(session[CURR_USER_KEY], self.test_user.id)

    def test_logout(self):
        """Test logging out."""
        with self.client as client:
            with app.app_context():
                db.session.add(self.test_user)  # Attach user to session
                with client.session_transaction() as sess:
                    sess[CURR_USER_KEY] = self.test_user.id

            response = client.get('/logout', follow_redirects=True)

            # Check that the user is no longer in session
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(CURR_USER_KEY, session)



class TestRecipeSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up the test client and create a test user"""
        cls.client = app.test_client()
        cls.client.testing = True
        cls.user = User(username="testuser", email="testuser@example.com", password="password")
        db.session.add(cls.user)
        db.session.commit()

    def test_search_recipes_valid(self):
        """Test searching for recipes with a valid query"""
        with self.client as client:
            # Simulate a logged-in user
            with client.session_transaction() as sess:
                sess['CURR_USER_KEY'] = self.user.id

            response = client.post('/search', data={'query': 'chicken'}, follow_redirects=True)

            self.assertEqual(response.status_code, 200)
            self.assertIn('search_results.html', response.get_data(as_text=True))  # Ensure search results page is rendered
            self.assertIn('chicken', response.get_data(as_text=True))  # Check that 'chicken' is in the response

    def test_search_recipes_invalid(self):
        """Test searching for recipes with an invalid query"""
        with self.client as client:
            response = client.post('/search', data={'query': ''}, follow_redirects=True)

            self.assertEqual(response.status_code, 200)
            self.assertIn("Invalid search query!", response.get_data(as_text=True))  # Flash message for invalid query

    @classmethod
    def tearDownClass(cls):
        """Clean up test data"""
        db.session.remove()
        db.drop_all()

if __name__ == '__main__':
    unittest.main()



class TestAddToFavorites(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up the test client and create a test user and recipe"""
        with app.app_context():
            cls.client = app.test_client()
            cls.client.testing = True
            cls.user = User(username="testuser", email="testuser@example.com", password="password")
            cls.recipe = Recipe(title="Chicken Soup", ingredients="chicken, salt", instructions="Boil the chicken.")
            db.session.add(cls.user)
            db.session.add(cls.recipe)
            db.session.commit()

    def test_add_to_favorites_logged_in(self):
        """Test adding a recipe to favorites when logged in"""
        with self.client as client:
            # Simulate a logged-in user
            with client.session_transaction() as sess:
                sess['CURR_USER_KEY'] = self.user.id

            response = client.post('/add_to_favorites', data={'recipe_id': self.recipe.id}, follow_redirects=True)

            self.assertEqual(response.status_code, 200)
            self.assertIn("Recipe added to your favorites!", response.get_data(as_text=True))  # Flash message
            favorite = Favorite.query.filter_by(user_id=self.user.id, recipe_id=self.recipe.id).first()
            self.assertIsNotNone(favorite)  # Ensure the recipe is in the favorites

    def test_add_to_favorites_not_logged_in(self):
        """Test adding a recipe to favorites when not logged in"""
        with self.client as client:
            response = client.post('/add_to_favorites', data={'recipe_id': self.recipe.id}, follow_redirects=True)

            self.assertEqual(response.status_code, 200)
            self.assertIn("You must be logged in to favorite a recipe.", response.get_data(as_text=True))  # Flash message

    def test_add_duplicate_to_favorites(self):
        """Test attempting to add a recipe to favorites when it's already favorited"""
        with self.client as client:
            # Simulate a logged-in user
            with client.session_transaction() as sess:
                sess['CURR_USER_KEY'] = self.user.id

            # Add the recipe to favorites once
            client.post('/add_to_favorites', data={'recipe_id': self.recipe.id}, follow_redirects=True)

            # Attempt to add the same recipe again
            response = client.post('/add_to_favorites', data={'recipe_id': self.recipe.id}, follow_redirects=True)

            self.assertEqual(response.status_code, 200)
            self.assertIn("Recipe is already in your favorites.", response.get_data(as_text=True))  # Flash message

    @classmethod
    def tearDownClass(cls):
        """Clean up test data"""
        db.session.remove()
        db.drop_all()

if __name__ == '__main__':
    unittest.main()