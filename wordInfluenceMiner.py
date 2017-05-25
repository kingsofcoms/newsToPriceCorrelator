#!/usr/bin/python3


##########Utility Functions#############
def removeText(text, term="https?://[^\s]+"):
   import re
   term = "(?P<text>" + term + ")"
   while True:
      textToRemove = re.search(term, text)
      if textToRemove:
         text = text.replace(textToRemove.group("text"), "").replace("  ", " ") 
      else: break
   return text
  
  
def chunks(listToCut, maxLength):
   chunkList = []
   for i in range(0, len(listToCut), maxLength):
      chunkList.append(listToCut[i:i+maxLength])
   return chunkList


def initTwitterApi():
   config = getConfig()
   import tweepy
   twitterKeys = config["twitterKeysMiner"]
   auth = tweepy.OAuthHandler(twitterKeys[0], twitterKeys[1])
   auth.set_access_token(twitterKeys[2], twitterKeys[3])
   return tweepy.API(auth, wait_on_rate_limit_notify=True, wait_on_rate_limit=True)


def getTwitterPosts():
   import tweepy
   import time
   from datetime import datetime
   import string
   tweets = {}
   
   config = getConfig()
   period = config["period"]
   coinNames = list(getCoinNames())
   api = initTwitterApi()
   sinceDate = datetime.fromtimestamp(time.time() - period * 2).strftime('%Y-%m-%d')
   untilDate = datetime.fromtimestamp(time.time() - period).strftime('%Y-%m-%d')
   for chunk in chunks(coinNames, 10):
      for tweet in tweepy.Cursor(api.search, q=" OR ".join(chunk), tweet_mode="extended", until=untilDate, since=sinceDate, lang="en").items(1000):
         tweetText = removeText(tweet._json["full_text"]).lower().strip()
         tweetText = "".join([item for item in list(tweetText) if item not in list(string.punctuation)])
         tweets[tweetText] = tweet._json["user"]["id"]
   return tweets


def removeDuplicateWords(coinPosts):
   allCoinWords = []
   for user in coinPosts:
      userWords = []
      for post in coinPosts[user]: 
         userWords.extend(post.split(" "))
      allCoinWords.extend(list(set(userWords)))
   return allCoinWords


def generateAndRemoveDuplicateBigrams(coinPosts):
   bigrams = []
   for user in coinPosts:
      userBigrams = []
      for post in coinPosts[user]:
         userBigrams.extend([b[0] + " " + b[1] for b in zip(post.split(" ")[:-1], post.split(" ")[1:])])
      bigrams.extend(list(set(userBigrams)))
   return bigrams


def sleepForPeriod(delay=0):
   import time
   config = getConfig()
   period = config["period"]
   currentTime = time.time() - delay
   time.sleep(period - currentTime % period)


def logError():
   import json
   import time
   import traceback
   error = traceback.format_exc()
   print("Exception occured: \n\n" + traceback.format_exc())
   currentTime = time.strftime("%Z - %d/%m/%Y, %H:%M:%S", time.localtime(time.time()))
   try:
      errorLogs = json.loads(open("errorLogs.json").read())
   except: errorLogs = []
   errorLogs.append({"time": currentTime, "error": error})
   with open("errorLogs.json", "w") as errorLogFile:
      errorLogFile.write(json.dumps(errorLogs, indent=2))
   time.sleep(300)
########################################


def getConfig():
   import json
   config = json.loads(open("config.json").read())
   return config


def getCoinNames():
   from poloniex import Poloniex
   polo = Poloniex()
   config = getConfig()
   coinMarketList = [market[market.index("_") + 1:] for market in polo.return24hVolume().keys() if "BTC_" in market]
   coinList = polo.returnCurrencies()
   coinNames = {}
   ignoredCoins = config["ignoredCoins"]
   for coin in coinList:
      if not coinList[coin]["name"].lower() in ignoredCoins and coin in coinMarketList:
         coinNames[coinList[coin]["name"].lower()] = "BTC_" + coin.upper()
   return coinNames


def amalgamatePosts():
   posts = {}
   coinNames = getCoinNames()
   config = getConfig()
   posts.update(getTwitterPosts())
   return posts


def categorizePosts():
   import json
   posts = amalgamatePosts()
   coinNames = getCoinNames()
   categorizedPosts = {}
   for post in posts:
      coins = [coinName for coinName in coinNames if coinName in post]
      if len(coins) == 1:
         coin = coins[0]
         if not coin in categorizedPosts.keys():
            categorizedPosts[coin] = {}
         if not posts[post] in categorizedPosts[coin]:
            categorizedPosts[coin][posts[post]] = []
         categorizedPosts[coin][posts[post]].append(post)
   return categorizedPosts
 

def getWordFrequencies():
   from nltk import FreqDist
   wordFrequencies = {}
   categorizedPosts = categorizePosts()
   for coin in categorizedPosts:
      wordFrequencies[coin] = {}
      bigrams = generateAndRemoveDuplicateBigrams(categorizedPosts[coin])
      allWords = removeDuplicateWords(categorizedPosts[coin])
      allWords.extend(bigrams)
      wordOccurences = FreqDist(allWords).most_common()
      totalWordCount = len(allWords)
      for word in wordOccurences:
         wordFrequencies[coin][word[0]] = word[1] / totalWordCount
   return wordFrequencies


def getPriceMovement():
   import time
   from poloniex import Poloniex
   coinNames = getCoinNames()
   config = getConfig()
   polo = Poloniex()
   coinPriceChanges = {}
   period = config["period"]
   #coinVols = polo.return24hVolume()
   #totalVol = sum([float(coinVols[coin]["BTC"]) for coin in coinVols if "BTC_" in coin])
   for coin in coinNames:
      startTime = time.time() - period
      coinWtdAvg = float(polo.returnChartData(coinNames[coin], start=startTime)[0]["weightedAverage"])
      lastCoinWtdAvg = float(polo.returnChartData(coinNames[coin], start=startTime - period, end=startTime)[0]["weightedAverage"])
      changePercent = coinWtdAvg / lastCoinWtdAvg - 1
      #coinVol = float(coinVols[coinNames[coin]]["BTC"]) / totalVol
      #coinPriceChanges[coin] = [coinVol, changePercent]
      coinPriceChanges[coin] = changePercent
   return coinPriceChanges


def getWordInfluences():
   wordInfluences = {}
   coinPriceChanges = getPriceMovement()
   wordFrequencies = getWordFrequencies()
   for coin in wordFrequencies:
      #coinVol, coinPriceChange = coinPriceChanges[coin]
      coinPriceChange = coinPriceChanges[coin]
      for word in wordFrequencies[coin].keys():
         if not word in wordInfluences.keys():
            wordInfluences[word] = [0, 0]
         totalInfluence, incrementCount = wordInfluences[word]
         wordInfluence = wordFrequencies[coin][word] * coinPriceChange# * coinVol
         wordInfluences[word] = [totalInfluence + wordInfluence, incrementCount + 1]
   return wordInfluences


def updateFile():
   import json
   wordInfluences = getWordInfluences()
   try:
      wordInfluencesFile = json.loads(open("wordInfluences.json").read())
   except: wordInfluencesFile = {}
   for word in wordInfluences:
      if not word in wordInfluencesFile:
         wordInfluencesFile[word] = [0, 0]
      totalInfluence, incrementCount = wordInfluencesFile[word]
      wordInfluencesFile[word] = [totalInfluence + wordInfluences[word][0], incrementCount + wordInfluences[word][1]]
   with open("wordInfluences.json", "w") as wordInfluencesFileObj:
      wordInfluencesFileObj.write(json.dumps(wordInfluencesFile, indent=2))


def loop():
   while True:
      sleepForPeriod()
      while True:
         try:
            updateFile()    
            break
         except:
            logError()


if __name__ == "__main__":
   loop()
   #updateFile() #Debugging


#Made by Alexpimania 2017
