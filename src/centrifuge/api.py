# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.
#
import uuid
import time
import logging
import motor
from bson import ObjectId
from tornado.gen import Task, coroutine, Return
from . import auth


def on_error(error):
    """
    General error wrapper.
    """
    logging.error(str(error))
    raise Return((None, error))


def ensure_indexes(sync_db, drop=False):
    if drop:
        logging.info('dropping indexes...')
        sync_db.user.drop_indexes()
        sync_db.project.drop_indexes()
        sync_db.category.drop_indexes()

    logging.info('ensuring indexes...')

    sync_db.user.ensure_index([('email', 1)], unique=True)
    sync_db.project.ensure_index([('name', 1)], unique=True)
    sync_db.category.ensure_index([('name', 1), ('project', 1)], unique=True)

    logging.info('ensuring indexes DONE')


def prepare_db_backend(settings):
    """
    Create MongoDB connection, ensure indexes
    """
    mongo = motor.MotorClient(
        host=settings.get("host", "localhost"),
        port=settings.get("port", 27017),
        max_pool_size=settings.get("max_pool_size", 10)
    ).open_sync()[settings.get("name", "centrifuge")]

    ensure_indexes(mongo)

    return mongo


def extract_obj_id(obj):
    if isinstance(obj, dict):
        obj_id = obj['_id']
    else:
        obj_id = obj
    return obj_id


@coroutine
def insert(collection, data):
    """
    Insert data into collection.
    """
    if 'created_at' not in data:
        data['created_at'] = int(time.time())
    if 'is_active' not in data:
        data['is_active'] = True
    (result, error), _ = yield Task(collection.insert, data)
    if error:
        on_error(error)

    raise Return((result, None))


@coroutine
def find(collection, haystack):
    """
    Find objects in MongoDB collection by haystack.
    """
    cursor = collection.find(haystack, limit=10000)
    (objects, error), _ = yield Task(cursor.to_list)
    if error:
        on_error(error)

    raise Return((objects, None))


@coroutine
def update(collection, haystack, update_data):
    """
    Update entries matching haystack with update_data.
    """
    if 'updated_at' not in update_data:
        update_data['updated_at'] = int(time.time())
    (result, error), _ = yield Task(
        collection.update, haystack, {"$set": update_data}
    )
    if error:
        on_error(error)
    raise Return((result, None))


@coroutine
def find_one(collection, haystack):
    """
    Find object in MongoDB collection.
    """
    (obj, error), _ = yield Task(collection.find_one, haystack)
    if error:
        on_error(error)
    if not obj:
        raise Return((None, None))
    raise Return((obj, None))


@coroutine
def remove(collection, haystack):
    """
    Find object in MongoDB collection.
    """
    (res, error), _ = yield Task(collection.remove, haystack)
    if error:
        on_error(error)

    raise Return((res, None))


@coroutine
def find_one_or_create(collection, haystack):
    """
    First try to find object by haystack, create new if not found.
    """
    obj, error = yield find_one(collection, haystack)
    if error:
        on_error(error)

    if not obj:
        obj_id = str(ObjectId())
        haystack['_id'] = obj_id
        result, error = yield insert(collection, haystack)
        if error:
            on_error(error)
        obj = haystack

    raise Return((obj, None))


@coroutine
def get_obj_related_items(
        relation_collection, item_collection, obj,
        obj_name, item_name, relation_key):
    """
    This is helpful for managing many-to-many-like relations.
    """
    obj_id = extract_obj_id(obj)
    relation_entries, error = yield find(
        relation_collection,
        {obj_name: obj_id, 'is_active': True}
    )
    if error:
        on_error(error)

    entry_dict = {}
    for entry in relation_entries:
        entry_dict[entry[item_name]] = entry

    items, error = yield find(
        item_collection,
        {'_id': {'$in': entry_dict.keys()}}
    )
    if error:
        on_error(error)

    for item in items:
        item[relation_key] = entry_dict[item['_id']]

    raise Return((items, None))


@coroutine
def get_or_create_user(db, email, first_name, last_name, locale):
    """
    Get user by email and return it's data if user exists.
    Otherwise create new user using provided arguments.
    """
    user_data, error = yield find_one(db.user, {'email': email})
    if error:
        on_error(error)

    if not user_data:
        user_data = {
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'locale': locale,
            '_id': str(ObjectId())
        }
        res, error = yield insert(db.user, user_data)
        if error:
            on_error(error)

    raise Return((user_data, None))


@coroutine
def get_project_key_by_public_key(db, public_key):

    project_key, error = yield find_one(
        db.projectkey,
        {'public_key': public_key}
    )
    if error:
        on_error(error)
    raise Return((project_key, None))


@coroutine
def check_auth(db, project, public_key, sign, encoded_data):
    """
    Authenticate incoming request. Make sure that it has all rights
    to create new events in specified project.
    """
    assert isinstance(project, dict)

    project_key, error = yield get_project_key_by_public_key(
        db, public_key
    )
    if error:
        on_error(error)

    if not project_key or project_key.get('readonly', True):
        raise Return((None, 'permission denied'))

    is_authenticated = auth.check_sign(
        project_key['secret_key'],
        project['_id'],
        encoded_data,
        sign
    )
    if not is_authenticated:
        raise Return((None, None))

    user_id = project_key['user']
    user, error = yield find_one(db.user, {'_id': user_id})
    if error:
        on_error(error)

    if not user:
        raise Return((None, None))

    raise Return((user, None))


@coroutine
def get_user_by_email(db, email):
    user, error = yield find_one(db.user, {'email': email})
    if error:
        on_error(error)
    raise Return((user, None))


@coroutine
def get_user_by_id(db, user_id):
    user, error = yield find_one(db.user, {'_id': user_id})
    if error:
        on_error(error)
    raise Return((user, None))


@coroutine
def get_project_by_name(db, project_name):
    project, error = yield find_one(db.project, {'name': project_name})
    if error:
        on_error(error)
    raise Return((project, None))


@coroutine
def get_project_by_id(db, project_id):
    project, error = yield find_one(db.project, {'_id': project_id})
    if error:
        on_error(error)
        return
    raise Return((project, None))


@coroutine
def get_user_project_key(db, user, project):
    user_id = extract_obj_id(user)
    project_id = extract_obj_id(project)
    haystack = {
        'project': project_id,
        'user': user_id
    }
    project_key, error = yield find_one(db.projectkey, haystack)
    if error:
        on_error(error)
        return
    raise Return((project_key, None))


@coroutine
def get_project_owner(db, project):
    assert isinstance(project, dict)
    user_id = project['user']
    owner, error = yield find_one(db.user, {'_id': user_id})
    if error:
        on_error(error)
        return
    raise Return((owner, None))


@coroutine
def get_user_projects(db, user):
    """
    Get all projects user can see.
    """
    projects, error = yield get_obj_related_items(
        db.projectkey,
        db.project,
        user,
        'user',
        'project',
        'project_key'
    )
    raise Return((projects, error))


@coroutine
def get_project_users(db, project):
    users, error = yield get_obj_related_items(
        db.projectkey,
        db.user,
        project,
        'project',
        'user',
        'project_key'
    )
    if error:
        on_error(error)
        return
    raise Return((users, None))


@coroutine
def get_project_categories(db, project):
    project_id = extract_obj_id(project)
    categories, error = yield find(db.category, {'project': project_id})
    if error:
        on_error(error)
        return
    raise Return((categories, None))


@coroutine
def check_event_uniqueness(db, channel, event_data, unique_keys):
    """
    Sometimes we should avoid creating duplicate events. For this
    purpose every incoming event can have `unique_keys` key. This
    is a list event_data's keys which must be unique for specified
    event key.
    """
    haystack = {
        'channel': channel
    }
    for key in unique_keys:
        if key in event_data:
            haystack['data.%s' % key] = event_data[key]
    matches, error = yield find(db.event, haystack)
    if error:
        on_error(error)
        return
    if matches:
        raise Return((False, None))

    raise Return((True, None))


@coroutine
def project_create(db, user, project_name, display_name, validate_url, description):
    user_id = extract_obj_id(user)
    project_id = str(ObjectId())
    to_insert = {
        '_id': project_id,
        'owner': user_id,
        'name': project_name,
        'display_name': display_name,
        'validate_url': validate_url,
        'description': description
    }
    result, error = yield insert(db.project, to_insert)
    if error:
        on_error(error)
        return
    raise Return((to_insert, None))


@coroutine
def project_delete(db, project):
    """
    Delete project. Also delete all related categories and events.
    """
    haystack = {
        '_id': project['_id']
    }
    _res, error = yield remove(db.project, haystack)
    if error:
        on_error(error)

    haystack = {
        'project': project['_id']
    }
    _res, error = yield remove(db.category, haystack)
    if error:
        on_error(error)

    _res, error = yield remove(db.projectkey, haystack)
    if error:
        on_error(error)

    raise Return((True, None))


@coroutine
def project_edit(db, project, name, display_name, validate_url, description):
    """
    Edit project
    """
    to_update = {
        'name': name,
        'display_name': display_name,
        'validate_url': validate_url,
        'description': description
    }
    _res, error = yield update(
        db.project,
        {'_id': project['_id']},
        to_update
    )
    if error:
        on_error(error)

    raise Return((True, None))


@coroutine
def category_create(
        db,
        project,
        category_name,
        bidirectional=False,
        save_events=False,
        publish_to_admins=False):

    haystack = {
        '_id': str(ObjectId()),
        'project': project['_id'],
        'name': category_name,
        'bidirectional': bidirectional,
        'save_events': save_events,
        'publish_to_admins': publish_to_admins
    }
    category, error = yield insert(db.category, haystack)
    if error:
        on_error(error)

    raise Return((category, None))


@coroutine
def category_delete(db, project, category_name):
    """
    Delete category from project. Also delete all related entries from
    event collection.
    """
    category, error = yield get_project_category(db, project, category_name)

    if not category:
        raise Return((True, None))

    haystack = {
        'project': project['_id'],
        '_id': category['_id']
    }
    _res, error = yield remove(db.category, haystack)
    if error:
        on_error(error)

    raise Return((True, None))


@coroutine
def is_user_in_project(db, user, project):
    user_projects, error = yield get_user_projects(db, user)
    if error:
        on_error(error)

    for user_project in user_projects:
        if user_project['name'] == project['name']:
            raise Return((True, None))

    raise Return((False, None))


@coroutine
def generate_project_keys(db, user_id, project_id, readonly):
    """
    Create secret and public keys for user in specified project.
    """
    project_key_id = str(ObjectId())
    to_insert = {
        '_id': project_key_id,
        'project': project_id,
        'user': user_id,
        'public_key': uuid.uuid4().hex,
        'secret_key': uuid.uuid4().hex,
        'readonly': readonly
    }
    result, error = yield insert(db.projectkey, to_insert)
    if error:
        on_error(error)

    raise Return((to_insert, None))


@coroutine
def regenerate_project_keys(db, user, project):
    """
    Create new secret and public keys for user in specified project.
    """
    user_id = extract_obj_id(user)
    project_id = extract_obj_id(project)
    haystack = {
        'user': user_id,
        'project': project_id
    }
    update_data = {
        'public_key': uuid.uuid4().hex,
        'secret_key': uuid.uuid4().hex
    }
    result, error = yield update(db.projectkey, haystack, update_data)
    if error:
        on_error(error)

    raise Return((update_data, None))


@coroutine
def add_user_into_project(db, user, project, readonly):

    user_id = extract_obj_id(user)
    project_id = extract_obj_id(project)

    haystack = {
        'project': project_id,
        'user': user_id
    }

    project_key, error = yield find_one(db.projectkey, haystack)
    if error:
        on_error(error)

    if not project_key:
        project_key, error = yield generate_project_keys(
            db, user_id, project_id, readonly
        )
        if error:
            on_error(error)

    elif not project_key.get('is_active', False):
        to_update = {
            'is_active': True,
            'readonly': readonly
        }
        _res, error = yield update(db.projectkey, haystack, to_update)
        if error:
            on_error(error)

    raise Return((project_key, None))


@coroutine
def del_user_from_project(db, user, project):
    user_id = extract_obj_id(user)
    project_id = extract_obj_id(project)
    haystack = {
        'project': project_id,
        'user': user_id
    }
    project_key, error = yield find_one(db.projectkey, haystack)
    if error:
        on_error(error)

    if project_key:
        update_data = {'is_active': False, 'readonly': True}
        res, error = yield update(db.projectkey, haystack, update_data)
        if error:
            on_error(error)

    raise Return((project_key, None))


@coroutine
def get_project_category(db, project, category_name):
    """
    Find category by name for project.
    """
    haystack = {
        'project': project['_id'],
        'name': category_name
    }
    category, error = yield find_one(db.category, haystack)
    if error:
        on_error(error)

    raise Return((category, None))


@coroutine
def get_categories_for_projects(db, projects):
    """
    pass
    """
    project_ids = [extract_obj_id(x) for x in projects]
    haystack = {
        "project": {"$in": project_ids}
    }

    categories, error = yield find(db.category, haystack)
    if error:
        on_error(error)

    to_return = {}

    for category in categories:
        if category['project'] not in to_return:
            to_return[category['project']] = []
        to_return[category['project']].append(category)

    raise Return((to_return, None))


@coroutine
def save_event(db, event):
    result, error = yield insert(db.event, event)
    if error:
        on_error(error)

    raise Return((result, None))