from flask import flash, session
from flask_login import LoginManager
from sqlalchemy.exc import SQLAlchemyError

from app.models.user import User

# Initialize login manager
login_manager = LoginManager()

# Configure login manager
login_manager.login_view = 'auth.login'  # pyright: ignore
login_manager.login_message = 'Please login first'


# User loader callback for login manager
@login_manager.user_loader
def load_user(user_id):
    try:
        user = User.query.get(int(user_id))
        if user is not None and not user.is_active:
            session.clear()
            return None
        return user
    except ValueError:
        session.clear()
        return None
    except SQLAlchemyError:
        session.clear()
        flash(
            'Your login session could not be validated because the database connection is unavailable. Please sign in again.',  # noqa: E501
            'danger',
        )
        return None
