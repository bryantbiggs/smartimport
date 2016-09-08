'''
Githup API class helper to authenticate login credentials, check API rate limit remaining,
search github repos, and get repo information
'''

import sys
import time
from random import randint
from github import Github


def authenticate_github():
    '''
    Get authenticated access to Github for higher requests limit
    IN: text file containing github token (line1) and user (line2)
    RETURN: authenticated github client object
    '''
    # import github private token
    with open('credentials/token.txt', 'r') as infile:
        token = infile.readline().strip()
        _ = infile.readline().strip()

    git_client = Github(token)

    return git_client


def get_rate_remaining(git_client, _type='core'):
    '''
    IN: term to determine if rate limit for requests (core) or searching (search) is to be returned
            _type => 'core' or 'search'
    RETURN: tuple of remaining rate limit quantity, and time till reset
    '''
    if _type == 'core' or _type == 'search':
        rate_limit = git_client.get_rate_limit()
        raw = dict(rate_limit.raw_data)
        remaining = int(raw['resources'][_type]['remaining'])
    else:
        remaining = 'Wrong input - \"search\" or \"core only\"'

    return remaining


def show_rate_remaining(git_client):
    '''
    IN: None
    RETURN: Printed output of github api rate limits
    '''
    print('Resource rate limit remaining: {0}'.format(
        get_rate_remaining(git_client, 'core')))
    print('Search rate limit remaining: {0}'.format(
        get_rate_remaining(git_client, 'search')))


def check_rate_limit(location, _count=0):
    '''
    IN:
            location => function name (input text) where program paused till rate is reset
            ct => counter to show length of pause in 5 minute intervals
    RETURN:
            None - program will halt here if limit is below buffer threshold and
            continue while it is above/reset
    '''
    # wait till rate limit is refreshed
    rate = get_rate_remaining('core')

    if rate < 150:  # buffer
        print('Stopped @ {0}'.format(location))
    while rate < 150:
        print('Rate: {0} ===> Waiting...{1}'.format(rate, _count))
        time.sleep(300)
        rate = get_rate_remaining('core')
        _count += 5


def get_repo_metadata(repo):
    '''
    IN: github repository object
    RETURN: dictionary with only relevant/desired repo metadata to be uploaded into mongodb
    '''
    repo_keys = ['owner', 'name', 'full_name', 'description', 'fork', 'html_url', 'homepage',
                 'language', 'forks_count', 'size', 'open_issues_count', 'has_issues', 'has_wiki',
                 'has_downloads', 'pushed_at', 'created_at', 'subscribers_count',
                 'stargazers_count']

    owner_keys = ['type', 'login', 'id', 'site_admin']

    # check for rate limit
    check_rate_limit('repo_metadata')

    # get returned payload raw data into dictionary
    raw_dict = dict(repo.raw_data)

    # trim repo by keys listed above
    repo_dict = {k: raw_dict[k] for k in repo_keys}

    # trim owner by keys listed above
    owner_dict = {k: raw_dict['owner'][k] for k in owner_keys}
    repo_dict['owner'] = owner_dict
    repo_dict['_id'] = repo.id

    return repo_dict


def get_repo_subscribers(repo):
    '''
    IN: github repository object
    RETURN: dictionary containing repo subscribers to be uploaded into mongodb
    '''
    # check for rate limit
    check_rate_limit('repo_subscribers')

    repo_dict = {}
    repo_dict['_id'] = repo.id
    repo_dict['repo_fullname'] = repo.full_name
    repo_dict['repo_name'] = repo.name
    repo_dict['repo_owner_login'] = repo.owner.login

    try:
        repo_dict['repo_subscribers'] = [
            f.login for f in repo.get_subscribers()]

    except Exception as _except:
        _ = _except
        repo_dict['repo_subscribers'] = []

    return repo_dict


def get_repo_contributors(repo):
    '''
    IN: github repository object
    RETURN: dictionary containing contributors (login names) keyed by
    repo full_name to be uploaed into mongodb
    '''
    # check for rate limit
    check_rate_limit('repo_contributors')

    repo_dict = {}
    repo_dict['_id'] = repo.id
    repo_dict['repo_fullname'] = repo.full_name
    repo_dict['repo_name'] = repo.name
    repo_dict['repo_owner_login'] = repo.owner.login

    try:
        repo_dict['repo_contributors'] = [
            f.login for f in repo.get_contributors()]

    except Exception as _except:
        _ = _except
        repo_dict['repo_contributors'] = ''

    return repo_dict


def get_user_metadata(user):
    '''
    IN: github NamedUser object
    RETURN: dictionary with only relevant/desired user metadata to be uploaded into mongodb
    '''
    user_keys = ['email', 'followers', 'hireable', 'login', 'bio', 'avatar_url', 'company',
                 'updated_at', 'type', 'created_at', 'name', 'location', 'html_url', 'public_repos',
                 'blog', 'public_gists', 'following']

    # check for rate limit
    check_rate_limit('user_metadata')

    # get returned payload raw data into dictionary
    raw_dict = dict(user.raw_data)

    # trim user by keys listed above
    user_dict = {k: raw_dict[k] for k in user_keys}
    user_dict['_id'] = user.id

    return user_dict


def get_user_following(user):
    '''
    IN: github NamedUser object
    RETURN: dictionary containing users (login names) followed by user
    (passed) to be uploaed into mongodb
    '''
    # check for rate limit
    check_rate_limit('user_following')

    user_dict = {}
    user_dict['_id'] = user.id
    user_dict['login'] = user.login

    try:
        user_dict['user_following'] = [f.login for f in repo.get_following()]

    except Exception as _except:
        _ = _except
        user_dict['user_following'] = []

    return user_dict


def get_user_followers(user):
    '''
    IN: github NamedUser object
    RETURN: dictionary containing users (login names) who follow user
    (passed) to be uploaed into mongodb
    '''
    # check for rate limit
    check_rate_limit('user_followers')

    user_dict = {}
    user_dict['_id'] = user.id
    user_dict['login'] = user.login

    try:
        user_dict['user_followers'] = [f.login for f in repo.get_followers()]

    except Exception as _except:
        _ = _except
        user_dict['user_followers'] = []

    return user_dict


def put_repo_documents(repo, _path='.'):
    '''
    IN:
        repo ==> github repository object
        doc_ct ==> sequential number for 'clean' file names inserted into mongodb
        _path ==> path to folder to extract repository files; '.' is top level repository folder
    RETRUN:
        None - all files from repo except those in the exclusion list will be inserted into mongob
    '''
    # only files with these extensions
    extensions = ['py', 'md', 'rst']

    # grab all contents in the main directory
    dir_contents = repo.get_dir_contents(_path)
    num_files = len(dir_contents)
    repo_fullname = repo.full_name

    # check for rate limit
    check_rate_limit('repo_scripts')

    for content in dir_contents:
        # if item is a directory then recursively navigate lower to get files inside
        if content.type == 'dir':
            put_repo_documents(repo, _path=content.path)

        else:
            # get file extension
            file_ext = content.name.split('.')[-1]

            if file_ext in extensions:
                # try to decode, but return blank if fail
                try:
                    raw_file_content = content.decoded_content.decode(
                        errors='replace')
                except Exception as _except:
                    _ = _except
                    raw_file_content = ''

                # actual file name, mongodb doc stored name
                file_name = content.name
                doc_name = '{0}__{1}'.format(repo.id, file_name)

                # add to collection if under limit (>16mb)
                file_size = sys.getsizeof(raw_file_content)
                if file_size < 16000000:
                    repo_scripts_upsert(
                        repo, file_name, doc_name, raw_file_content, file_ext)
                else:
                    print(
                        'FILE SIZE LIMIT: {0} -- {1}'.format(file_name, file_size))
    return None


def searched_repos(term='python', language='python', _count=0, new_only=True):
    '''
    IN: counter initializer for number of repositories traversed
    RETURN: None (print when finished traversing)
    '''
    for repo in git_client.search_repositories(term, sort='stars', order='desc')[0:10]:
        # ensure its a python tagged dirctory
        if repo.language.lower() == language:
            _count += 1
            put_repo_data(repo, ct, new_only=new_only)
            put_repo_owner(repo, ct, new_only=new_only)

        # don't get cut off
        time.sleep(randint(2, 9))
    return print('DONE')


def get_repos_of_top_repos(_count=0, new_only=True):
    for user_meta in db['git_users_meta'].find():
        git_user = user_meta['login']
        _user = git_client.get_user(git_user)

        for repo in _user.get_repos():
            _count += 1
            put_repo_data(repo, ct, new_only=new_only)

            # don't get cut off
            time.sleep(randint(2, 9))
    return print('DONE')


if __name__ == '__main__':
    pass
