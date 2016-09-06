
import os
import sys
import re
import time
from pymongo import MongoClient
from random import randint
from pprint import pprint


def connect_mongo(pw_file):
	'''
	IN: text file containing mongo instance public ip, mongo username, and mongo user password
	RETURN: mongo github database instance
	'''
	# credentials
	pw_file = 'credentials/mongo_pw.txt'
	if os.path.exists(pw_file): 
		with open(pw_file, 'r') as f:
			pub_ip, mongo_usr, mongo_usr_pw = f.readline().strip().split(', ')

	# connect to ec2 mongo client
	client = MongoClient('{0}:27017'.format(pub_ip))

	# get reference to  resume_db
	db = client['github_db']

	# authenticate user for database
	db.authenticate(mongo_usr, mongo_usr_pw)

	return db

def initialize_collections(db, reset=False):
	'''
	IN: 
		db ==> mongo database instance
		reset ==> if reset is true, all collections in database will be deleted and re-initalized to zero
	RETURN: None - collections will either all be initailized to zero or left untouched
	'''
	# drop collections if reset is set to True
	if reset:
		for name in db.collection_names():
			db.drop_collection(name)
			
	# create a collection in the 'github_db' database (not required but helpful)
	lst_collections = ['git_users_meta', 'git_users_following', 'git_users_followers', 
					   'git_repos_meta', 'git_repos_docs', 'git_repos_subscribers', 'git_repos_contributors']

	# initialize blank collections
	for collection in lst_collections:
		if collection not in db.collection_names():
			db.create_collection(collection)

def show_collections(db):
	'''
	IN: None
	RETURN: Printed output of collections and collection counts
	'''
	for name in sorted(db.collection_names()):
		print('Documents in \"{0}\" collection: {1}'.format(name, db[name].count()))

def copy_db(current_db, new_db):
	# Copy MongoDB database
	'''
	IN: 
		current_db ==> current database with information to be copied to new_db
		new_db ==> new database to be created and populated with data from current_db
	RETURN: None
	'''
	r = client.admin.command('copydb', fromdb=current_db, todb=new_db)
	if r['ok'] == 1.0:
		return print('DB {0} created'.format(new_db))

def upsert_repo_metadata(repo):
	'''
	IN: github repository object
	RETURN: None - data returned from repo_metadata function is inserted into mongodb
	'''
	col = db['git_repos_meta']
	try:
		col.update_one(
			{'_id': repo.id}, 
			{'$set':{col.insert_one(get_repo_metadata(repo))}}, 
			upsert=True)
	except:
		pass
	return None

def upsert_repo_subscribers(repo):
	'''
	IN: github repository object
	RETURN: None - data returned from repo_subscribers function is inserted into mongodb
	'''
	col = db['git_repos_subscribers']
	try:
		col.update_one(
			{'_id': repo.id}, 
			{'$set': {col.insert_one(get_repo_subscribers(repo))}
			}, upsert=True)
	except:
		pass
	return None

def upsert_repo_contributors(repo):
	'''
	IN: github repository object
	RETURN: None - data returned from repo_contributors function is inserted into mongodb
	'''
	col = db['git_repos_contributors']
	try:
		col.update_one(
			{'_id': repo.id}, 
			{'$set': {col.insert_one(get_repo_contributors(repo))}
			}, upsert=True)
	except:
		pass
	return None

def upsert_user_metadata(user):
	'''
	IN: github NamedUser object
	RETURN: None - data returned from user_metadata function is inserted into mongodb
	'''
	col = db['git_users_meta']
	try:
		col.update_one(
			{'_id': user.id}, 
			{'$set':{col.insert_one(get_user_metadata(user))}}, 
			upsert=True)
	except:
		pass
	return None

def upsert_user_following(user):
	'''
	IN: github NamedUser object
	RETURN: None - data returned from user_following function is inserted into mongodb
	'''
	col = db['git_users_following']
	try:
		col.update_one(
			{'_id': user.id}, 
			{'$set': {col.insert_one(get_user_following(user))}
			}, upsert=True)
	except:
		pass
	return None

def upsert_user_followers(user):
	'''
	IN: github NamedUser object
	RETURN: None - data returned from user_followers function is inserted into mongodb
	'''
	col = db['git_users_followers']
	try:
		col.update_one(
			{'_id': user.id}, 
			{'$set': {col.insert_one(get_user_followers(user))}
			}, upsert=True)
	except:
		pass
	return None

def upsert_repo_scripts(repo, file_name, doc_name, raw_file_cont, file_ext):
	'''
	IN: 
		repo ==> github repository object
		file_name ==> file name pulled from github repo
		raw_file_contnet ==> raw file contents of file_name
		file_ext ==> file extension of file_name
	RETURN: 
		None - file details/information uploaded into mongodb
	'''
	try:
		db['git_repos_docs'].update_one(
			{'doc_name' : doc_name}, 
			{'$set':{
					'file_name': file_name,
					'file_contents': raw_file_cont,
					'file_extension': file_ext,
					'repo_fullname' : repo.full_name,
					'repo_id' : repo.id,
					'repo_name' : repo.name,
					'repo_owner_login' : repo.owner.login,
					'doc_name' : doc_name}
				}, 
			upsert=True)
	except:
		pass
	return None

def put_repo_data(repo, ct, new_only=True):
	'''
	IN: 
		repo ==> github repository object
		ct ==> repository counter
		new_only ==> True if only new repos are to be added, False if add all (new/existing)
	RETURN: None - all desired repository data uploaded to mongodb
	'''
	if new_only:
		if db['git_repos_meta'].find({'full_name': repo.full_name}).count() == 0:
			print('Repo (new).....#{0} - {1}'.format(ct, repo.full_name))
			put_repo_documents(repo)
			upsert_repo_metadata(repo)
			upsert_repo_subscribers(repo)
			upsert_repo_contributors(repo)

	else:
		print('Repo (all).....#{0} - {1}'.format(ct, repo.full_name))
		put_repo_documents(repo)
		upsert_repo_metadata(repo)
		upsert_repo_subscribers(repo)
		upsert_repo_contributors(repo)
		
	return None

def put_repo_owner(repo, ct, new_only=True):
	'''
	IN: github repository object
		repo ==> github repository object
		ct ==> repository counter
		new_only ==> True if only new repos are to be added, False if add all (new/existing)
	RETURN: None - all desired data pertaining to repository owner uploaded to mongodb
	'''
	user = repo.owner
	if new_only:
		if db['git_users_meta'].find({'_id': user.id}).count() == 0:
			print('Repo owner (new).....#{0} - {1}'.format(ct, user.login))
			upsert_user_metadata(user)
			upsert_user_following(user)
			upsert_user_followers(user)

	else:
		print('Repo owner (all).....#{0} - {1}'.format(ct, user.login))
		upsert_user_metadata(user)
		upsert_user_following(user)
		upsert_user_followers(user)


if __name__ == '__main__':
	pass