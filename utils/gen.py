'''utilities in GenerateUtterances class to generate additional utterances for RASA training given a sample utterance.

Author: Matt Stachyra
Date: June 2022
'''
import re
import itertools
from random import shuffle

import numpy as np
from numpy.linalg import norm
import warnings
warnings.filterwarnings('ignore')

import nltk
from nltk.corpus import wordnet as wn
from nltk.tokenize import RegexpTokenizer
from nltk.stem import WordNetLemmatizer,PorterStemmer
from nltk.corpus import stopwords
nltk.download('wordnet')
nltk.download('omw-1.4')

import spacy
nlp = spacy.load("en_core_web_sm")

from gensim.models.word2vec import Word2Vec
import gensim.downloader as api
wikimodel = api.load("glove-wiki-gigaword-100")


class UtteranceGenerator:
    '''class to generate utterances from a single utterance.

    USAGE  call generate() to return a list of possible alternatives utterances.
    NOTE  if a model is not input, then synonyms are not filtered by cosine similarity.
    '''
    def __init__(self, utterance, model=None):
        self._utterance    = self.preprocess(utterance)
        self._posmap       = {'VERB':'v', 'NOUN':'n', 'PRON':'n', 'PROPN':'n', 'ADJ':'a', 'ADV':'r'}
        self._model        = model if model else wikimodel
        self._phrasebank   = self.get_phrases()
        self._synonymsdict = self.map_synonyms()  # {word : synonyms} for words in utterance


    def preprocess(self, utterance):
        '''return list of words in utterance preprocessed to be lower case, removing any non
        alphabetic characters, removing words less than 2 characters.
        '''
        lower     = utterance.lower()
        cleanr    = re.compile('<.*?>')
        cleantext = re.sub(cleanr, '', lower)
        rem_num   = re.sub('[0-9]+', '', cleantext)
        tokenizer = RegexpTokenizer(r'\w+')

        return " ".join(tokenizer.tokenize(rem_num))


    def get_phrases(self):
        need = ['do i need', 'do i need to', 'must i', 'must i have', 'is it required that i', 'will i need', 'will i need to']
        signs = ['what are the signs i need', 'what are the signs i need', 'how do i know i need', 'when will i need to', 'how can i know i need to', 'what are the signs you should', 'when should i have', 'how do i know i should have']
        timing = ['when will I get', 'when can I expect', 'when are', 'by when should I have']
        frequency = ['how often do i need', 'what is the timeframe for']
        scheduling = ['when is my', 'on what date', 'when do i see']
        insurance = ['is this covered', 'will my insurance cover', 'will insurance cover', 'do i need to pay']
        bill = ['what is my bill', 'how much do i owe', 'how much will i pay for']
        location = ['where is', 'where can i find', 'how can i find', 'i cant find', 'what is the location',
                    'can i have the location']
        ability = ['what can i', 'is there anything i can', 'can i']
        preparation = ['what do i need', 'how do i prepare', 'how can i get ready for', 'what should i bring']
        forgetfulness = ['what if i forgot', 'i forgot to', 'is it ok if i forgot']
        explanation = ['what is', 'tell me what is', 'describe', 'i want to understand']
        phrasebank = [need,
                      signs,
                      timing,
                      bill,
                      frequency,
                      scheduling,
                      insurance,
                      location,
                      ability,
                      preparation,
                      forgetfulness,
                      explanation]

        return phrasebank


    def get_pos(self, word):
        '''return the part of speech of the word in the utterance if it is a verb
        noun, pronoun, proper noun, adjective, or adverb.
        '''
        if not self._utterance or not word:
            raise ValueError("Error: Input is empty string.")
        if self.preprocess(word) not in self._utterance:

            raise ValueError("Error: The word is not in the utterance.")

        for w in nlp(self._utterance):
            if str(w)==word: return w.pos_


    def get_similarities(self, word, synonyms, model):
        '''utility for get_synonyms that returns a dictionary with synonym:cosine similarity key-value pairs.
        '''
        def cosinesim(v1, v2):
            return (np.dot(v1, v2 / (norm(v1) * norm(v2))))
        def embed(vector, model):

            try:
                vec = model.get_vector(vector)
            except:
                return np.empty(0)

            return vec

        sims = {word: 1.0}
        ref  = embed(word, model)

        for s in synonyms:
            vec = embed(s, model)
            if vec.any():
                sim     = cosinesim(ref, vec)
                sims[s] = sim

        return sims


    def print_similarities(self, similarities):
        '''print each word with its cosine similarity to a reference vector.
        '''
        for synonym, similarity in similarities.items():
            print(f"word: {synonym}, cosine similarity: {similarity}")


    def get_synonyms(self, word):
        '''return synonyms by taking the lemma generated by synsets that have the same part of speech,
        given a word if its part of speech is a verb, noun, adverb, or adjective.

        NOTE  it is necessary to pass in the pos to get the relevant kind of synonym.
        '''
        pos = self.get_pos(self.preprocess(word))

        if pos not in ['VERB', 'NOUN', 'PRON', 'PROPN', 'ADJ', 'ADV']: return

        # get full set of synonyms
        synonyms = set(list(itertools.chain([synonym
                                             for synset in wn.synsets(word, pos=self._posmap[pos])
                                             for synonym in synset.lemma_names()
                                             if len(word)>1])))

        if not self._model: return synonyms

        # filter this set using cosine similarities
        similarities = self.get_similarities(word, synonyms, self._model)

        return [synonym
                for synonym, similarity in similarities.items()
                if similarity>=0.70]


    def map_synonyms(self):
        '''return dictionary of words to synonyms for words, removing any words
        that do not have synonyms returned.

        NOTE  current version removes ngrams.
        '''
        d = {}

        for word in self._utterance.split():
            synonyms = self.get_synonyms(word)

            if synonyms: synonyms = [synonym
                                     for synonym in synonyms
                                     if len(synonym.split("_"))==1 and self.preprocess(synonym)!=word]

            if synonyms: d[word] = synonyms

        return d


    def add_synonyms(self):
        '''utility for generate() to return a list of generated utterances where a word's synonyms
        are used to replace the word in the original utterance.
        '''
        genlist = []
        tokens  = []
        prev    = 0

        # generate tokens using synonymsmap
        for word in self._utterance.split():
            if word in self._synonymsdict:
                tokens.append(list(itertools.chain(*[[word], self._synonymsdict[word]])))
            else:
                tokens.append([word])

        # use tokens to return new utterances
        for i in range(len(tokens)):
            word  = tokens[i][0]
            slist = tokens[i]

            for j in range(len(slist)):
                start = self._utterance.find(word, prev)
                end   = start + len(word)
                gen   = self._utterance[:start] + slist[j] + self._utterance[end:]
                genlist.append(gen)

            prev = end

        return list(set(genlist))


    def add_phrases(self):
        '''utility for generate() to return a list of generated utterances where phrases from the
        phrasebank are added if there is any match on at least 1 phrase.
        '''
        if not self._phrasebank: return []

        genlist = []
        tokens  = []

        # generate tokens using phrasebank
        for plist in self._phrasebank:
            for phrase in plist:
                if phrase in self._utterance:
                    print("match")
                    for i in range(len(plist)-1):
                        if plist[i]!=phrase:
                            copy = self._utterance
                            tokens.append(copy.replace(phrase, plist[i]))

        return tokens


    def generate(self):
        '''return new list of utterances using any synonyms and phrases.

        NOTE  this current method requires validating the generated text manually.

        TODO  build django app to provide GUI for selecting which utterances to keep.
        '''
        generated = self.add_synonyms()
        generated.extend(self.add_phrases())
        shuffle(generated)

        return generated

