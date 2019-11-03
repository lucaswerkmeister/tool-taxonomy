# -*- coding: utf-8 -*-

import flask
import mwapi
import os
import random
import string
import toolforge
import yaml


app = flask.Flask(__name__)

user_agent = toolforge.set_user_agent(
    'taxonomy',
    email='mail@lucaswerkmeister.de')

__dir__ = os.path.dirname(__file__)
try:
    with open(os.path.join(__dir__, 'config.yaml')) as config_file:
        app.config.update(yaml.safe_load(config_file))
except FileNotFoundError:
    print('config.yaml file not found, assuming local development setup')
    characters = string.ascii_letters + string.digits
    random_string = ''.join(random.choice(characters) for _ in range(64))
    app.secret_key = random_string


@app.template_global()
def csrf_token():
    if 'csrf_token' not in flask.session:
        characters = string.ascii_letters + string.digits
        random_string = ''.join(random.choice(characters) for _ in range(64))
        flask.session['csrf_token'] = random_string
    return flask.session['csrf_token']


@app.template_global()
def form_value(name):
    if 'repeat_form' in flask.g and name in flask.request.form:
        return (flask.Markup(r' value="') +
                flask.Markup.escape(flask.request.form[name]) +
                flask.Markup(r'" '))
    else:
        return flask.Markup()


@app.template_global()
def form_attributes(name):
    return (flask.Markup(r' id="') +
            flask.Markup.escape(name) +
            flask.Markup(r'" name="') +
            flask.Markup.escape(name) +
            flask.Markup(r'" ') +
            form_value(name))


@app.template_filter()
def user_link(user_name):
    user_href = 'https://www.wikidata.org/wiki/User:'
    return (flask.Markup(r'<a href="' + user_href) +
            flask.Markup.escape(user_name.replace(' ', '_')) +
            flask.Markup(r'">') +
            flask.Markup(r'<bdi>') +
            flask.Markup.escape(user_name) +
            flask.Markup(r'</bdi>') +
            flask.Markup(r'</a>'))


@app.route('/taxon/<item_id>')
def taxon(item_id):
    taxon_name, tree = load_taxon_tree(item_id)
    return flask.render_template('taxon.html',
                                 taxon_name=taxon_name,
                                 item_id=item_id,
                                 tree=tree)

def load_taxon_tree(item_id):
    if item_id in flask.g.get('tree_cache', {}):
        return flask.g.tree_cache[item_id]
    taxon_name, parent_taxon_item_ids = load_taxon(item_id)
    d = {}
    for parent_taxon_item_id in parent_taxon_item_ids:
        parent_taxon_item_name, tree = load_taxon_tree(parent_taxon_item_id)
        d[parent_taxon_item_name] = (parent_taxon_item_id, tree)
    flask.g.setdefault('tree_cache', {})[item_id] = taxon_name, d
    return taxon_name, d

def load_taxon(item_id):
    session = mwapi.Session('https://www.wikidata.org', user_agent=user_agent)
    result = session.get(action='wbgetentities',
                         ids=[item_id],
                         props=['claims'])
    entity = result['entities'][item_id]
    try:
        taxon_name_statement = entity['claims']['P225'][0]
        taxon_name = taxon_name_statement['mainsnak']['datavalue']['value']
    except KeyError:
        taxon_name = item_id
    parent_taxon_statements = entity['claims'].get('P171', [])
    parent_taxon_item_ids = {'preferred': [], 'normal': []}
    for parent_taxon_statement in parent_taxon_statements:
        parent_taxon_rank = parent_taxon_statement['rank']
        parent_taxon_mainsnak = parent_taxon_statement['mainsnak']
        if parent_taxon_mainsnak['snaktype'] == 'value':
            parent_taxon_item_id = parent_taxon_mainsnak['datavalue']['value']['id']
            parent_taxon_item_ids[parent_taxon_rank].append(parent_taxon_item_id)
    best_parent_taxon_item_ids = (parent_taxon_item_ids['preferred'] or
                                  parent_taxon_item_ids['normal'])
    return taxon_name, best_parent_taxon_item_ids


@app.route('/', methods=['GET', 'POST'])
def index():
    if flask.request.method == 'POST' and submitted_request_valid():
        return flask.redirect(flask.url_for('taxon', item_id=flask.request.form['item_id']))

    return flask.render_template('index.html')


def full_url(endpoint, **kwargs):
    scheme = flask.request.headers.get('X-Forwarded-Proto', 'http')
    return flask.url_for(endpoint, _external=True, _scheme=scheme, **kwargs)


def submitted_request_valid():
    """Check whether a submitted POST request is valid.

    If this method returns False, the request might have been issued
    by an attacker as part of a Cross-Site Request Forgery attack;
    callers MUST NOT process the request in that case.
    """
    real_token = flask.session.pop('csrf_token', None)
    submitted_token = flask.request.form.get('csrf_token', None)
    if not real_token:
        # we never expected a POST
        return False
    if not submitted_token:
        # token got lost or attacker did not supply it
        return False
    if submitted_token != real_token:
        # incorrect token (could be outdated or incorrectly forged)
        return False
    if not (flask.request.referrer or '').startswith(full_url('index')):
        # correct token but not coming from the correct page; for
        # example, JS running on https://tools.wmflabs.org/tool-a is
        # allowed to access https://tools.wmflabs.org/tool-b and
        # extract CSRF tokens from it (since both of these pages are
        # hosted on the https://tools.wmflabs.org domain), so checking
        # the Referer header is our only protection against attackers
        # from other Toolforge tools
        return False
    return True


# If you don’t want to handle CSRF protection in every POST handler,
# you can instead uncomment the @app.before_request decorator
# on the following function,
# which will raise a very generic error for any invalid POST.
# Otherwise, you can remove the whole function.
# @app.before_request
def require_valid_submitted_request():
    if flask.request.method == 'POST' and not submitted_request_valid():
        return 'CSRF error', 400  # stop request handling
    return None  # continue request handling


@app.after_request
def deny_frame(response):
    """Disallow embedding the tool’s pages in other websites.

    If other websites can embed this tool’s pages, e. g. in <iframe>s,
    other tools hosted on tools.wmflabs.org can send arbitrary web
    requests from this tool’s context, bypassing the referrer-based
    CSRF protection.
    """
    response.headers['X-Frame-Options'] = 'deny'
    return response
