# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, RetHost, CUrlItem, ArticleContent
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, rm, GetPluginDir
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common, CParsingHelper
import Plugins.Extensions.IPTVPlayer.libs.urlparser as urlparser
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import clean_html
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.components.asynccall import iptv_js_execute
from Plugins.Extensions.IPTVPlayer.libs.crypto.cipher.aes_cbc import AES_CBC
###################################################

###################################################
# FOREIGN import
###################################################
import time
import re
import urllib
import string
import random
import base64
import hashlib
from binascii import hexlify, unhexlify
from urlparse import urlparse, urljoin
try:    import json
except Exception: import simplejson as json
from Components.config import config, ConfigSelection, ConfigYesNo, ConfigText, getConfigListEntry
###################################################


###################################################
# E2 GUI COMMPONENTS 
###################################################
from Plugins.Extensions.IPTVPlayer.components.asynccall import MainSessionWrapper
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################

def GetConfigList():
    optionList = []
    return optionList
###################################################


def gettytul():
    return 'https://video.penny.ie/'

class VideoPenny(CBaseHostClass):
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'video.penny.ie', 'cookie':'video.penny.ie.cookie', 'cookie_type':'MozillaCookieJar'})
        self.USER_AGENT = 'User-Agent=Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT':'1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest'} )
        
        self.DEFAULT_ICON_URL = 'https://video.penny.ie/wp-content/uploads/icons/Video-Penny-logo-126x21.png'
        self.MAIN_URL = None
        self.cacheSeries = []
        self.cachePrograms = []
        self.cacheLast = {}

        self.defaultParams = {'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self._getHeaders = None
        
    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        
        def _getFullUrl(url):
            if self.cm.isValidUrl(url): return url
            else: return urljoin(baseUrl, url)
        
        addParams['cloudflare_params'] = {'domain':self.up.getDomain(baseUrl), 'cookie_file':self.COOKIE_FILE, 'User-Agent':self.USER_AGENT, 'full_url_handle':_getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        
    def getFullUrl(self, url):
        url = CBaseHostClass.getFullUrl(self, url)
        try: url.encode('ascii')
        except Exception: url = urllib.quote(url, safe="/:&?%@[]()*$!+-=|<>;")
        return url
        
    def selectDomain(self):                
        self.MAIN_URL = 'https://video.penny.ie/'
        self.MAIN_CAT_TAB = [{'category':'list_series',         'title': 'Seriale',           'url':self.getFullUrl('/new-header/')},
                             {'category':'list_programs',       'title': 'Programy online',   'url':self.getFullUrl('/new-header/')},
                             {'category':'list_sort_filter',    'title': 'Filmy',             'url':self.getFullUrl('/category/filmy-pl/')},
                             {'category':'list_sort_filter',    'title': 'Bajki',             'url':self.getFullUrl('/category/bajki/')},
                             {'category':'list_last',           'title': 'Ostatnio dodane',   'url':self.getFullUrl('/new-header/')},
                             
                             {'category':'search',          'title': _('Search'), 'search_item':True, },
                             {'category':'search_history',  'title': _('Search history'),             } 
                            ]
    def _listTitles(self, cItem, nextCategory, cacheTab, m1, m2):
        printDBG("VideoPenny.listSeries")
        
        if 0 == len(cacheTab):
            uniqueTab = []
            
            sts, data = self.getPage(cItem['url'])
            if not sts: return
            
            allItem = None
            data = self.cm.ph.getDataBeetwenMarkers(data, m1, m2)[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li ', '</li>')
            for item in data:
                url   = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                if not self.cm.isValidUrl(url): continue
                if url in uniqueTab: continue
                
                title = self.cleanHtmlStr(item)
                params = {'title':title, 'tilte_norm':title.upper(), 'url':url}
                if 'OSTATNIO DODANE' in params['tilte_norm']:
                    printDBG("Skip item[%s]" % params)
                    continue
                uniqueTab.append(url)
                if None == allItem and params['tilte_norm'].startswith('WSZYSTKIE'):
                    allItem = params
                else:
                    cacheTab.append(params)
            cacheTab.sort(key=lambda item: item['tilte_norm'])#, reverse=True)
            if allItem != None:
                cacheTab.insert(0, allItem)
                
        for item in cacheTab:
            params = dict(cItem)
            params.update({'good_for_fav':True, 'title':item['title'], 'url':item['url'], 'category':nextCategory})
            self.addDir(params)
    
    def listSeries(self, cItem, nextCategory):
        printDBG("VideoPenny.listSeries")
        self._listTitles(cItem, nextCategory, self.cacheSeries, 'menu-popularne-container', 'menu-tv-shows')
            
    def listPrograms(self, cItem, nextCategory):
        printDBG("VideoPenny.listPrograms")
        self._listTitles(cItem, nextCategory, self.cachePrograms, 'menu-tv-shows', '</ul>')
            
    def listSortFilters(self, cItem, nextCategory):
        printDBG("VideoPenny.listSortFilters")
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        
        data = self.cm.ph.getDataBeetwenMarkers(data, 'video-listing-filter', '</div>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a ', '</a>')
        for item in data:
            url   = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            if not self.cm.isValidUrl(url): continue
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'good_for_fav':False, 'title':title, 'url':url, 'category':nextCategory})
            self.addDir(params)
                
    def listItems(self, cItem):
        printDBG("VideoPenny.listItems")
        
        page = cItem.get('page', 1)
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<a[^>]+?class=["']nextpostslink['"][^>]+?href=['"]([^"^']+?)['"]''')[0])
        
        data = self.cm.ph.getDataBeetwenMarkers(data, 'listing-content', '</section>')[1]
        data = data.split('<div id="post')
        #data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div id="post', '<div class="clearfix">')
        for item in data:
            if 'item-head"' not in item: continue
            
            url   = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            if not self.cm.isValidUrl(url): continue
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h3>', '</h3>')[1])
            if title == '': title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0])
            icon  = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''data-lazy-src=['"]([^'^"]+?)['"]''')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p>', '</p>')[1])
            
            params = dict(cItem)
            params.update({'good_for_fav':True, 'title':title, 'url':url, 'icon':icon, 'desc':desc})
            self.addVideo(params)
        
        if self.cm.isValidUrl(nextPage):
            params = dict(cItem)
            params.update({'good_for_fav':False, 'title':_('Next page'), 'url':nextPage, 'page':page+1})
            self.addDir(params)
            
    def listLast(self, cItem, nextCategory):
        printDBG("VideoPenny.listLast")
        self.cacheLast = {}
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        
        data = self.cm.ph.getDataBeetwenMarkers(data, '<article', '</article>')[1]
        data = data.split('<div class="smart-box-head">')
        if len(data): del data[0]
        for section in data:
            sectionTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(section, '<h2', '</h2>')[1])
            if sectionTitle == '': sectionTitle = 'Inne'
            section = section.split('<div class="video-item format-video">')
            if len(section): del section[0]
            itemsTab = []
            for item in section:
                url   = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                if not self.cm.isValidUrl(url): continue
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h3>', '</h3>')[1])
                if title == '': title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0])
                icon  = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''data-lazy-src=['"]([^'^"]+?)['"]''')[0])
                desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p>', '</p>')[1])
                itemsTab.append({'good_for_fav':True, 'title':title, 'url':url, 'icon':icon, 'desc':desc})
            
            if len(itemsTab):
                self.cacheLast[sectionTitle] = itemsTab
                params = dict(cItem)
                params.update({'good_for_fav':False, 'category':nextCategory, 'title':sectionTitle, 'cache_key':sectionTitle})
                self.addDir(params)
    
    def listLastItems(self, cItem):
        printDBG("VideoPenny.listLastItems")
        cacheKey = cItem.get('cache_key', '')
        tab = self.cacheLast.get(cacheKey, [])
        for item in tab:
            params = dict(cItem)
            params.update(item)
            self.addVideo(params)
        
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("VideoPenny.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        page = cItem.get('page', 1)
        
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('page/%s/?s=%s' % (page, urllib.quote_plus(searchPattern)))
        self.listItems(cItem)
    
    def getLinksForVideo(self, cItem):
        printDBG("VideoPenny.getLinksForVideo [%s]" % cItem)
        
        sts, data = self.getPage(cItem['url'])
        if not sts: return []
        
        urlTab = []
        data = self.cm.ph.getDataBeetwenMarkers(data, 'player-embed', '</div>')[1]
        printDBG(data)
        data = re.compile('''['"](\s*https?://[^"^']+?)\s*['"]''').findall(data)
        printDBG(data)
        for item in data:
            playerUrl = item.strip()
            if not self.cm.isValidUrl(playerUrl): continue
            if 1 != self.up.checkHostSupport(playerUrl): continue 
            urlTab.append({'name':self.up.getDomain(playerUrl, False), 'url':playerUrl, 'need_resolve':1})
        return urlTab
        
    def getVideoLinks(self, videoUrl):
        printDBG("VideoPenny.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        if self.cm.isValidUrl(videoUrl):
            urlTab = self.up.getVideoLinkExt(videoUrl)
        return urlTab
    
    def getFavouriteData(self, cItem):
        printDBG('VideoPenny.getFavouriteData')
        return json.dumps(cItem) 
        
    def getLinksForFavourite(self, fav_data):
        printDBG('VideoPenny.getLinksForFavourite')
        if self.MAIN_URL == None:
            self.selectDomain()
        links = []
        try:
            cItem = byteify(json.loads(fav_data))
            links = self.getLinksForVideo(cItem)
        except Exception: printExc()
        return links
        
    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('VideoPenny.setInitListFromFavouriteItem')
        if self.MAIN_URL == None:
            self.selectDomain()
        try:
            params = byteify(json.loads(fav_data))
        except Exception: 
            params = {}
            printExc()
        self.addDir(params)
        return True
        
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL == None:
            #rm(self.COOKIE_FILE)
            self.selectDomain()

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')
        
        printDBG( "handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category) )
        self.currList = []
        
    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name':'category'})
        elif category == 'list_series':
            self.listSeries(self.currItem, 'list_sort_filter')
        elif category == 'list_programs':
            self.listPrograms(self.currItem, 'list_sort_filter')
        elif category == 'list_sort_filter':
            self.listSortFilters(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'list_last':
            self.listLast(self.currItem, 'list_last_items')
        elif category == 'list_last_items':
            self.listLastItems(self.currItem)
    #SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item':False, 'name':'category'}) 
            self.listSearchResult(cItem, searchPattern, searchType)
    #HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name':'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, VideoPenny(), True, [])
    