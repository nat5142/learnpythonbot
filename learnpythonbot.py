################################################################################
# learnpythonbot.py | Created 2018/01/26									   #
#																			   #
# Author: Nicholas Tulli (nat5142 [at] psu [dot] edu)						   #
#																			   #
# This script is responsible for the content of Twitter user @learnpythonbot.  #
# Running via an every-minute crontab, this script will use the Python-Reddit  #
# API Wrapper (praw) to find new posts to the subreddit /r/learnpython, and    #
# tweet the content and URL of each.										   #
#																			   #
# In addition to tweets, the script also collects and logs information about   #
# the posts' body and title in a MySQL database.							   #
#																			   #
# Developed for Python 3.6													   #
################################################################################

# ------- MODULE LIBRARY ------- #
import re
import time
import tweepy
import os
import json
import praw
import mysql.connector
# ------------------------------ #


# load credentials from JSON file
tokenPath = "./credentials.json"
tokens = os.path.expanduser(tokenPath)
with open(tokens) as t:
	credentials = json.load(t)

# load database connection information
databaseTokenPath = '~/Desktop/Code/dbAccess.json'
dTokens = os.path.expanduser(databaseTokenPath)
with open(dTokens) as d:
	access = json.load(d)

'''
	Load file containing 1000 most common english words. Words in this
	list are excluded from database storage if matched in post.
'''
with open('./1-1000.txt') as f:
	lines = f.readlines()[0:100]
common = [line.strip() for line in lines]

# Reddit connection via praw package
reddit = praw.Reddit(client_id=credentials['reddit']['client_id'],
					client_secret=credentials['reddit']['client_secret'],
					user_agent=credentials['reddit']['user_agent'],
					username=credentials['reddit']['username'],
					password=credentials['reddit']['password'])
learnpython = reddit.subreddit('learnpython')

# Twitter connection via Tweepy
auth = tweepy.OAuthHandler(credentials['twitter']['learnpythonbot']['consumer_key'],
				credentials['twitter']['learnpythonbot']['consumer_secret'])
auth.set_access_token(credentials['twitter']['learnpythonbot']['access_token'],
			credentials['twitter']['learnpythonbot']['access_token_secret'])
api = tweepy.API(auth)


def __open():
	'''
		Open a database connection
	'''
	cnx = mysql.connector.connect(user=access['user'], host=access['host'],
				database='learnpython', password=access['password'])
	cursor = cnx.cursor(dictionary=True)

	return cnx, cursor

def __close(connection, curs):
	'''
		Close a database connection
	'''
	curs.close()
	connection.close()
	return


def newPosts():
	'''
		PURPOSE: Search the /r/learnpython subreddit for new posts and manage
				 flow of script
	'''
	posts = [x for x in learnpython.new(limit=200) if x.created_utc > \
									credentials['reddit']['globalEpoch']]
	if posts:
		for post in posts[::-1]:
			timeUpdater(post.created_utc)
			submissionTweet(post.author.name, post.url, post.title)
			postInsert(post)
			parseTitle(post)
	else:
		pass
	return

def postInsert(submission):
	'''
		PURPOSE: Insert information about new post into `posts` table
				 of MySQL database.
	'''
	cnx, cursor = __open()
	insert = '''INSERT INTO posts \
		(post_id, user, title, body, url, created, created_utc) \
		VALUES \
		(%(id)s, %(author)s, %(title)s, %(selftext)s,\
				 %(url)s, %(created)s, %(created_utc)s)'''
	if submission.author.name == None:
		pass
	else:
		author = str(submission.author.name)
		dictionary = {str(key):str(value) for key, value \
						in submission.__dict__.items() if key != 'author'}
		dictionary['author'] = author
		try:
			cursor.execute(insert, dictionary)
			cnx.commit()
			print("\t--- Successful database insert to table posts ---")
		except mysql.connector.errors.IntegrityError:
			print("\t--- IntegrityError caught in function 'postInsert' ---")

	__close(cnx, cursor)

	return


def tagMatch(p):
	'''
		PURPOSE: Use regular expression to match tags in post title.
				 Tags in the following format will be matched:

				 [tag] --> match: 'tag'
				 (tag) --> match: 'tag'
				 [help with flask] --> match: 'help with flask'

		If backslashes are found in the title tag, each string split will
		be treated as a unique tag.
	'''
	r = re.search('[\[\(]([\w\s\.\_\-\/]{2,})[\]\)]', p.title)
	if r:
		cnx, cursor = __open()

		insert = '''INSERT INTO tags \
			(tag, instances, firstSeen_postID, firstSeen, firstSeen_utc) \
			VALUES \
			(%(tag)s, %(instances)s, %(id)s, %(created)s, %(created_utc)s)'''

		select = '''SELECT * FROM tags'''
		cursor.execute(select)
		tagList = cursor.fetchall()

		# split posts o
		multiple = str(r.group(1)).split('/')

		for match in multiple:	
			if tagList:
				tagDict = {x['tag'].lower(): x['instances'] for x in tagList}
				if match.lower() in tagDict.keys():
					runningTotal = int(tagDict[str(match)]) + 1
					update = '''UPDATE tags \
						SET instances = %s \
						WHERE tag = "%s"''' % (runningTotal, str(match))
					cursor.execute(update)
					cnx.commit()
					print("\t--- Successful database insert to table tags ---")
				else:
					print("\t--- New tag! --> " + str(match))
					newTag = {}
					newTag['tag'] = str(match)
					newTag['instances'] = 1
					newTag['id'] = str(p.id)
					newTag['created'] = str(p.created)
					newTag['created_utc'] = str(p.created_utc)
					cursor.execute(insert, newTag)
					cnx.commit()
					print("\t--- Successful database insert to table tags ---")

			else:
				print("\t--- New tag! --> " + str(match))
				newTag = {}
				newTag['tag'] = str(match)
				newTag['instances'] = 1
				newTag['id'] = str(p.id)
				newTag['created'] = str(p.created)
				newTag['created_utc'] = str(p.created_utc)
				cursor.execute(insert, newTag)
				cnx.commit()
				print("\t--- Successful database insert to table tags ---")


		__close(cnx, cursor)
	
	return


def parseTitle(submission):
	'''
		PURPOSE: Find all unique words in the title of a post and update 
				 the database accordingly.

		In the `titles` table, information about the unique word and its
		number of occurances on in subreddit titles will be stored.
	'''
	words = []
	tokens = [str.lower(x) for x in re.split('[\s_\-]', submission.title) \
					if str.lower(x) not in common]
	for token in tokens:
		word = re.search('(\w{4,})', token)
		if word:
			words.append(word.group())

	counts = {y: words.count(y) for y in words}
	
	cnx, cursor = __open()
	titleSelect = '''SELECT * FROM titles'''
	cursor.execute(titleSelect)
	titleWords = cursor.fetchall()

	titleInsert = '''INSERT INTO titles \
		(word,instances,firstSeen,firstSeen_postID,firstSeen_utc) \
		VALUES (%(word)s, %(instances)s, %(firstSeen)s, %(firstSeen_postID)s, \
					%(firstSeen_utc)s)'''

	titleDict = {str(x['word']):x['instances'] for x in titleWords}

	if titleWords:
		for word, instance in counts.items():
			if str(word) not in titleDict.keys():
				print("\t--- New word found! --> " + str(word))
				newWordDict = {}
				newWordDict['word'] = str(word)
				newWordDict['instances'] = str(instance)
				newWordDict['firstSeen'] = str(submission.created)
				newWordDict['firstSeen_postID'] = str(submission.id)
				newWordDict['firstSeen_utc'] = str(submission.created)

				try:
					cursor.execute(titleInsert, newWordDict)
					cnx.commit()
					print("\t--- Successful database insert to table titles ---")
				except mysql.connector.errors.IntegrityError:
					print("\t--- IntegrityError caught in function 'parseTitle' ---")


			else:
				runningTotal = int(instance) + int(titleDict[word])

				reset = '''UPDATE titles SET instances = %s WHERE word = %s'''
				cursor.execute(reset, (runningTotal, word))
				cnx.commit()
				print("\t--- Successful database UPDATE to table titles ---")
	else:
		for word, instance in counts.items():
			newWordDict = {}
			newWordDict['word'] = word
			newWordDict['instances'] = str(instance)
			newWordDict['firstSeen'] = str(submission.created)
			newWordDict['firstSeen_postID'] = str(submission.id)
			newWordDict['firstSeen_utc'] = str(submission.created)

			cursor.execute(titleInsert, newWordDict)
			cnx.commit()
			print("\t--- Successful database insert to table titles ---")

	__close(cnx, cursor)

	tagMatch(submission)

	return


def submissionTweet(author, url, title):
	'''
		PURPOSE: Configure a tweet from the post's title, author, and url.
	'''
	status_string = f'''{title} - /u/{author} {str(url)}'''
	if len(status_string) > 280:
		additions = len(f'''... - /u/{author} {str(url)}''')
		titleLength = 280 - additions
		status_string = f'''{title[0:titleLength]} ... -/u/{author} {str(url)}'''

	print(time.strftime("%Y/%m/%d %H:%M:%S", time.gmtime())+'\t\t'+status_string)
	try:
		api.update_status(status=status_string)
	except tweepy.error.TweepError:
		print('Status has already been tweeted.')
	time.sleep(3)
	return


def timeUpdater(utcTime):
	'''
		PURPOSE: Update the timestamp stored in JSON file to control which
				 posts are treated as 'new'. Prevents posts from being
				 processed and tweeted more than once.
	'''
	credentials['reddit']['globalEpoch'] = utcTime

	jsonFile = open('./credentials.json', 'r')
	data = json.load(jsonFile)
	jsonFile.close()

	data['reddit']['globalEpoch'] = utcTime

	jsonFile = open('./credentials.json', 'w+')
	jsonFile.write(json.dumps(data))
	jsonFile.close()

	return


if __name__ == '__main__':
	newPosts()




# ----------------------------------- BACK BURNER ---------------------------------- #


'''
for tweet in tweepy.Cursor(api.user_timeline, id=credentials['twitter']['owner_ID']).items():
	api.destroy_status(tweet._json['id'])
'''


# ---------------------------------------------------------------------------------- #











