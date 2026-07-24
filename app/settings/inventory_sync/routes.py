from __future__ import annotations

from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user

from app.inventory.schedule import get_inventory_sync_policy, update_inventory_sync_policy
from app.notifications.service import record_operational_activity
from app.rbac.decorators import permission_required
from app.settings.inventory_sync.forms import InventorySyncPolicyForm

bp = Blueprint('inventory_sync', __name__)


@bp.route('/', methods=['GET', 'POST'])
@permission_required('settings.manage_integrations')
def index():
    policy = get_inventory_sync_policy()
    form = InventorySyncPolicyForm()
    if form.validate_on_submit():
        policy = update_inventory_sync_policy(
            enabled=bool(form.enabled.data),
            interval_minutes=int(form.interval_minutes.data or 60),
            user_id=current_user.id,
        )
        record_operational_activity(
            user_id=current_user.id,
            event_type='inventory_sync_policy_updated',
            status='success',
            title='Inventory sync configuration updated',
            message=(
                f'Automatic inventory sync runs every {policy.interval_minutes} minutes.'
                if policy.enabled
                else 'Automatic inventory sync is disabled.'
            ),
            metadata={'enabled': policy.enabled, 'interval_minutes': policy.interval_minutes},
        )
        return redirect(url_for('settings.inventory_sync.index'))
    if not form.is_submitted():
        form.enabled.data = policy.enabled
        form.interval_minutes.data = policy.interval_minutes
    return render_template('settings/inventory_sync/index.html', form=form, policy=policy)
