from __future__ import annotations

from flask import Blueprint, redirect, request, url_for

bp = Blueprint('access_compat', __name__)


def _redirect(endpoint: str, **values: int):
    status_code = 308 if request.method != 'GET' else 302
    return redirect(url_for(endpoint, **values), code=status_code)


@bp.get('/roles')
def roles():
    return _redirect('access.roles.index')


@bp.route('/roles/new', methods=['GET', 'POST'])
def new_role():
    return _redirect('access.roles.create')


@bp.route('/roles/<int:role_id>/clone', methods=['GET', 'POST'])
def clone_role(role_id: int):
    return _redirect('access.roles.clone', role_id=role_id)


@bp.get('/roles/<int:role_id>')
def role_detail(role_id: int):
    return _redirect('access.roles.detail', role_id=role_id)


@bp.route('/roles/<int:role_id>/edit', methods=['GET', 'POST'])
def edit_role(role_id: int):
    return _redirect('access.roles.edit', role_id=role_id)


@bp.post('/roles/<int:role_id>/delete')
def delete_role(role_id: int):
    return _redirect('access.roles.delete', role_id=role_id)


@bp.get('/permissions')
def permission_catalog():
    return _redirect('access.permissions.index')
