Hi, all.

I've created a very simple script that will watch for new posts to the [/r/learnpython](https://www.reddit.com/r/learnpython/) subreddit and tweet out the title, username, and permalink from the twitter account [@learnpythonbot](https://twitter.com/learnpythonbot). Contributors are more than welcome, and I'll be updating the repo as I find free time in my schedule.

At first commit, this is a one-function bot whose only purpose is to tweet links. I'm in the process of turning this into an object-oriented project in order to add the following functionality:
 	
	- Tweet top-10 most-used words in post titles and bodies at the end of each month
	- Tweet top-5 highest-voted posts for each month

I'll add to that list of future functionality as I go along.


Note: File '1-1000.txt' is a list of the 1000 most-used words in the English language. I'm excluding those on the list from being added to the keywords
portion of the databse.
