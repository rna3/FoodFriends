from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional, URL
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()

class LoginForm(FlaskForm):
    """Login form."""

    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[Length(min=6)])


class UserAddForm(FlaskForm):
    """Form for adding users."""

    username = StringField('Username', validators=[DataRequired()])
    email = StringField('E-mail', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[Length(min=6)])
    image_url = StringField('(Optional) Profile Image URL')


class RecipeAddForm(FlaskForm):
    """Form for adding a recipe"""

    title = StringField('Recipe Title', validators=[DataRequired()])
    ingredients = TextAreaField('Ingredients', validators=[DataRequired()])
    instructions = TextAreaField('Instructions', validators=[DataRequired()])
    image_url = StringField('Image URL', validators=[Optional(), URL()])
    is_public = BooleanField('Make recipe public?', default=True)


class SearchForm(FlaskForm):
    """Form for searching recipes"""
    query = StringField('Search', validators=[DataRequired()])
    submit = SubmitField('Search')
