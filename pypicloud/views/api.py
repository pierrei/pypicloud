""" Views for simple api calls that return json data """
from pyramid.httpexceptions import HTTPNotFound, HTTPForbidden, HTTPBadRequest
from pyramid.security import NO_PERMISSION_REQUIRED, remember
from pyramid.view import view_config

from pypicloud.route import (APIResource, APIPackageResource,
                             APIPackagingResource, APIPackageFileResource)
from pyramid_duh import argify, addslash


@view_config(context=APIPackagingResource, request_method='GET',
             subpath=(), renderer='json')
@addslash
@argify
def all_packages(request, verbose=False):
    """ List all packages """
    if verbose:
        packages = request.db.summary()
    else:
        packages = request.db.distinct()
    i = 0
    while i < len(packages):
        package = packages[i]
        name = package if isinstance(package, basestring) else package['name']
        if not request.access.has_permission(name, 'read'):
            del packages[i]
            continue
        i += 1
    return {'packages': packages}


@view_config(context=APIPackageResource, request_method='GET',
             subpath=(), renderer='json', permission='read')
@addslash
def package_versions(context, request):
    """ List all unique package versions """
    versions = request.db.all(context.name)
    return {
        'packages': versions,
        'write': request.access.has_permission(context.name, 'write'),
    }


@view_config(context=APIPackageFileResource, request_method='GET',
             permission='read')
def download_package(context, request):
    """ Download package, or redirect to the download link """
    package = request.db.fetch(context.filename)
    if not package:
        return HTTPNotFound()
    return request.db.download_response(package)


@view_config(context=APIPackageFileResource, request_method='POST',
             subpath=(), renderer='json', permission='write')
@argify
def upload_package(context, request, content):
    """ Upload a package """
    try:
        return request.db.upload(content.filename, content.file,
                                 name=context.name)
    except ValueError as e:  # pragma: no cover
        return HTTPBadRequest(*e.args)


@view_config(context=APIPackageFileResource, request_method='DELETE',
             subpath=(), permission='write')
def delete_package(context, request):
    """ Delete a package """
    package = request.db.fetch(context.filename)
    if package is None:
        return HTTPBadRequest("Could not find %s" % context.filename)
    request.db.delete(package)
    return request.response


@view_config(context=APIResource, name='user', request_method='PUT',
             subpath=('username/*'), renderer='json',
             permission=NO_PERMISSION_REQUIRED)
@argify
def register(request, password):
    """ Register a user """
    if not request.access.allow_register and not request.access.need_admin():
        return HTTPNotFound()
    username = request.named_subpaths['username']
    request.access.register(username, password)
    if request.access.need_admin():
        request.access.approve_user(username)
        request.access.set_user_admin(username, True)
        request.response.headers.extend(remember(request, username))
    return request.response


@view_config(context=APIResource, name='user', subpath=('password'),
             request_method='POST', permission='login')
@argify
def change_password(request, old_password, new_password):
    """ Change a user's password """
    if not request.access.verify_user(request.userid, old_password):
        return HTTPForbidden()
    request.access.edit_user_password(request.userid, new_password)
    return request.response
