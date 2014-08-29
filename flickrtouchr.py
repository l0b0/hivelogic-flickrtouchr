#!/usr/bin/env python

#
# FlickrTouchr - a simple python script to grab all your photos from flickr,
#                dump into a directory - organised into folders by set -
#                along with any favourites you have saved.
#
#                You can then sync the photos to an iPod touch.
#
# Version:       1.2
#
# Original Author:	colm - AT - allcosts.net  - Colm MacCarthaigh - 2008-01-21
#
# Modified by:			Dan Benjamin - http://hivelogic.com
#
# License:       		Apache 2.0 - http://www.apache.org/licenses/LICENSE-2.0.html
#

import unicodedata
import sys

import xml.dom.minidom
import webbrowser
import urlparse
import urllib2
import cPickle
import hashlib
import os

API_KEY = "e224418b91b4af4e8cdb0564716fa9bd"
SHARED_SECRET = "7cddb9c9716501a0"
SECRET_AND_API_KEY = SHARED_SECRET + "api_key" + API_KEY

API_SERVICES_URL = 'https://api.flickr.com/services/'
API_REST_URL = API_SERVICES_URL + 'rest/'
API_AUTH_URL = API_SERVICES_URL + 'auth/'
API_KEY_PARAMETER = "api_key=" + API_KEY

FROB_CACHE_FILE = "touchr.frob.cache"


def get_text_nodes_string(nodelist):
    text_nodes = filter(__node_is_text, nodelist)
    text_nodes_string = ''.join(node.data for node in text_nodes)
    return text_nodes_string.encode("utf-8")


def get_frob():
    # Formulate the request
    url = API_REST_URL + "?method=flickr.auth.getFrob"
    url += "&" + API_KEY_PARAMETER + "&api_sig=" + __get_api_signature()

    try:
        dom = __get_web_page_dom(url)

        # get the frob
        frob = get_text_nodes_string(
            dom.getElementsByTagName("frob")[0].childNodes)

        # Free the DOM
        dom.unlink()

        # Return the frob
        return frob

    except:
        raise Exception("Could not retrieve frob")


def get_authorization(frob, perms):
    # Formulate the request
    url = API_AUTH_URL + "?" + API_KEY_PARAMETER + "&perms=" + perms
    url += "&frob=" + frob + "&api_sig=" + __get_authorization_signature(
        frob, perms)

    # Tell the user what's happening
    print "In order to allow FlickrTouchr to read your photos and favourites"
    print "you need to allow the application. Please press return when you've"
    print "granted access at the following url (which should have opened"
    print "automatically)."
    print
    print url
    print
    print "Waiting for you to press return"

    # We now have a login url, open it in a web-browser
    webbrowser.open_new(url)

    # Wait for input
    sys.stdin.readline()

    # Now, try and retrieve a token
    string = SECRET_AND_API_KEY + "frob" + frob + "methodflickr.auth.getToken"
    hash = hashlib.md5(string).hexdigest()

    # Formulate the request
    url = API_REST_URL + "?method=flickr.auth.getToken"
    url += "&" + API_KEY_PARAMETER + "&frob=" + frob
    url += "&api_sig=" + hash

    try:
        return __get_token_and_nsid(url)
    except:
        raise Exception("Login failed")


def __get_token_and_nsid(url):
    dom = __get_web_page_dom(url)
    # get the token and user-id
    token = get_text_nodes_string(
        dom.getElementsByTagName("token")[0].childNodes)
    nsid = dom.getElementsByTagName("user")[0].getAttribute("nsid")
    dom.unlink()
    return (nsid, token)


def sign_request(url, token):
    query = urlparse.urlparse(url).query
    query += "&" + API_KEY_PARAMETER + "&auth_token=" + token
    params = query.split('&')

    # Create the string to hash
    string = SHARED_SECRET

    # Sort the arguments alphabetically
    params.sort()
    for param in params:
        string += param.replace('=', '')
    hash = hashlib.md5(string).hexdigest()

    # Now, append the api_key, and the api_sig args
    url += "&" + API_KEY_PARAMETER
    url += "&auth_token=" + token + "&api_sig=" + hash

    # Return the signed url
    return url


def get_photo(id, token, filename):
    try:
        # Construct a request to find the sizes
        url = API_REST_URL + "?method=flickr.photos.getSizes"
        url += "&photo_id=" + id

        # Sign the request
        url = sign_request(url, token)

        dom = __get_web_page_dom(url)

        # Get the list of sizes
        sizes = dom.getElementsByTagName("size")

        # Grab the original if it exists
        allowedTags = ("Original", "Video Original", "Large")
        if (sizes[-1].getAttribute("label") in allowedTags):
            imgurl = sizes[-1].getAttribute("source")
        else:
            print "Failed to get original for photo id " + id
            dom.unlink()
            return

        # Grab the image file
        response = urllib2.urlopen(imgurl)
        data = response.read()

        # Save the file!
        fh = open(filename, "w")
        fh.write(data)
        fh.close()

        return filename
    except:
        print "Failed to retrieve photo id " + id


def __get_api_signature():
    string = SECRET_AND_API_KEY + "methodflickr.auth.getFrob"
    return hashlib.md5(string).hexdigest()


def __get_authorization_signature(frob, perms):
    string = SECRET_AND_API_KEY + "frob" + frob + "perms" + perms
    return hashlib.md5(string).hexdigest()


def __get_web_page_dom(page_url):
    return xml.dom.minidom.parse(__get_web_page(page_url))


def __get_web_page(page_url):
    return urllib2.urlopen(page_url)


def __node_is_text(node):
    return node.nodeType == node.TEXT_NODE


def __parse_arguments():
    try:
        os.chdir(sys.argv[1])
    except:
        print "usage: %s directory" % sys.argv[0]
        sys.exit(1)


def __get_configuration():
    try:
        cache = open(FROB_CACHE_FILE, "r")
        config = cPickle.load(cache)
        cache.close()

    # We don't - get a new one
    except:
        (user, token) = get_authorization(get_frob(), "read")
        config = {"version": 1, "user": user, "token": token}

        # Save it for future use
        cache = open(FROB_CACHE_FILE, "w")
        cPickle.dump(config, cache)
        cache.close()

    return config


def __get_photo_urls(config):
    url = API_REST_URL + "?method=flickr.photosets.getList"
    url += "&user_id=" + config["user"]
    url = sign_request(url, config["token"])

    dom = __get_web_page_dom(url)

    # Get the list of Sets
    sets = dom.getElementsByTagName("photoset")

    # For each set - create a url
    urls = []
    for set in sets:
        pid = set.getAttribute("id")
        dir = __get_set_directory(set)

        # Build the list of photos
        url = __get_set_url(pid)

        # Append to our list of urls
        urls.append((url, dir))

    # Free the DOM memory
    dom.unlink()

    # Add the photos which are not in any set
    url = API_REST_URL + "?method=flickr.photos.getNotInSet"
    urls.append((url, "No Set"))

    # Add the user's Favourites
    url = API_REST_URL + "?method=flickr.favorites.getList"
    urls.append((url, "Favourites"))
    return urls


def __get_set_directory(set):
    dir = get_text_nodes_string(
        set.getElementsByTagName("title")[0].childNodes)
    # Normalize to ASCII
    dir = unicodedata.normalize(
        'NFKD',
        dir.decode("utf-8", "ignore")).encode('ASCII', 'ignore')
    return dir


def __get_set_url(pid):
    url = API_REST_URL + "?method=flickr.photosets.getPhotos"
    url += "&photoset_id=" + pid
    return url


def __get_photos(config, urls):
    # Time to get the photos
    inodes = {}
    for (url, dir) in urls:
        # Create the directory
        try:
            os.makedirs(dir)
        except:
            pass

        # Get 500 results per page
        url += "&per_page=500"
        pages = page = 1

        while page <= pages:
            dom = __get_photos_page(config, page, url)

            # Get the total
            pages = __get_page_count(dom)
            # Grab the photos
            for photo in dom.getElementsByTagName("photo"):
                # Grab the id
                photoid = photo.getAttribute("id")

                # The target
                target = dir + "/" + photoid + ".jpg"

                # Skip files that exist
                if __path_is_accessible(target):
                    inodes[photoid] = target
                    sys.stdout.write('.')
                    sys.stdout.flush()
                    continue
                else:
                    print ''
                    print photo.getAttribute("title").encode("utf8") + \
                        " ... in set ... " + dir

                if __photo_inode_is_accessible(photoid, inodes):
                    os.link(inodes[photoid], target)
                else:
                    inodes[photoid] = get_photo(
                        photo.getAttribute("id"), config["token"], target)

            # Move on the next page
            page += 1


def __get_photos_page(config, page, url):
    request = url + "&page=" + str(page)
    signed_request = sign_request(request, config["token"])
    return __get_web_page_dom(signed_request)


def __get_page_count(dom):
    try:
        return int(dom.getElementsByTagName(
            "photo")[0].parentNode.getAttribute("pages"))
    except IndexError:
        return 0


def __path_is_accessible(path):
    return os.access(path, os.R_OK)


def __photo_inode_is_accessible(photoid, inodes):
    return photoid in inodes and inodes[photoid] and __path_is_accessible(
        inodes[photoid])


def main():
    __parse_arguments()

    config = __get_configuration()
    urls = __get_photo_urls(config)
    __get_photos(config, urls)


if __name__ == '__main__':
    main()
