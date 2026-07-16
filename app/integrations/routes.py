from flask import Blueprint, render_template
from flask.typing import ResponseReturnValue

from app.integrations.service import build_integrations_overview
from app.rbac.decorators import permission_required

integrations_bp = Blueprint('integrations', __name__, url_prefix='/integrations')


@integrations_bp.get('/')
@permission_required('settings.manage_integrations')
def overview() -> ResponseReturnValue:
    return render_template('integrations/overview.html', **build_integrations_overview())
