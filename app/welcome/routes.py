from __future__ import annotations

from flask import Blueprint, render_template
from flask_login import login_required

from app.welcome.shortcuts import build_welcome_shortcuts

welcome_bp = Blueprint('welcome', __name__)


@welcome_bp.route('/')
@welcome_bp.route('/welcome')
@login_required
def index():
    shortcuts = build_welcome_shortcuts()
    return render_template(
        'welcome/index.html',
        shortcuts=shortcuts,
        shortcut_count=len(shortcuts),
    )
