﻿# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, RetHost, CUrlItem, ArticleContent
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, CSearchHistoryHelper, remove_html_markup, GetLogoDir, GetCookieDir, byteify
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common, CParsingHelper
import Plugins.Extensions.IPTVPlayer.libs.urlparser as urlparser
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import clean_html
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
import base64
try:    import json
except: import simplejson as json
from datetime import datetime
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
config.plugins.iptvplayer.exua_proxy_enable = ConfigYesNo(default = False)
config.plugins.iptvplayer.exua_language = ConfigSelection(default = "uk", choices = [("ru", "русский"),
                                                                                     ("uk", "українська"),
                                                                                     ("en", "english"),
                                                                                     ("es", "espanol"),
                                                                                     ("de", "deutsch"),
                                                                                     ("fr", "français"),
                                                                                     ("pl", "polski"),
                                                                                     ("ja", "日本語"),
                                                                                     ("kk", "қазақ") ])

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Language:"), config.plugins.iptvplayer.exua_language))
    optionList.append(getConfigListEntry(_("Use ru proxy server:"), config.plugins.iptvplayer.exua_proxy_enable))
    return optionList
###################################################


def gettytul():
    return 'http://www.ex.ua/'

class ExUA(CBaseHostClass):
    MAIN_URL = 'http://www.ex.ua/'
    LANG_URL = MAIN_URL + 'language?lang='
    SRCH_URL = MAIN_URL +  'search?original_id={0}&s=' 
    DEFAULT_ICON_URL = 'http://cdn.keddr.com/wp-content/uploads/2011/10/ex.jpg'
    
    MAIN_CAT_TAB = [{'category':'search',         'title': _('Search'),       'search_item':True},
                    {'category':'search_history', 'title': _('Search history')} 
                   ]
 
    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'ExUA', 'cookie':'ExUA.cookie', 'cookie_type':'MozillaCookieJar', 'proxyURL': config.plugins.iptvplayer.russian_proxyurl.value, 'useProxy': config.plugins.iptvplayer.exua_proxy_enable.value})
        self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE, 'header':{'User-Agent': 'Mozilla/5.0'}}
        self.videoCatsCache = []
        
    def getVideoCats(self):
        return self.videoCatsCache
        
    def _getFullUrl(self, url, series=False):
        if not series:
            mainUrl = self.MAIN_URL
        else:
            mainUrl = self.S_MAIN_URL
        if url.startswith('/'):
            url = url[1:]
        if 0 < len(url) and not url.startswith('http'):
            url = mainUrl + url
        if not mainUrl.startswith('https://'):
            url = url.replace('https://', 'http://')
        return url
        
    def listsTab(self, tab, cItem, type='dir'):
        printDBG("ExUA.listsTab")
        for item in tab:
            params = dict(cItem)
            params.update(item)
            params['name']  = 'category'
            if '' == params.get('icon', ''):
                params['icon'] = self.DEFAULT_ICON_URL
            if type == 'dir':
                self.addDir(params)
            else: self.addVideo(params)
        
    def getMainTab(self, cItem):
        printDBG("ExUA.getMainTab")
        url = self.LANG_URL + config.plugins.iptvplayer.exua_language.value
        sts, data = self.cm.getPage(url, self.defaultParams)
        if not sts: return False
        data = self.cm.ph.getDataBeetwenMarkers(data, '<td class=menu_text>', '</td>', False)[1]
        data = re.compile('''<a[^>]*?href=['"]([^'^"]+?)['"][^>]*?>([^<]+?)</a>''').findall(data)
        haveAccess = False
        videoCatsUrl = ''
        for item in data:
            if 'video' in item[0]:
                params = dict(cItem)
                videoCatsUrl = self._getFullUrl(item[0])
                params.update({'name':'category', 'category':'videos', 'title':item[1], 'url':videoCatsUrl, 'icon':self.DEFAULT_ICON_URL})
                self.addDir(params)
                haveAccess = True
                break
        if not haveAccess:
            msg = _("You probably have not access to this page due to geolocation restriction.")
            msg += '\n' + _("You can use Russian proxy server as a workaround.")
            self.sessionEx.open(MessageBox, msg, type = MessageBox.TYPE_INFO, timeout = 10 )
        else:
            self.videoCatsCache = self._fillVideoCatsCache(videoCatsUrl)
        printDBG(self.videoCatsCache)
        return haveAccess
    
    def _fillVideoCatsCache(self, url):
        printDBG("ExUA._fillVideoCatsCache")
        table = []
        sts, data = self.cm.getPage(url, self.defaultParams)
        if not sts: return []
        data = self.cm.ph.getDataBeetwenMarkers(data, 'class=include_0>', '</table>', False)[1]
        data = data.split('</td>')
        
        for item in data:
            tmp = item.split('<p>')
            title = self.cleanHtmlStr( tmp[0] )
            desc  = self.cleanHtmlStr( tmp[-1] )
            url   = self._getFullUrl(self.cm.ph.getSearchGroups(tmp[0], '''href=['"]([^"^']+?)["']''', 1, True)[0])
            if url.startswith('http'):
                table.append({'title':title, 'url':url, 'desc':desc})
        return table
        
    def listVideosCategories(self, cItem, category):
        printDBG("ExUA.listVideosCategories")
        cItem = dict(cItem)
        cItem['category'] = category
        self.listsTab(self.videoCatsCache, cItem)
            
    def listItems(self, cItem, category='video', m1='class=include_0>'):
        printDBG("ExUA.listMovies")
        url = cItem['url']
        page = cItem.get('page', 0)
        if page > 0:
            if '?' not in url:
                url += '?'
            elif not url.endswith('&'):
                url += '&' 
            url += 'p=%d' % page
        
        sts, data = self.cm.getPage(url, self.defaultParams)
        if not sts: return
        
        nextPage = False
        if 'id="browse_next"' in data:
            nextPage = True
        
        data = self.cm.ph.getDataBeetwenMarkers(data, m1, '</table>', False)[1]
        data = data.split('</td>')
        if len(data):
            del data[-1]
        
        for item in data:
            url    = self.cm.ph.getSearchGroups(item, '''href=["']([^"^']+?)["']''')[0]
            icon   = self.cm.ph.getSearchGroups(item, '''src=["']([^"^']+?)["']''')[0]
            title  = self.cm.ph.getSearchGroups(item, '''alt=["']([^"^']+?)["']''')[0].split('/')
            if len(title) > 1:
                try:
                    tmp = title[0].decode('utf-8').encode('ascii')
                except:
                    del data[0]
            title  = '/'.join(title)
            if '/' in url:
                params = dict(cItem)
                params.update( {'title': self.cleanHtmlStr(title), 'url':self._getFullUrl(url), 'desc': self.cleanHtmlStr( item ), 'icon':self._getFullUrl(icon)} )
                self.addVideo(params)
        
        if nextPage:
            params = dict(cItem)
            params.update( {'title':_('Next page'), 'page':page+1} )
            self.addDir(params)
    
    def listSearchResult(self, cItem, searchPattern, searchType):
        searchPattern = urllib.quote_plus(searchPattern)
        cItem = dict(cItem)
        try:
            idx = int(self.cm.ph.getSearchGroups(searchType, '\[[0-9]+?\]\[([0-9]+?)\]', 1, True)[0])
            url = self.getVideoCats()[idx]['url']
            id  = int(url.split('/')[-1].split('?')[0])
        except:
            printExc()
            return
        cItem['url'] = self.SRCH_URL.format( id ) + urllib.quote_plus(searchPattern)
        self.listItems(cItem, 'video', 'class=panel>')
        
    def getLinksForVideo(self, cItem):
        printDBG("ExUA.getLinksForVideo [%s]" % cItem)
        urlTab = []
        url = cItem['url']
        
        sts, data = self.cm.getPage(url)
        if not sts: return urlTab

        meta = {}
        if config.plugins.iptvplayer.exua_proxy_enable.value:
            meta['http_proxy'] = config.plugins.iptvplayer.russian_proxyurl.value
            
        # download urls
        downloadUrls = []
        subTracks = []
        downData = self.cm.ph.getAllItemsBeetwenMarkers(data, '<td width=17>', '</tr>', False)
        for item in downData:
            printDBG(">>>>>>>>>>>>>>>>>>>> [%s]" % item)
            url    = self.cm.ph.getSearchGroups(item, '''href=["']([^"^']+?)["']''')[0]
            title  = self.cm.ph.getSearchGroups(item, '''title=["']([^"^']+?)["']''')[0]
            if '/get/' not in url:
                continue
            title = self.cleanHtmlStr( title )
            # video
            if 'class="fox-play-btn"' in item: 
                downloadUrls.append({'name':title, 'url':url, 'need_resolve':0})
            elif title.lower().endswith('.srt'):
                subTracks.append({'title':title, 'url':self.up.decorateUrl(self._getFullUrl(url), meta), 'lang':'', 'format':'srt'})
        
        if len (subTracks):
            meta['external_sub_tracks'] = subTracks
        
        # watch urls
        watchUrls = re.compile('''['"](http[^"^']+?\.mp4)['"]''').findall(data)
        tmpAdded = []
        for item in watchUrls:
            if item not in tmpAdded:
                title = '' 
                if len(downloadUrls) > len(tmpAdded):
                    title = '.'.join(downloadUrls[len(tmpAdded)]['name'].split('.')[:-1]) + '.mp4'
                tmpAdded.append(item)
                if title == '':
                    title = str(len(tmpAdded))
                iMeta = dict(meta) 
                iMeta['iptv_format'] = 'video/mp4'
                urlTab.append({'name':_('[watch] %s') % title, 'url':self.up.decorateUrl(item, iMeta), 'need_resolve':0})
            
        for item in downloadUrls:
            item['name'] = _('[download] %s') % item['name']
            item['url'] = self.up.decorateUrl(self._getFullUrl(item['url']), meta)
            urlTab.append(item)

        return urlTab
        
    def getVideoLinks(self, baseUrl):
        printDBG("ExUA.getVideoLinks [%s]" % baseUrl)
        urlTab = []
        
        videoUrl = ''
        if '/get/' in baseUrl:
            sts, data = self.cm.getPage(baseUrl)
            if not sts: return []
            data = self.cm.ph.getDataBeetwenMarkers(data, 'fullyGreenButton', '</a>', False)[1]
            url = self.cm.ph.getSearchGroups(data, 'href="([^"]*?/link/play/[^"]+?)"')[0]
            sts, data = self.cm.getPage(self._getFullUrl(url))
            if not sts: return []
            videoUrl = self.cm.ph.getSearchGroups(data, '<iframe[^>]+?src="(http[^"]+?)"', 1, True)[0]
        
        return urlTab
        
    def getFavouriteData(self, cItem):
        return cItem['url']
        
    def getLinksForFavourite(self, fav_data):
        return self.getLinksForVideo({'url':fav_data})

    def getArticleContent(self, cItem):
        printDBG("ExUA.getArticleContent [%s]" % cItem)
        retTab = []
        
        sts, data = self.cm.getPage(cItem['url'])
        if not sts: return retTab
        
        title = self.cm.ph.getDataBeetwenMarkers(data, '</select>', '</div>', False)[1]
        desc  = self.cm.ph.getDataBeetwenMarkers(data, '<p class="description"', '</p>', True)[1]
        icon  = self.cm.ph.getDataBeetwenMarkers(data, '<div class="coverImage">', '</div>', False)[1]
        icon  = self.cm.ph.getSearchGroups(icon, 'href="([^"]*?\.jpg)"')[0]
        
        descData = self.cm.ph.getDataBeetwenMarkers(data, '<div class="overViewBox">', '</div>', False)[1].split('</dl>')
        printDBG(descData)
        descTabMap = {"Directors":    "director",
                      "Cast":         "actors",
                      "Genres":       "genre",
                      "Country":      "country",
                      "Release Date": "released",
                      "Duration":     "duration"}
        
        otherInfo = {}
        for item in descData:
            item = item.split('</dt>')
            if len(item) < 2: continue
            key = self.cleanHtmlStr( item[0] ).replace(':', '').strip()
            val = self.cleanHtmlStr( item[1] )
            if key in descTabMap:
                otherInfo[descTabMap[key]] = val
        
        imdbRating = self.cm.ph.getDataBeetwenMarkers(data, '<div class="imdbRating', '</p>', True)[1]
        solarRating = self.cm.ph.getDataBeetwenMarkers(data, '<div class="solarRating', '</p>', True)[1]
        
        otherInfo['rating'] = self.cleanHtmlStr( imdbRating )
        otherInfo['rated'] = self.cleanHtmlStr( solarRating )
        
        return [{'title':self.cleanHtmlStr( title ), 'text': self.cleanHtmlStr( desc ), 'images':[{'title':'', 'url':self._getFullUrl(icon)}], 'other_info':otherInfo}]
        
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG( "handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category) )
        self.currList = []
        
    #MAIN MENU
        if name == None:
            self.getMainTab({})
            self.listsTab(self.MAIN_CAT_TAB, {'name':'category'})
    #MOVIES
        elif category == 'videos':
            self.listVideosCategories(self.currItem, 'list_videos')
        elif category == 'list_videos':
            self.listItems(self.currItem)
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
        CHostBase.__init__(self, ExUA(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])

    def getLogoPath(self):
        return RetHost(RetHost.OK, value = [GetLogoDir('exualogo.png')])
    
    def getLinksForVideo(self, Index = 0, selItem = None):
        retCode = RetHost.ERROR
        retlist = []
        if not self.isValidIndex(Index): return RetHost(retCode, value=retlist)
        
        urlList = self.host.getLinksForVideo(self.host.currList[Index])
        for item in urlList:
            retlist.append(CUrlItem(item["name"], item["url"], item['need_resolve']))

        return RetHost(RetHost.OK, value = retlist)
    # end getLinksForVideo
    
    def getResolvedURL(self, url):
        # resolve url to get direct url to video file
        retlist = []
        urlList = self.host.getVideoLinks(url)
        for item in urlList:
            need_resolve = 0
            retlist.append(CUrlItem(item["name"], item["url"], need_resolve))

        return RetHost(RetHost.OK, value = retlist)
        
    #def getArticleContent(self, Index = 0):
    #    retCode = RetHost.ERROR
    #    retlist = []
    #    if not self.isValidIndex(Index): return RetHost(retCode, value=retlist)
    #    cItem = self.host.currList[Index]
    #    
    #    if cItem['type'] != 'video' and cItem['category'] != 'list_seasons':
    #        return RetHost(retCode, value=retlist)
    #    hList = self.host.getArticleContent(cItem)
    #    for item in hList:
    #        title      = item.get('title', '')
    #        text       = item.get('text', '')
    #        images     = item.get("images", [])
    #        othersInfo = item.get('other_info', '')
    #        retlist.append( ArticleContent(title = title, text = text, images =  images, richDescParams = othersInfo) )
    #    return RetHost(RetHost.OK, value = retlist)
    
    def converItem(self, cItem):
        searchTypesOptions = [] # ustawione alfabetycznie
        hostLinks = []
        type = CDisplayListItem.TYPE_UNKNOWN
        possibleTypesOfSearch = None

        if 'category' == cItem['type']:
            if cItem.get('search_item', False):
                type = CDisplayListItem.TYPE_SEARCH
                itId = 0
                tmp = self.host.getVideoCats()
                for idx in range(len(tmp)):
                    searchTypesOptions.append((tmp[idx]['title'], '[0][%s] %s' % (idx, tmp[idx]['title'])))
                possibleTypesOfSearch = searchTypesOptions
            else:
                type = CDisplayListItem.TYPE_CATEGORY
        elif cItem['type'] == 'video':
            type = CDisplayListItem.TYPE_VIDEO
        elif 'more' == cItem['type']:
            type = CDisplayListItem.TYPE_MORE
        elif 'audio' == cItem['type']:
            type = CDisplayListItem.TYPE_AUDIO
            
        if type in [CDisplayListItem.TYPE_AUDIO, CDisplayListItem.TYPE_VIDEO]:
            url = cItem.get('url', '')
            if '' != url:
                hostLinks.append(CUrlItem("Link", url, 1))
            
        title       =  cItem.get('title', '')
        description =  cItem.get('desc', '')
        icon        =  cItem.get('icon', '')
        
        return CDisplayListItem(name = title,
                                    description = description,
                                    type = type,
                                    urlItems = hostLinks,
                                    urlSeparateRequest = 1,
                                    iconimage = icon,
                                    possibleTypesOfSearch = possibleTypesOfSearch)
    # end converItem

    def getSearchItemInx(self):
        try:
            list = self.host.getCurrList()
            for i in range( len(list) ):
                if list[i]['category'] == 'search':
                    return i
        except:
            printDBG('getSearchItemInx EXCEPTION')
            return -1

    def setSearchPattern(self):
        try:
            list = self.host.getCurrList()
            if 'history' == list[self.currIndex]['name']:
                pattern = list[self.currIndex]['title']
                search_type = list[self.currIndex]['search_type']
                self.host.history.addHistoryItem( pattern, search_type)
                self.searchPattern = pattern
                self.searchType = search_type
        except:
            printDBG('setSearchPattern EXCEPTION')
            self.searchPattern = ''
            self.searchType = ''
        return
