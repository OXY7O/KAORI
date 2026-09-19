from __future__ import annotations

from flask import Blueprint, redirect, request, url_for
from flask.typing import ResponseReturnValue

bp = Blueprint('data_lifecycle', __name__)


def _redirect(endpoint: str, **values) -> ResponseReturnValue:
    if request.method == 'GET':
        values.update(request.args.to_dict(flat=True))
        return redirect(url_for(endpoint, **values), code=302)
    return redirect(url_for(endpoint, **values), code=308)


@bp.get('/')
def index() -> ResponseReturnValue:
    return _redirect('platform_operations.data_lifecycle.index')


@bp.get('/preview')
def preview() -> ResponseReturnValue:
    return _redirect('platform_operations.data_lifecycle.preview')


@bp.post('/policy')
def save_policy() -> ResponseReturnValue:
    return _redirect('platform_operations.data_lifecycle.save_policy')


@bp.post('/run')
def run() -> ResponseReturnValue:
    return _redirect('platform_operations.data_lifecycle.run')


@bp.post('/archives/<archive_id>/verify')
def verify(archive_id: str) -> ResponseReturnValue:
    return _redirect('platform_operations.data_lifecycle.verify', archive_id=archive_id)


@bp.get('/archives/<archive_id>/download')
def download(archive_id: str) -> ResponseReturnValue:
    return _redirect('platform_operations.data_lifecycle.download', archive_id=archive_id)
