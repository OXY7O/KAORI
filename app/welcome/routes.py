from __future__ import annotations

from flask import Blueprint, render_template
from flask_login import login_required

from app.welcome.shortcuts import build_welcome_workspace_groups

welcome_bp = Blueprint('welcome', __name__)


@welcome_bp.route('/')
@welcome_bp.route('/welcome')
@login_required
def index():
    workspace_groups = build_welcome_workspace_groups()
    shortcut_count = sum(group['shortcut_count'] for group in workspace_groups)

    return render_template(
        'welcome/index.html',
        workspace_groups=workspace_groups,
        workspace_group_count=len(workspace_groups),
        shortcut_count=shortcut_count,
    )
